"""`infrastructure/seed/demo_seed.py` (KCH-231).

Real SQLite files (WAL journalling and the raw-bytes scan both need one),
never `data/loans.db` -- every test here seeds into `tmp_path`. The autouse
`_active_test_key_ring` fixture (tests/conftest.py) supplies the encrypting
repository's key for the direct `seed()` calls; the CLI tests set real
environment variables instead, because `main()` -> `Container.get_key_ring()`
reads `os.environ` itself, the same as the real app.
"""

from __future__ import annotations

import base64
import os
from datetime import date, datetime, time
from pathlib import Path

import pytest
from loan_manager import config
from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.infrastructure.database.models import Base
from loan_manager.infrastructure.database.session import create_sqlite_engine
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.repositories.sqlalchemy_loan_repo import SqlAlchemyLoanRepository
from loan_manager.infrastructure.seed import demo_seed
from loan_manager.infrastructure.seed.demo_fixture import CHECKPOINTS, DEMO_LOANS, FIXTURE_TODAY
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


def _seeded_engine(db_path: Path, today: date = FIXTURE_TODAY):
    """A fresh, WAL-enabled engine at `db_path`, seeded once."""
    engine = create_sqlite_engine(db_path)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    count = demo_seed.seed(session_factory, today=today)
    return engine, session_factory, count


def _test_key_env(monkeypatch, version: int = 1) -> None:
    """A GENERATED key, never a real one (ORCH ruling) -- see
    `demo_fixture`'s own docstring on seeded data being synthetic-only.
    """
    key = base64.b64encode(bytes([version]) * 32).decode()
    monkeypatch.setenv("FINHIVE_KEY_VERSION", str(version))
    monkeypatch.setenv(f"FINHIVE_MASTER_KEY_V{version}", key)


# --- assert_seed_target ---------------------------------------------------


def test_refuses_protected_db(tmp_path: Path) -> None:
    protected = tmp_path / "loans.db"
    protected.write_bytes(b"not empty")

    # match is deliberately the exact refusal phrase, not just "protected" --
    # pytest's own tmp_path for THIS test is named after the test function
    # (".../test_refuses_protected_db0/..."), so a loose "protected" pattern
    # would match the interpolated path string even if the protected-path
    # check itself were gone, and the "already exists" branch fired instead.
    with pytest.raises(demo_seed.SeedRefused, match="resolves to the protected database"):
        demo_seed.assert_seed_target(protected, protected=protected)


def test_refuses_symlink_to_protected_db(tmp_path: Path) -> None:
    """A plain symlink is caught by the resolved-path equality check --
    `Path.resolve()` dereferences it to `protected`'s own path. The
    `os.path.samefile` branch exists for cases resolve() does NOT collapse
    (see `test_refuses_a_hardlink_to_the_protected_db`)."""
    protected = tmp_path / "real" / "loans.db"
    protected.parent.mkdir()
    protected.write_bytes(b"not empty")
    link = tmp_path / "alias.db"
    link.symlink_to(protected)

    with pytest.raises(demo_seed.SeedRefused, match="resolves to the protected database"):
        demo_seed.assert_seed_target(link, protected=protected)


def test_refuses_non_empty_without_replace(tmp_path: Path) -> None:
    protected = tmp_path / "loans.db"  # exists only to be a plausible target
    target = tmp_path / "demo.db"
    target.write_bytes(b"already has data")

    with pytest.raises(demo_seed.SeedRefused, match="already exists"):
        demo_seed.assert_seed_target(target, protected=protected, replace=False)


def test_replace_removes_target_and_wal_sidecars(tmp_path: Path) -> None:
    protected = tmp_path / "loans.db"
    target = tmp_path / "demo.db"
    target.write_bytes(b"stale")
    (tmp_path / "demo.db-wal").write_bytes(b"stale-wal")
    (tmp_path / "demo.db-shm").write_bytes(b"stale-shm")

    demo_seed.assert_seed_target(target, protected=protected, replace=True)

    assert not target.exists()
    assert not (tmp_path / "demo.db-wal").exists()
    assert not (tmp_path / "demo.db-shm").exists()


def test_refuses_a_hardlink_to_the_protected_db(tmp_path: Path) -> None:
    """A hard link is the `os.path.samefile` branch specifically: unlike a
    symlink, `Path.resolve()` does not follow it back to `protected`'s path,
    so only the `samefile` inode check (not the resolved-equality check
    above) catches this case.
    """
    protected = tmp_path / "loans.db"
    protected.write_bytes(b"not empty")
    hardlink = tmp_path / "hardlink.db"
    os.link(protected, hardlink)
    assert hardlink.resolve() != protected.resolve()  # proves which branch this hits

    with pytest.raises(demo_seed.SeedRefused, match="same file"):
        demo_seed.assert_seed_target(hardlink, protected=protected)


def test_accepts_a_fresh_empty_or_nonexistent_target(tmp_path: Path) -> None:
    protected = tmp_path / "loans.db"
    target = tmp_path / "demo.db"

    demo_seed.assert_seed_target(target, protected=protected)  # must not raise


def test_refuses_config_db_path_even_when_default_db_path_differs(
    tmp_path: Path, monkeypatch
) -> None:
    """`config.DB_PATH` (`resolve_db_path()`: `FINHIVE_DB_PATH` if set, else
    `DEFAULT_DB_PATH`) is the file the real app actually opens, and it can
    differ from `config.DEFAULT_DB_PATH`. `assert_seed_target`'s default
    (`protected=None`) path checked only `config.DEFAULT_DB_PATH`, so a `--db`
    equal to a `FINHIVE_DB_PATH`-redirected live database sailed straight
    through (KCH-231 fix cycle 2, item 4): `config.DB_PATH` must be refused
    too, read fresh from `config` at call time, same as `DEFAULT_DB_PATH`.
    """
    live_db = tmp_path / "live" / "loans.db"
    default_db = tmp_path / "default" / "loans.db"
    monkeypatch.setattr(config, "DB_PATH", live_db)
    monkeypatch.setattr(config, "DEFAULT_DB_PATH", default_db)

    with pytest.raises(demo_seed.SeedRefused, match="resolves to the protected database"):
        demo_seed.assert_seed_target(live_db)  # protected=None -> defaults kick in


def test_refuses_a_hardlink_to_config_db_path(tmp_path: Path, monkeypatch) -> None:
    """The `os.path.samefile` branch of the same `config.DB_PATH` check --
    mirrors `test_refuses_a_hardlink_to_the_protected_db` above, but for
    `DB_PATH` specifically rather than the passed-in `protected`.
    """
    live_db = tmp_path / "live" / "loans.db"
    live_db.parent.mkdir()
    live_db.write_bytes(b"not empty")
    default_db = tmp_path / "default" / "loans.db"
    monkeypatch.setattr(config, "DB_PATH", live_db)
    monkeypatch.setattr(config, "DEFAULT_DB_PATH", default_db)

    hardlink = tmp_path / "hardlink.db"
    os.link(live_db, hardlink)
    assert hardlink.resolve() != live_db.resolve()

    with pytest.raises(demo_seed.SeedRefused, match="same file"):
        demo_seed.assert_seed_target(hardlink)


# --- seed() ----------------------------------------------------------------


def test_statuses_match_status_engine_at_pinned_today(tmp_path: Path) -> None:
    engine, session_factory, count = _seeded_engine(tmp_path / "status.db")
    try:
        assert count == len(DEMO_LOANS)
        session = session_factory()
        repo = SqlAlchemyLoanRepository(session)
        for fixture in DEMO_LOANS:
            loan = repo.get_by_reference_id(fixture.ref)
            assert loan is not None, f"{fixture.ref} was not written"
            assert loan.giving_date == fixture.giving_date
            assert loan.due_date == fixture.due_date
            if fixture.paidoff_date is not None:
                # set_inactive() overwrites the computed status with PAIDOFF
                # -- covered separately by test_paidoff_row_is_archived_and_inactive.
                continue
            expected = StatusEngine.compute(fixture.giving_date, fixture.due_date, FIXTURE_TODAY)
            assert loan.status == expected, (
                f"{fixture.ref}: expected {expected}, got {loan.status}"
            )
        session.close()
    finally:
        engine.dispose()


def test_statuses_match_status_engine_at_a_non_default_pinned_today(tmp_path: Path) -> None:
    """`test_statuses_match_status_engine_at_pinned_today` seeds with the
    DEFAULT `today` (`FIXTURE_TODAY`), which happens to equal the real
    calendar date this suite was written on -- a `seed()` that silently used
    `date.today()` internally instead of its `today` parameter would still
    pass that test on that one day. Seeding with a DIFFERENT pinned `today`
    (2026-06-15 -- distinct from `FIXTURE_TODAY`, and it falls on either side
    of different rows' `due_date`, not before all of them) makes that
    substitution bug show up as a status mismatch (KCH-231 review 1, item
    3b).
    """
    pinned_today = date(2026, 6, 15)
    engine, session_factory, count = _seeded_engine(
        tmp_path / "status_pinned.db", today=pinned_today
    )
    try:
        assert count == len(DEMO_LOANS)
        session = session_factory()
        repo = SqlAlchemyLoanRepository(session)
        for fixture in DEMO_LOANS:
            if fixture.paidoff_date is not None:
                continue  # set_inactive() overwrites status with PAIDOFF regardless of `today`.
            loan = repo.get_by_reference_id(fixture.ref)
            assert loan is not None, f"{fixture.ref} was not written"
            expected = StatusEngine.compute(fixture.giving_date, fixture.due_date, pinned_today)
            assert loan.status == expected, (
                f"{fixture.ref} at pinned today={pinned_today}: expected {expected}, "
                f"got {loan.status} -- seed() may be reading date.today() instead of `today`"
            )
        session.close()
    finally:
        engine.dispose()


def test_seed_writes_the_expected_reference_id_to_borrower_mapping(tmp_path: Path) -> None:
    """Row identities, pinned: every `(reference_id -> borrower_name)` pair
    `DEMO_LOANS` declares must come back unchanged -- catches a row dropped,
    duplicated, or shuffled onto the wrong reference_id (e.g. by a bug in
    `_build_demo_loans`'s per-year-month ordering, or in `seed()`'s own
    iteration) that a coarse row-count check would miss (KCH-231 review 1,
    item 3d).
    """
    engine, session_factory, count = _seeded_engine(tmp_path / "identity.db")
    try:
        assert count == len(DEMO_LOANS)
        session = session_factory()
        repo = SqlAlchemyLoanRepository(session)
        for fixture in DEMO_LOANS:
            loan = repo.get_by_reference_id(fixture.ref)
            assert loan is not None, f"{fixture.ref} missing after seed"
            assert loan.borrower_name == fixture.borrower_name, (
                f"{fixture.ref}: expected borrower {fixture.borrower_name!r}, "
                f"got {loan.borrower_name!r}"
            )
            assert loan.depositor_name == fixture.depositor_name
            assert int(loan.amount) == fixture.amount
        session.close()
    finally:
        engine.dispose()


def test_paidoff_row_is_archived_and_inactive(tmp_path: Path) -> None:
    engine, session_factory, _ = _seeded_engine(tmp_path / "paidoff.db")
    try:
        paidoff_fixture = next(f for f in DEMO_LOANS if f.paidoff_date is not None)
        session = session_factory()
        repo = SqlAlchemyLoanRepository(session)

        loan = repo.get_by_reference_id(paidoff_fixture.ref)
        assert loan is not None
        assert loan.is_active is False
        assert loan.status.value == "Paidoff"

        history_rows = session.execute(
            text("SELECT reference_id, paidoff_date FROM loan_history WHERE reference_id = :ref"),
            {"ref": paidoff_fixture.ref},
        ).fetchall()
        assert len(history_rows) == 1
        assert history_rows[0][1] == paidoff_fixture.paidoff_date.isoformat()

        active = repo.get_all_active()
        assert paidoff_fixture.ref not in {str(loan.reference_id) for loan in active}
        session.close()
    finally:
        engine.dispose()


@pytest.mark.parametrize("field,value,expected", CHECKPOINTS)
def test_checkpoints_reproduce(tmp_path: Path, field: str, value: str, expected: int) -> None:
    db_name = f"checkpoint_{field}_{value}.db".replace(" ", "_")
    engine, session_factory, _ = _seeded_engine(tmp_path / db_name)
    try:
        session = session_factory()
        repo = SqlAlchemyLoanRepository(session)
        matches = repo.get_all_active(filters={field: value})
        matched_refs = [str(loan.reference_id) for loan in matches]
        assert len(matches) == expected, (
            f"{field}={value!r}: expected {expected} active loans, got "
            f"{len(matches)} ({matched_refs})"
        )
        session.close()
    finally:
        engine.dispose()


def test_meera_iyer_and_iyer_chem_coexist_without_cross_matching(tmp_path: Path) -> None:
    """"meera iyer" (a depositor) and "iyer chem" (a borrower group) share
    the substring "iyer". Blind-index equality must not let either field's
    filter pick up the other's rows.
    """
    engine, session_factory, _ = _seeded_engine(tmp_path / "coexist.db")
    try:
        session = session_factory()
        repo = SqlAlchemyLoanRepository(session)

        assert len(repo.get_all_active(filters={"depositor_name": "meera iyer"})) == 3
        assert len(repo.get_all_active(filters={"borrower_group": "iyer chem"})) == 2
        # Cross-field nonsense values must match nothing.
        assert repo.get_all_active(filters={"borrower_group": "meera iyer"}) == []
        assert repo.get_all_active(filters={"depositor_name": "iyer chem"}) == []
        session.close()
    finally:
        engine.dispose()


def test_seed_deterministic_row_identities(tmp_path: Path) -> None:
    """Seeding twice from the same `DEMO_LOANS`/`today` must write the same
    rows -- no random ordering, no `date.today()`/`uuid` sneaking in.
    """
    engine_a, factory_a, count_a = _seeded_engine(tmp_path / "det_a.db")
    engine_b, factory_b, count_b = _seeded_engine(tmp_path / "det_b.db")
    try:
        assert count_a == count_b

        def snapshot(factory):
            session = factory()
            repo = SqlAlchemyLoanRepository(session)
            rows = sorted(
                (
                    str(loan.reference_id),
                    loan.borrower_name,
                    loan.borrower_group,
                    int(loan.amount),
                    loan.status.value,
                    loan.is_active,
                )
                for loan in (repo.get_by_reference_id(f.ref) for f in DEMO_LOANS)
            )
            session.close()
            return rows

        assert snapshot(factory_a) == snapshot(factory_b)
    finally:
        engine_a.dispose()
        engine_b.dispose()


def test_next_create_loan_ref_does_not_collide(tmp_path: Path) -> None:
    """After seeding, the `loan_meta` counter for a year-month DEMO_LOANS
    actually used must be at that month's true max order, so the next
    reference id `CreateLoan` (or this test, standing in for it) generates
    does not already exist.
    """
    engine, session_factory, _ = _seeded_engine(tmp_path / "no_collide.db")
    try:
        session = session_factory()
        uow = SqlAlchemyUnitOfWork(session)

        # "2026_02" carries 10 DEMO_LOANS rows (b3..b11, vikram sharma) --
        # verified independent of demo_seed's own bookkeeping.
        seeded_orders = [
            ReferenceIdService.parse(f.ref)[2]
            for f in DEMO_LOANS
            if ReferenceIdService.year_month_key(*ReferenceIdService.parse(f.ref)[:2]) == "2026_02"
        ]
        expected_last_order = max(seeded_orders)

        last_order = uow.loan_meta.get_last_order("2026_02")
        assert last_order == expected_last_order

        next_ref = ReferenceIdService.next_id(2026, 2, last_order)
        assert uow.loans.get_by_reference_id(next_ref) is None, (
            f"{next_ref} already exists in the seeded data -- would collide"
        )

        now = datetime.now()
        new_loan = Loan(
            id=None,
            reference_id=ReferenceId(next_ref),
            borrower_name="fresh borrower",
            borrower_group="fresh group",
            depositor_name="fresh depositor",
            depositor_group=None,
            amount=Money(5000),
            giving_date=FIXTURE_TODAY,
            due_period=None,
            due_date=None,
            status=StatusEngine.compute(FIXTURE_TODAY, None, FIXTURE_TODAY),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        uow.loans.save(new_loan)
        uow.loan_meta.set_last_order("2026_02", last_order + 1)
        uow.commit()

        assert uow.loans.get_by_reference_id(next_ref) is not None
        # The existing seeded row at the previous order must be untouched --
        # a real collision would have overwritten it instead of erroring
        # (save() upserts by reference_id).
        previous_ref = (
            ReferenceIdService.next_id(2026, 2, last_order - 1) if last_order > 1 else None
        )
        if previous_ref:
            assert uow.loans.get_by_reference_id(previous_ref) is not None
        session.close()
    finally:
        engine.dispose()


def test_seed_rolls_back_and_writes_nothing_on_failure(tmp_path: Path, monkeypatch) -> None:
    """A failure partway through must not leave a half-seeded database --
    `seed()` is documented as one UoW / one commit."""
    db_path = tmp_path / "rollback.db"
    engine = create_sqlite_engine(db_path)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    real_save = SqlAlchemyLoanRepository.save
    calls = {"n": 0}

    def _fail_on_third_save(self, loan):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("simulated failure mid-seed")
        return real_save(self, loan)

    monkeypatch.setattr(SqlAlchemyLoanRepository, "save", _fail_on_third_save)

    try:
        with pytest.raises(RuntimeError, match="simulated failure"):
            demo_seed.seed(session_factory, today=FIXTURE_TODAY)
    finally:
        monkeypatch.undo()

    session = session_factory()
    repo = SqlAlchemyLoanRepository(session)
    assert repo.get_by_reference_id(DEMO_LOANS[0].ref) is None, (
        "a row from before the failure was committed -- seed() must roll back atomically"
    )
    session.close()
    engine.dispose()


# --- raw-bytes NPI scan ------------------------------------------------


def _npi_string_tokens() -> set[str]:
    tokens: set[str] = set()
    for fixture in DEMO_LOANS:
        for value in (
            fixture.borrower_name,
            fixture.borrower_group,
            fixture.depositor_name,
            fixture.depositor_group,
        ):
            if value and len(value) >= 5:
                tokens.add(value)
    return tokens


def _sqlite_minimal_int_bytes(value: int) -> bytes:
    """SQLite record format's own minimal big-endian two's-complement
    integer encoding -- the discrete widths (1, 2, 3, 4, 6, 8 bytes) it
    actually serialises an INTEGER column value into, whichever is the
    smallest that fits. Used only to build a byte pattern to search for;
    this is not a claim about how (or whether) `amount` is stored -- ARB
    D-15 encrypts it, so it should never appear this way at all.
    """
    for width in (1, 2, 3, 4, 6, 8):
        limit = 1 << (width * 8 - 1)
        if -limit <= value < limit:
            return value.to_bytes(width, byteorder="big", signed=True)
    return value.to_bytes(8, byteorder="big", signed=True)


def _npi_amount_int_patterns() -> set[bytes]:
    """The subset of `_npi_amount_patterns()` built from SQLite's minimal
    big-endian integer encoding specifically (kept separate so the scan test
    can assert THIS half is non-empty on its own, not just the ASCII half).

    Every original `DEMO_LOANS` amount is `<= 500000 < 2**23`, which
    `_sqlite_minimal_int_bytes` always encodes in <= 3 bytes -- discarded by
    the `>= 4` filter below, a 2-3 byte sequence recurs constantly in an
    otherwise-random encrypted file by chance alone, so asserting its absence
    proves nothing. That meant the int half of `_npi_amount_patterns()`'s
    result was always empty and the scan's `leaked_amounts` check for the
    int encoding checked nothing, silently (KCH-231 fix cycle 2, item 1).
    `demo_fixture.DEMO_LOANS` now carries one row with `amount=10_000_000`
    (>= `2**23`) specifically so this set is non-empty.
    """
    patterns: set[bytes] = set()
    for fixture in DEMO_LOANS:
        int_bytes = _sqlite_minimal_int_bytes(fixture.amount)
        if len(int_bytes) >= 4:
            patterns.add(int_bytes)
    return patterns


def _npi_amount_patterns() -> set[bytes]:
    """Byte patterns for every `amount` with >= 5 digits, in both encodings
    a plaintext leak could plausibly take: ASCII text, and SQLite's own
    minimal big-endian integer encoding. The int pattern is included only
    when it is itself >= 4 bytes -- a 2-3 byte sequence recurs constantly in
    an otherwise-random encrypted file by chance alone, so asserting its
    absence would prove nothing (KCH-231 review 1, item 3a: the prior scan
    checked names/groups only, never amounts).
    """
    patterns: set[bytes] = set()
    for fixture in DEMO_LOANS:
        digits = str(fixture.amount)
        if len(digits) >= 5:
            patterns.add(digits.encode())
    patterns |= _npi_amount_int_patterns()
    return patterns


def test_raw_bytes_contain_no_plaintext_npi(tmp_path: Path) -> None:
    db_path = tmp_path / "npi_scan.db"
    engine, session_factory, _ = _seeded_engine(db_path)
    tokens = _npi_string_tokens()
    amount_patterns = _npi_amount_patterns()
    int_amount_patterns = _npi_amount_int_patterns()
    assert tokens, "no candidate NPI tokens >= 5 bytes -- fixture changed, test would prove nothing"
    assert amount_patterns, (
        "no candidate amount byte patterns -- fixture changed, test would prove nothing"
    )
    assert int_amount_patterns, (
        "no >= 4 byte SQLite-int-encoded amount pattern -- the int half of "
        "this scan checks nothing without one (KCH-231 fix cycle 2, item 1)"
    )

    def _scan(raw: bytes, when: str) -> None:
        lowered = raw.lower()
        leaked_names = [t for t in tokens if t.encode() in lowered]
        assert not leaked_names, (
            f"plaintext NPI name/group found in raw bytes ({when}): {leaked_names}"
        )
        leaked_amounts = [p for p in amount_patterns if p in raw]
        assert not leaked_amounts, (
            f"plaintext NPI amount found in raw bytes ({when}): {leaked_amounts!r}"
        )

    # While the engine (and its WAL file) is still open -- a committed row
    # can live solely in `-wal` at this point.
    _scan(db_path.read_bytes(), "main file, engine open")
    wal_path = db_path.with_name(db_path.name + "-wal")
    if wal_path.exists():
        _scan(wal_path.read_bytes(), "-wal file, engine open")

    engine.dispose()  # closes the last connection -> WAL auto-checkpoints

    _scan(db_path.read_bytes(), "main file, after dispose")


# --- CLI (main()) ------------------------------------------------------


def test_cli_seeds_with_today_flag(tmp_path: Path, monkeypatch) -> None:
    _test_key_env(monkeypatch)
    db_path = tmp_path / "cli_demo.db"

    exit_code = demo_seed.main(["--db", str(db_path), "--today", "2026-09-25"])

    assert exit_code == 0
    assert db_path.exists()

    engine = create_sqlite_engine(db_path)
    try:
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        repo = SqlAlchemyLoanRepository(session)
        assert len(repo.get_all_active()) == len(DEMO_LOANS) - 1  # one paid off
        session.close()
    finally:
        engine.dispose()


def test_cli_prints_a_success_line_on_a_clean_run(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A successful `main()` run went through a bare `logger.info(...)` with
    no handler attached -- `setup_logging()` is the GUI app's job, never
    called here -- so nothing reached stdout/stderr at all (KCH-231 fix cycle
    2, item 2): a clean seed of the demo database printed nothing whatsoever.
    """
    _test_key_env(monkeypatch)
    db_path = tmp_path / "cli_success_demo.db"

    exit_code = demo_seed.main(["--db", str(db_path)])

    assert exit_code == 0
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "Seeded" in output
    assert str(len(DEMO_LOANS)) in output
    assert str(db_path) in output


def test_cli_seeds_with_a_non_default_today_flag(tmp_path: Path, monkeypatch) -> None:
    """`test_cli_seeds_with_today_flag` passes `--today 2026-09-25`, which
    equals `FIXTURE_TODAY` -- the CLI would produce an identical result even
    if `--today` were silently ignored, so it proves nothing about the flag
    itself (KCH-231 review 1, item 3c). Passing a DIFFERENT pinned date and
    asserting `created_at`/status follow it closes that gap.
    """
    _test_key_env(monkeypatch)
    db_path = tmp_path / "cli_pinned_today.db"
    pinned_today = date(2026, 6, 15)

    exit_code = demo_seed.main(["--db", str(db_path), "--today", pinned_today.isoformat()])

    assert exit_code == 0
    engine = create_sqlite_engine(db_path)
    try:
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        repo = SqlAlchemyLoanRepository(session)
        sample = next(f for f in DEMO_LOANS if f.paidoff_date is None)
        loan = repo.get_by_reference_id(sample.ref)
        assert loan is not None
        assert loan.created_at == datetime.combine(pinned_today, time(9, 0))
        expected_status = StatusEngine.compute(sample.giving_date, sample.due_date, pinned_today)
        assert loan.status == expected_status
        session.close()
    finally:
        engine.dispose()


def test_cli_exits_1_without_key_and_creates_no_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("FINHIVE_KEY_VERSION", raising=False)
    monkeypatch.delenv("FINHIVE_MASTER_KEY_V1", raising=False)
    db_path = tmp_path / "no_key_demo.db"

    exit_code = demo_seed.main(["--db", str(db_path)])

    assert exit_code == 1
    assert not db_path.exists()
    assert not db_path.with_name(db_path.name + "-wal").exists()


def test_cli_with_replace_checks_the_key_before_deleting_an_existing_file(
    tmp_path: Path, monkeypatch
) -> None:
    """`--replace` must not destroy an existing target until AFTER the key
    is proven usable -- `assert_seed_target(replace=True)` unlinks the file
    (and its `-wal`/`-shm` sidecars) as part of its own check, so calling it
    before the key check risked losing whatever `--replace` was about to
    overwrite even when the seed itself then aborts for lack of a key
    (KCH-231 review 1, item 4).
    """
    monkeypatch.delenv("FINHIVE_KEY_VERSION", raising=False)
    monkeypatch.delenv("FINHIVE_MASTER_KEY_V1", raising=False)
    db_path = tmp_path / "existing_demo.db"
    db_path.write_bytes(b"stale-demo-data")

    exit_code = demo_seed.main(["--db", str(db_path), "--replace"])

    assert exit_code == 1
    assert db_path.read_bytes() == b"stale-demo-data", (
        "the existing file was deleted before the key check ran"
    )


def test_cli_refuses_the_protected_default_db_path(tmp_path: Path, monkeypatch, capsys) -> None:
    """Guards against a `--db` typo/omission ever reaching the real
    database: pass `DEFAULT_DB_PATH` itself as --db and confirm main()
    refuses before touching a key or a file.

    `DEFAULT_DB_PATH` is redirected to a path UNDER `tmp_path` here, never
    the real `config.DEFAULT_DB_PATH` -- KCH-231 review 1, item 1b. Passing
    the real one to `main()` means that if `assert_seed_target`'s guard were
    ever broken (exactly the mutation that motivated this fix: item 1a's
    `Path = DEFAULT_DB_PATH` default froze at import time, so a broken guard
    here would have gone on to write the actual live `data/loans.db` on
    every machine that runs this suite, this repo's own included). Testing
    the refusal must never risk the thing it is protecting.
    """
    fake_default = tmp_path / "protected" / "loans.db"
    monkeypatch.setattr(config, "DEFAULT_DB_PATH", fake_default)

    _test_key_env(monkeypatch)
    assert not fake_default.exists(), "precondition: nothing to protect against overwriting"

    exit_code = demo_seed.main(["--db", str(fake_default)])

    assert exit_code == 1
    assert "resolves to the protected database" in capsys.readouterr().err
    assert not fake_default.exists()
