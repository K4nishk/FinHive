"""Encryption-at-rest proof across the full write path (KCH-230, ARB D-15/D-16).

Existing coverage before this file, honestly:
 - tests/unit/test_encrypted_types.py: ORM-level round trip and
   no-plaintext-on-disk, `loans` table only, tamper detection at the
   TypeDecorator level (`process_bind_param`/`process_result_value` called
   directly, no DB involved).
 - tests/unit/test_encryption_migration_and_rotation.py
   ::test_legacy_migration_leaves_no_plaintext_names_in_file (renamed by this
   same issue from test_no_plaintext_in_any_encrypted_table): a pre-KCH-227
   `loans` table only, names/groups only.

Neither exercises `loan_history` or `report_records` (including the four
derived amounts ADR-2.4 calls non-optional), the WAL file, the rollback
journal, or a real repository/use-case write path end to end. This file
does. Every row here is written ONLY through `SqlAlchemyUnitOfWork` + real
use cases -- never a raw INSERT, which would bypass the encrypting
repository and prove nothing about it.

KCH-114's "prove encryption at rest before any real data lands" names a wire
leg: under ARB D-16 (Postgres deferred to M1a), SQLite is the only backend
M1.1 ships against, and there is no network hop between the app and its own
local file -- so that clause is N/A here, not silently dropped.
[REVIEW REQUIRED: confirm this reading holds once D-16 lapses and a
Postgres/network leg exists again -- the wire clause would then need its own
proof, which this file does not attempt.]

This file proves the "at rest" half by scanning the raw file (main db + WAL +
rollback journal, including freed/unreclaimed pages within them) rather than
issuing `SELECT` over the three tables. That is strictly stronger: a `SELECT`
only sees what the ORM's TypeDecorators choose to decrypt for a live row, so
it can never notice a stray plaintext byte sitting in a freed page, an old
WAL frame, or a journaled pre-image -- exactly the places a real leak would
hide and a live query would never look.
"""

from __future__ import annotations

import dataclasses
import shutil
import sqlite3
import struct
from datetime import date
from decimal import Decimal
from importlib.util import find_spec
from pathlib import Path

import pytest
from loan_manager.application.dtos.loan_dto import LoanCreateDTO, PaidOffRequestDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.application.use_cases.loans.create_loan import CreateLoan
from loan_manager.application.use_cases.loans.mark_paidoff import MarkPaidOff
from loan_manager.application.use_cases.reports.approve_report import ApproveReport
from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import ExtensionPeriodUnit, LoanStatus
from loan_manager.infrastructure.database.models import Base, LoanHistoryModel
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


def _missing() -> str | None:
    for mod in ("cryptography", "finhive"):
        try:
            if find_spec(mod) is None:
                return mod
        except (ImportError, ValueError):
            return mod
    return None


_MISSING = _missing()
needs_crypto = pytest.mark.skipif(
    _MISSING is not None,
    reason=f"encryption at rest needs `{_MISSING}` -- "
    "pip install -r requirements.txt && pip install -e <repo root>",
)
pytestmark = needs_crypto

if _MISSING is None:  # pragma: no branch - import only when usable
    from finhive.db.encryption import DecryptionError


# --- Fixture data: distinctive strings/amounts, never reused elsewhere -----

BORROWER_A = "zqxvbrell ormondtrap"
GROUP_SHARED = "kwyjibo-cluster"  # A, C1, C2 all carry this group
DEPOSITOR_A = "fenwick glarmoth"
DGROUP_A = "vuxtorial-holdings"
AMOUNT_A = 4_300_000_007  # > 2**32

BORROWER_B = "plimsworth quaggan"
GROUP_B = "druvenhall-group"
DEPOSITOR_B = "orvassk tindlemire"
AMOUNT_B = 5_566_778_899  # > 2**32

BORROWER_C1 = "grimsden vortlecap"
DEPOSITOR_C1 = "control depositor one"
AMOUNT_C1 = 6_123_456_789  # > 2**32

BORROWER_C2 = "halloway tresscombe"
DEPOSITOR_C2 = "control depositor two"
AMOUNT_C2 = 7_234_567_890  # > 2**32

ALL_NAMES = [
    BORROWER_A, DEPOSITOR_A, DGROUP_A, GROUP_SHARED,
    BORROWER_B, DEPOSITOR_B, GROUP_B,
    BORROWER_C1, DEPOSITOR_C1,
    BORROWER_C2, DEPOSITOR_C2,
]
ALL_AMOUNTS = [AMOUNT_A, AMOUNT_B, AMOUNT_C1, AMOUNT_C2]


# --- Needle construction: several plausible on-disk encodings per value ----

def _string_needles(text: str) -> list[bytes]:
    needles: list[bytes] = []
    for variant in {text, text.upper(), text.title()}:
        needles.append(variant.encode("utf-8"))
        needles.append(variant.encode("utf-16-le"))
        needles.append(variant.encode("utf-16-be"))
    return needles


def _indian_grouping(n: int) -> str:
    s = str(n)
    last3, rest = s[-3:], s[:-3]
    parts: list[str] = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ",".join(parts + [last3]) if parts else last3


def _int_big_endian_minimal(n: int) -> bytes:
    """Minimal two's-complement width, floored at 4 bytes.

    Short (1-3 byte) widths are excluded on purpose -- they collide with
    generic binary noise (IVs, tags) constantly and would make this an
    exercise in chasing false positives rather than proving anything.
    """
    length = max(4, (n.bit_length() // 8) + 1)
    return n.to_bytes(length, "big")


def _amount_needles(n: int) -> list[bytes]:
    return [
        str(n).encode(),
        f"{n:,}".encode(),
        _indian_grouping(n).encode(),
        _int_big_endian_minimal(n),
        struct.pack(">d", float(n)),
    ]


def _decimal_needles(d: Decimal) -> list[bytes]:
    needles = [str(d).encode(), struct.pack(">d", float(d))]
    if d == d.to_integral_value():
        # Cheap completeness: an integral derived amount (e.g. "300.00") is
        # also plausible as a raw SQLite INTEGER cell, not just a decimal
        # string or an IEEE-754 double -- cover that encoding too whenever
        # it applies. The fixture's own values are asserted non-integral
        # below, so this branch is defence-in-depth, not what actually
        # fires today.
        needles.append(_int_big_endian_minimal(int(d)))
    return needles


def _haystacks(path: Path) -> bytes:
    """Concatenate the main file with its WAL/rollback-journal siblings,
    whichever of the three exist."""
    chunks = []
    for suffix in ("", "-wal", "-journal"):
        p = Path(str(path) + suffix)
        if p.exists():
            chunks.append(p.read_bytes())
    return b"".join(chunks)


def _assert_no_needles(haystack: bytes, needles: list[bytes], *, label: str) -> None:
    for needle in needles:
        assert needle not in haystack, (
            f"plaintext needle {needle!r} ({label}) is readable in the raw file"
        )


def _sig_digits(d: Decimal) -> int:
    return len(str(abs(d)).replace(".", "").lstrip("0"))


# --- Field-by-field comparison: entity vs DTO, every field, not a subset --

def _loan_fields(loan) -> dict:
    """Every `Loan`/`LoanDTO` field but `id`/`created_at`/`updated_at`, as
    plain primitives so an entity (value objects, `Enum`) and its DTO
    (already primitives via `model_dump`) compare equal field-for-field."""
    d = loan.model_dump() if hasattr(loan, "model_dump") else dataclasses.asdict(loan)
    d.pop("id", None)
    d.pop("created_at", None)
    d.pop("updated_at", None)
    ref = d.get("reference_id")
    if isinstance(ref, dict):  # dataclasses.asdict recursed into ReferenceId
        d["reference_id"] = ref["value"]
    amount = d.get("amount")
    if isinstance(amount, dict):  # dataclasses.asdict recursed into Money
        d["amount"] = amount["amount"]
    status = d.get("status")
    if hasattr(status, "value"):
        d["status"] = status.value
    return d


def _record_fields(record) -> dict:
    """Every `ReportRecord`/`ReportRecordDTO` field but `id`."""
    d = record.model_dump() if hasattr(record, "model_dump") else dataclasses.asdict(record)
    d.pop("id", None)
    unit = d.get("extension_period_unit")
    if hasattr(unit, "value"):
        d["extension_period_unit"] = unit.value
    return d


# --- The populated world: one on-disk file, built ONLY through use cases --

@pytest.fixture(scope="module")
def world(tmp_path_factory):
    # `tests/conftest.py::_active_test_key_ring` is function-scoped and
    # autouse, but this fixture is module-scoped: pytest sets up broader
    # scopes first, so at THIS point in fixture resolution no key ring is
    # active yet. Set the identical ring by hand for this one-time build;
    # every actual test body below still gets it (re-)installed by the
    # per-test autouse fixture before it runs, with the same key material.
    from loan_manager.infrastructure.security.key_provider import set_active_key_ring

    from finhive.db.keys import KeyRing

    set_active_key_ring(KeyRing(current_version=1, masters={1: b"\x42" * 32}))

    db_path = tmp_path_factory.mktemp("at_rest") / "at_rest.db"
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _wal_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA wal_autocheckpoint=0")
        cur.close()

    # Held open for the fixture's whole lifetime. SQLite auto-checkpoints
    # (and can delete) the WAL file when the LAST connection to a database
    # closes; every use case below opens and closes its own session, so
    # without one connection staying open throughout, the WAL could vanish
    # between calls, before the no-plaintext-in-WAL test ever reads it.
    keepalive = engine.connect()

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def uow_factory():
        return SqlAlchemyUnitOfWork(session_factory())

    ref_service = ReferenceIdService()
    event_bus = EventBus()
    create_loan = CreateLoan(uow_factory, ref_service, event_bus)

    loan_a = create_loan.execute(LoanCreateDTO(
        borrower_name=BORROWER_A, borrower_group=GROUP_SHARED,
        depositor_name=DEPOSITOR_A, depositor_group=DGROUP_A,
        amount=AMOUNT_A, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
    ))
    loan_b = create_loan.execute(LoanCreateDTO(
        borrower_name=BORROWER_B, borrower_group=GROUP_B,
        depositor_name=DEPOSITOR_B, depositor_group=None,
        amount=AMOUNT_B, giving_date=date(2026, 2, 1), due_date=None,
    ))
    loan_c1 = create_loan.execute(LoanCreateDTO(
        borrower_name=BORROWER_C1, borrower_group=GROUP_SHARED,
        depositor_name=DEPOSITOR_C1, depositor_group=None,
        amount=AMOUNT_C1, giving_date=date(2026, 3, 1), due_date=date(2026, 6, 1),
    ))
    loan_c2 = create_loan.execute(LoanCreateDTO(
        borrower_name=BORROWER_C2, borrower_group=GROUP_SHARED,
        depositor_name=DEPOSITOR_C2, depositor_group=None,
        amount=AMOUNT_C2, giving_date=date(2026, 3, 5), due_date=date(2026, 6, 5),
    ))

    mark_paidoff = MarkPaidOff(uow_factory, event_bus)
    report_dto = mark_paidoff.execute(
        loan_a.reference_id,
        PaidOffRequestDTO(
            paidoff_date=date(2026, 4, 15),
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
            tds_flag=True,
        ),
    )
    # Sanity: the fixture's own derived-amount needles must actually be
    # substantial numbers, not e.g. "0.00" -- a needle that small would
    # match constantly and prove nothing.
    for field in ("interest_amount", "commission_amount", "tds_amount", "chq_amount"):
        value = getattr(report_dto.records[0], field)
        assert value is not None and _sig_digits(value) >= 6, (
            f"fixture {field}={value!r} has too few significant digits to "
            f"serve as a needle"
        )
        assert value != value.to_integral_value(), (
            f"fixture {field}={value!r} is integral -- pick inputs that "
            f"produce a fractional derived amount so the needle set actually "
            f"exercises the decimal-string/float paths in this run, not just "
            f"the (also-handled) integral-amount branch in _decimal_needles"
        )

    recovery = RecoveryService()
    recovery.write = lambda *a, **k: None
    recovery.clear = lambda: None
    backup = BackupService()
    backup.create_backup = lambda: None
    approve = ApproveReport(uow_factory, recovery, backup, event_bus)
    approval = approve.execute(report_dto.report_id)
    assert approval.success, "fixture setup: report must approve cleanly"

    # Independently-computed expected report-record fields, NOT read from
    # `report_dto` -- `report_dto` is itself built by the same
    # `report_model_to_entity` mapping the round-trip test later re-reads
    # through, so comparing a fresh read against `report_dto` would pass
    # even if that ONE shared mapping function swapped two fields, because
    # both sides would be wrong the same way. This recomputes the derived
    # amounts by hand from the known inputs via `InterestCalculator`, the
    # same formulas `MarkPaidOff` itself calls, so the expected side never
    # goes through the repository/mapper layer at all.
    extension_period = (date(2026, 4, 15) - date(2026, 4, 1)).days
    interest_amount = InterestCalculator.calculate_daily(AMOUNT_A, Decimal("12"), extension_period)
    commission_amount = InterestCalculator.calculate_daily(AMOUNT_A, Decimal("6"), extension_period)
    tds_amount = InterestCalculator.calculate_tds(interest_amount)
    chq_amount = InterestCalculator.calculate_chq(interest_amount, tds_amount)
    expected_record = {
        "report_id": report_dto.report_id,
        "reference_id": loan_a.reference_id,
        "borrower_name": BORROWER_A,
        "depositor_name": DEPOSITOR_A,
        "depositor_group": DGROUP_A,
        "amount": AMOUNT_A,
        "giving_date": date(2026, 1, 1),
        "due_date": date(2026, 4, 1),
        "extension_period": extension_period,
        "extension_period_unit": ExtensionPeriodUnit.DAYS.value,
        "interest_rate": Decimal("12"),
        "commission_rate": Decimal("6"),
        "tds_flag": True,
        "interest_amount": interest_amount,
        "commission_amount": commission_amount,
        "tds_amount": tds_amount,
        "chq_amount": chq_amount,
        "post_extension_giving_date": None,
        "post_extension_due_date": None,
        "paidoff_date": date(2026, 4, 15),
    }

    # Same trap, same fix, for loan A/B: `world["loan_a"]`/`world["loan_b"]`
    # are themselves built by `loan_entity_to_model` -> `loan_model_to_entity`
    # at creation time (see `SqlAlchemyLoanRepository.save`), the SAME
    # mapping pair the round-trip test re-reads through later. Comparing a
    # fresh read against those DTOs would pass even if that mapping swapped
    # or coerced a field, because both sides would already be wrong the same
    # way. These are independently known from the fixture's own inputs and a
    # direct `StatusEngine.compute` call instead.
    today = date.today()
    expected_loan_b = {
        "reference_id": loan_b.reference_id,
        "borrower_name": BORROWER_B,
        "borrower_group": GROUP_B,
        "depositor_name": DEPOSITOR_B,
        "depositor_group": None,
        "amount": AMOUNT_B,
        "giving_date": date(2026, 2, 1),
        "due_period": None,
        "due_date": None,
        "status": StatusEngine.compute(date(2026, 2, 1), None, today).value,
        "is_active": True,
    }
    expected_loan_a = {
        "reference_id": loan_a.reference_id,
        "borrower_name": BORROWER_A,
        "borrower_group": GROUP_SHARED,
        "depositor_name": DEPOSITOR_A,
        "depositor_group": DGROUP_A,
        "amount": AMOUNT_A,
        "giving_date": date(2026, 1, 1),
        "due_period": None,
        "due_date": date(2026, 4, 1),
        # Post-ApproveReport: archived and marked Paidoff regardless of what
        # StatusEngine would compute from dates alone (business rule).
        "status": LoanStatus.PAIDOFF.value,
        "is_active": False,
    }

    yield {
        "db_path": db_path,
        "uow_factory": uow_factory,
        "loan_a": loan_a,
        "loan_b": loan_b,
        "loan_c1": loan_c1,
        "loan_c2": loan_c2,
        "report_dto": report_dto,
        "expected_record": expected_record,
        "expected_loan_a": expected_loan_a,
        "expected_loan_b": expected_loan_b,
    }

    keepalive.close()
    engine.dispose()


# --- 1. Round trip through repositories, including a null due_date --------

def test_round_trip_through_repositories_is_exact_including_null_due_date(world):
    """A FRESH engine on the SAME file -- no Python object survives from the
    fixture's own session -- must read back EVERY field of loan A, loan B,
    the report record and the history row exactly as written, not a
    hand-picked subset of them: the amount as `int`, the derived amounts as
    2dp `Decimal`, a loan created with no `due_date` as `None` (not some
    coerced sentinel), and every identity/date/rate/flag field bit for bit.
    """
    fresh_engine = create_engine(f"sqlite:///{world['db_path']}")
    session = sessionmaker(bind=fresh_engine, expire_on_commit=False)()
    uow = SqlAlchemyUnitOfWork(session)

    loan_a = uow.loans.get_by_reference_id(world["loan_a"].reference_id)
    loan_b = uow.loans.get_by_reference_id(world["loan_b"].reference_id)
    assert loan_a is not None and loan_b is not None

    # Loan B is never touched after creation -- every field must match the
    # independently known inputs exactly (NOT `world["loan_b"]`; see why in
    # the `world` fixture above).
    assert _loan_fields(loan_b) == world["expected_loan_b"], (
        "loan B must round-trip every field exactly"
    )
    assert loan_b.due_date is None, (
        "a loan created with due_date=None must read back as None -- not "
        "coerced to giving_date or any other sentinel"
    )

    # Loan A went through ApproveReport, which legitimately changes `status`
    # and `is_active` (Active -> Paidoff, archived) -- everything else
    # (identity fields, amount, giving_date, due_date, due_period) must
    # still match the independently known creation inputs exactly.
    assert _loan_fields(loan_a) == world["expected_loan_a"], (
        "loan A must round-trip every field exactly (status/is_active "
        "updated by ApproveReport, per business rule)"
    )
    assert isinstance(int(loan_a.amount), int)

    report = uow.reports.get_by_report_id(world["report_dto"].report_id)
    assert report is not None
    record = report.records[0]
    assert _record_fields(record) == world["expected_record"], (
        "the report record must round-trip every field exactly, not just "
        "the four derived amounts -- compared against independently "
        "computed expected values, not against report_dto (which is built "
        "by the same mapping function this re-read exercises)"
    )
    for field in ("interest_amount", "commission_amount", "tds_amount", "chq_amount"):
        got = getattr(record, field)
        assert isinstance(got, Decimal)
        assert got == got.quantize(Decimal("0.01")), (
            f"{field} did not round-trip at exactly two decimal places: {got!r}"
        )

    history_id = (
        session.query(LoanHistoryModel.id)
        .filter_by(reference_id=world["loan_a"].reference_id)
        .scalar()
    )
    assert history_id is not None, "loan A must have been archived to loan_history"
    history = session.get(LoanHistoryModel, history_id)
    # Every LoanHistoryModel column but `id`/`archived_at` (timestamp).
    expected_history = {
        "reference_id": world["loan_a"].reference_id,
        "borrower_name": BORROWER_A,
        "borrower_group": GROUP_SHARED,
        "depositor_name": DEPOSITOR_A,
        "depositor_group": DGROUP_A,
        "amount": AMOUNT_A,
        "giving_date": date(2026, 1, 1),
        "due_date": date(2026, 4, 1),
        "paidoff_date": date(2026, 4, 15),
        "key_version": 1,
    }
    got_history = {field: getattr(history, field) for field in expected_history}
    assert got_history == expected_history, (
        f"history row: {got_history} != {expected_history}"
    )

    session.close()
    fresh_engine.dispose()


# --- 2. No plaintext anywhere in the WAL-mode file, across all 3 tables ----

def test_no_plaintext_in_db_or_wal_across_loans_history_and_report_records(world):
    wal_path = Path(str(world["db_path"]) + "-wal")
    assert wal_path.exists() and wal_path.stat().st_size > 0, (
        "expected a non-empty WAL file (wal_autocheckpoint=0 must still be "
        "in effect) -- otherwise this test silently degrades to scanning "
        "only the checkpointed main file"
    )

    haystack = _haystacks(world["db_path"])

    # Positive control: reference_id is NOT NPI and stays plaintext by
    # design, so it MUST be findable here -- proves the scan is reading
    # real, meaningful data rather than an empty or wrong file.
    assert world["loan_a"].reference_id.encode() in haystack, (
        "positive control failed: even the plaintext reference_id is "
        "unreadable, so this scan is not exercising real data"
    )

    for name in ALL_NAMES:
        _assert_no_needles(haystack, _string_needles(name), label=name)
    for amount in ALL_AMOUNTS:
        _assert_no_needles(haystack, _amount_needles(amount), label=f"amount {amount}")

    expected = world["report_dto"].records[0]
    for field in ("interest_amount", "commission_amount", "tds_amount", "chq_amount"):
        value = getattr(expected, field)
        if value is not None:
            _assert_no_needles(haystack, _decimal_needles(value), label=f"{field}={value}")


# --- 3. No plaintext in a PERSIST-mode rollback journal --------------------

def test_no_plaintext_in_rollback_journal(tmp_path):
    """A second, independent engine/file in `journal_mode=PERSIST`: an
    INSERT followed by an UPDATE forces SQLite to write the pre-update page
    (already ciphertext, from the INSERT) into the rollback journal -- a
    completely different on-disk path from the WAL file in `world`.
    """
    db_path = tmp_path / "journal.db"
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _persist_journal(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=PERSIST")
        cur.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def uow_factory():
        return SqlAlchemyUnitOfWork(session_factory())

    create_loan = CreateLoan(uow_factory, ReferenceIdService(), EventBus())
    loan = create_loan.execute(LoanCreateDTO(
        borrower_name=BORROWER_C1, borrower_group=GROUP_SHARED,
        depositor_name=DEPOSITOR_C1, depositor_group=None,
        amount=AMOUNT_C1, giving_date=date(2026, 3, 1), due_date=date(2026, 6, 1),
    ))

    # Mutate borrower_name specifically, not the (originally NULL)
    # depositor_group: a NULL column has no ciphertext blob to begin with, so
    # updating it would leave no real pre-image for the journal to hold.
    # borrower_name has a real ciphertext blob from the INSERT above, so its
    # OLD value's ciphertext exists ONLY in the journal's pre-image page
    # after this UPDATE overwrites the main db page with new ciphertext.
    updated_borrower_name = "renamed control borrower"
    with uow_factory() as uow:
        existing = uow.loans.get_by_reference_id(loan.reference_id)
        existing.borrower_name = updated_borrower_name
        uow.loans.save(existing)
        uow.commit()

    journal_path = Path(str(db_path) + "-journal")
    assert journal_path.exists() and journal_path.stat().st_size > 0, (
        "expected a non-empty PERSIST-mode rollback journal after the update"
    )

    # Positive control scoped to the journal file ALONE (not the combined
    # haystack) -- proves the journal itself holds real page data, not an
    # empty or zeroed-out file.
    journal_bytes = journal_path.read_bytes()
    assert loan.reference_id.encode() in journal_bytes, (
        "positive control missing from the journal file itself"
    )

    haystack = _haystacks(db_path)
    assert loan.reference_id.encode() in haystack, "positive control missing"

    for name in (BORROWER_C1, updated_borrower_name, DEPOSITOR_C1, GROUP_SHARED):
        _assert_no_needles(haystack, _string_needles(name), label=name)
    _assert_no_needles(haystack, _amount_needles(AMOUNT_C1), label=f"amount {AMOUNT_C1}")

    engine.dispose()


# --- 4. A tampered ciphertext value raises, never decrypts wrong -----------

def test_flipped_bit_in_stored_ct_value_raises_decryption_error(world, tmp_path):
    """A raw sqlite3 UPDATE XORs the last byte of a stored ciphertext blob --
    inside its GCM tag -- for `loans.borrower_name_ct` and
    `report_records.interest_amount_ct`.

    TEST-ONLY tamper: no production code path ever writes a `_ct` column
    outside the encrypting repository. This simulates disk corruption or an
    attacker's edit to prove the read path raises rather than ever
    returning corrupted plaintext.
    """
    copy_path = tmp_path / "tamper.db"
    shutil.copy2(world["db_path"], copy_path)
    wal_src = Path(str(world["db_path"]) + "-wal")
    if wal_src.exists():
        shutil.copy2(wal_src, str(copy_path) + "-wal")

    raw = sqlite3.connect(str(copy_path))
    try:
        loan_row = raw.execute(
            "SELECT id, borrower_name_ct FROM loans WHERE reference_id = ?",
            (world["loan_a"].reference_id,),
        ).fetchone()
        assert loan_row is not None
        loan_row_id, blob = loan_row
        tampered = bytearray(blob)
        tampered[-1] ^= 0xFF
        raw.execute(
            "UPDATE loans SET borrower_name_ct = ? WHERE id = ?",
            (bytes(tampered), loan_row_id),
        )

        record_row = raw.execute(
            "SELECT id, interest_amount_ct FROM report_records "
            "WHERE report_id = ? AND reference_id = ?",
            (world["report_dto"].report_id, world["loan_a"].reference_id),
        ).fetchone()
        assert record_row is not None
        record_id, record_blob = record_row
        tampered_record = bytearray(record_blob)
        tampered_record[-1] ^= 0xFF
        raw.execute(
            "UPDATE report_records SET interest_amount_ct = ? WHERE id = ?",
            (bytes(tampered_record), record_id),
        )
        raw.commit()
    finally:
        raw.close()

    engine = create_engine(f"sqlite:///{copy_path}")
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    uow = SqlAlchemyUnitOfWork(session)

    with pytest.raises(DecryptionError):
        uow.loans.get_by_reference_id(world["loan_a"].reference_id)

    with pytest.raises(DecryptionError):
        uow.reports.get_by_report_id(world["report_dto"].report_id)

    session.close()
    engine.dispose()


# --- 5. No SQLite index covers any amount column ---------------------------

def test_no_sqlite_index_covers_an_amount_column(world):
    """Scoped to the SQLite ORM schema this file builds via
    `Base.metadata.create_all` -- the Postgres schema
    (`migrations/0003`/`0004`) is a separate artifact, covered separately by
    the root `tests/integration` lane (deferred to M1a per ARB D-16)."""
    amount_ct_columns = {
        "amount_ct", "interest_amount_ct", "commission_amount_ct",
        "tds_amount_ct", "chq_amount_ct",
    }
    raw = sqlite3.connect(str(world["db_path"]))
    try:
        for table in ("loans", "loan_history", "report_records"):
            for _seq, index_name, *_rest in raw.execute(f"PRAGMA index_list({table})"):
                indexed_columns = {
                    info[2] for info in raw.execute(f"PRAGMA index_info({index_name})")
                }
                offending = indexed_columns & amount_ct_columns
                assert not offending, (
                    f"{table}.{index_name} indexes {offending} -- an amount "
                    f"column must never carry any index (ADR-2.4: round-number "
                    f"loan amounts are reversible by frequency analysis "
                    f"without the key)"
                )
    finally:
        raw.close()


# --- 6. Blind index is deterministic, and exact-match filtering is exact --

def test_blind_index_is_deterministic_and_exact_filter_returns_right_rows(world):
    raw = sqlite3.connect(str(world["db_path"]))
    try:
        rows = dict(raw.execute(
            "SELECT reference_id, borrower_group_bidx FROM loans "
            "WHERE reference_id IN (?, ?)",
            (world["loan_c1"].reference_id, world["loan_c2"].reference_id),
        ).fetchall())
    finally:
        raw.close()

    assert len(rows) == 2
    assert rows[world["loan_c1"].reference_id] == rows[world["loan_c2"].reference_id], (
        "two rows written with the same borrower_group must carry the exact "
        "same blind index -- it is a DETERMINISTIC digest, not a per-row "
        "random one"
    )

    uow = world["uow_factory"]()
    try:
        matches = uow.loans.get_all_active(filters={"borrower_group": GROUP_SHARED})
    finally:
        uow.session.close()
    matched_refs = {loan.ref_id_str() for loan in matches}

    assert matched_refs == {world["loan_c1"].reference_id, world["loan_c2"].reference_id}, (
        f"exact-match filter on {GROUP_SHARED!r} returned {matched_refs}, "
        f"expected exactly the two active loans sharing that group -- "
        f"loan_a shares the group too but is archived/inactive, loan_b has "
        f"a wholly different group"
    )
