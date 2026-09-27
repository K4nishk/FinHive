from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary,
    Numeric, SmallInteger, String, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from loan_manager.infrastructure.database.encrypted_types import (
    EncryptedDecimal,
    EncryptedRupees,
    EncryptedString,
)

# NPI columns below (identity fields + every financial amount) are encrypted
# at rest (KCH-227, ARB D-15) via the `TypeDecorator`s imported above --
# `finhive/db/encryption.py` AES-256-GCM under the hood. Attribute names are
# UNCHANGED from their plaintext originals (`borrower_name`, not
# `borrower_name_ct`): only the mapped column's type changes, which is what
# keeps every repository and mapping function working without modification.
# `migrations/0003_encrypt_npi_columns.sql` (the Postgres path) uses `_ct`
# suffixes instead; the names converge there, not here.
#
# Each identity column above is paired with a `<column>_bidx` column
# (KCH-229, ADR-2.3/ADR-2.4) -- HMAC-SHA256(key_index, normalize(plaintext))
# [:16], see `finhive/db/blind_index.py` -- which is what equality filters
# run against instead of the `_ct` ciphertext (see
# `sqlalchemy_loan_repo.py`). It is computed and kept in sync automatically
# by the mapper events in `blind_index_sync.py`, imported at the bottom of
# this module, never by a repository remembering to set it. Mirrors
# `migrations/0004_add_identity_blind_index.sql` exactly, including which
# columns get one: identity fields only, NEVER an amount -- loan amounts
# cluster on round numbers, so a deterministic index over them would be
# reversible by frequency analysis without the key (ADR-2.4).


class Base(DeclarativeBase):
    pass


class LoanModel(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    # borrower_name/depositor_name: index=True removed. A B-tree over
    # AES-GCM ciphertext with a random IV can never serve a lookup -- the
    # same plaintext encrypts to different bytes every time, so there is
    # nothing stable to index. The working replacement is the `_bidx`
    # HMAC blind index below, delivered in this same change (KCH-229 was
    # folded into KCH-227 -- there is no commit where these columns are
    # encrypted and exact-match filtering is broken).
    borrower_name: Mapped[str] = mapped_column("borrower_name_ct", EncryptedString(), nullable=False)
    borrower_group: Mapped[str] = mapped_column("borrower_group_ct", EncryptedString(), nullable=False)
    depositor_name: Mapped[str] = mapped_column("depositor_name_ct", EncryptedString(), nullable=False)
    depositor_group: Mapped[Optional[str]] = mapped_column("depositor_group_ct", EncryptedString(), nullable=True)
    # Blind-index companions -- see the module-level comment above. Plain
    # LargeBinary, not one of the encrypted TypeDecorators: an HMAC digest
    # is not further encrypted, it IS the stored value.
    borrower_name_bidx: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    borrower_group_bidx: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    depositor_name_bidx: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    depositor_group_bidx: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True, index=True)
    amount: Mapped[int] = mapped_column("amount_ct", EncryptedRupees(), nullable=False)
    giving_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_period: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Which key_version's master this row's ciphertext is under (KCH-227,
    # ARB D-15). Lets rotation migrate rows incrementally rather than in one
    # big-bang re-encrypt -- see finhive/db/keys.py rotate_field.
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class LoanMetaModel(Base):
    __tablename__ = "loan_meta"

    year_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    last_order: Mapped[int] = mapped_column(Integer, nullable=False)


class LoanHistoryModel(Base):
    __tablename__ = "loan_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    borrower_name: Mapped[str] = mapped_column("borrower_name_ct", EncryptedString(), nullable=False)
    borrower_group: Mapped[str] = mapped_column("borrower_group_ct", EncryptedString(), nullable=False)
    depositor_name: Mapped[str] = mapped_column("depositor_name_ct", EncryptedString(), nullable=False)
    depositor_group: Mapped[Optional[str]] = mapped_column("depositor_group_ct", EncryptedString(), nullable=True)
    borrower_name_bidx: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    borrower_group_bidx: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    depositor_name_bidx: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    depositor_group_bidx: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True, index=True)
    amount: Mapped[int] = mapped_column("amount_ct", EncryptedRupees(), nullable=False)
    giving_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    paidoff_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class ReportModel(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    report_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="Pending")
    # KCH-242: who proposed the report -- "FORM" (a human, via the report
    # form -- every report before this issue) or "AGENT" (Ask FinHive,
    # KCH-243+). `server_default` too, not just `default`, so the migration's
    # `ALTER TABLE ... ADD COLUMN actor ... DEFAULT 'FORM'` backfills every
    # pre-existing row without a second UPDATE pass.
    actor: Mapped[str] = mapped_column(String(5), nullable=False, default="FORM", server_default="FORM")
    # The user's own words behind an AGENT-authored report -- NPI (it can
    # name a borrower/amount), encrypted at rest like every other identity
    # column. NULL for a FORM report, which has no such prompt.
    user_request: Mapped[Optional[str]] = mapped_column("user_request_ct", EncryptedString(), nullable=True)
    # Correlates an AGENT report back to the conversation turn that proposed
    # it (KCH-240 wires the FK/index; this column alone carries no
    # referential constraint yet -- see DEBT).
    turn_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    records: Mapped[list[ReportRecordModel]] = relationship(
        "ReportRecordModel", back_populates="report", cascade="all, delete-orphan"
    )


class ReportRecordModel(Base):
    __tablename__ = "report_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(20), ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    # Nullable since KCH-242: a CREATE-mode row proposes a borrower who has
    # no loan yet, so there is no reference_id until ApproveReport mints one
    # on approval (assign_reference_id). Every other mode still always has
    # one -- enforced by the domain entity's __post_init__, not here.
    reference_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    # borrower_group (KCH-242): CREATE-mode only -- the group a NEW borrower
    # would be filed under, since there is no existing loan row to read it
    # from. Deliberately NO `_bidx` companion: this table has never had one
    # for borrower_group (unlike `loans`/`loan_history`), and a CREATE
    # proposal's group is not searched by exact match the way an existing
    # loan's is.
    borrower_group: Mapped[Optional[str]] = mapped_column("borrower_group_ct", EncryptedString(), nullable=True)
    borrower_name: Mapped[str] = mapped_column("borrower_name_ct", EncryptedString(), nullable=False)
    depositor_name: Mapped[str] = mapped_column("depositor_name_ct", EncryptedString(), nullable=False)
    depositor_group: Mapped[Optional[str]] = mapped_column("depositor_group_ct", EncryptedString(), nullable=True)
    # No borrower_group_bidx -- see the borrower_group comment above.
    borrower_name_bidx: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    depositor_name_bidx: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    depositor_group_bidx: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True, index=True)
    amount: Mapped[int] = mapped_column("amount_ct", EncryptedRupees(), nullable=False)
    # Nullable since KCH-242: a CREATE-mode row has no existing loan, so
    # there is no current giving_date -- the proposed one lives in
    # post_extension_giving_date below, per the CREATE row convention.
    giving_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # due_period (KCH-242): CREATE-mode only -- the new loan's due_period,
    # carried alongside post_extension_due_date so ApproveReport's CREATE
    # branch can build a LoanCreateDTO without re-deriving it. Plaintext:
    # it is a term length, not a financial amount (derivation-check note in
    # the KCH-242 plan: a term does not let anyone solve for the principal).
    due_period: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extension_period: Mapped[int] = mapped_column(Integer, nullable=False)
    extension_period_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tds_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # interest_rate/commission_rate stay plaintext (percentages, not
    # balances) -- only the derived amounts below are NPI.
    interest_amount: Mapped[Optional[Decimal]] = mapped_column("interest_amount_ct", EncryptedDecimal(), nullable=True)
    commission_amount: Mapped[Optional[Decimal]] = mapped_column("commission_amount_ct", EncryptedDecimal(), nullable=True)
    tds_amount: Mapped[Optional[Decimal]] = mapped_column("tds_amount_ct", EncryptedDecimal(), nullable=True)
    chq_amount: Mapped[Optional[Decimal]] = mapped_column("chq_amount_ct", EncryptedDecimal(), nullable=True)
    post_extension_giving_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    post_extension_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    paidoff_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    report: Mapped[ReportModel] = relationship("ReportModel", back_populates="records")


class ReportMetaModel(Base):
    __tablename__ = "report_meta"

    report_date: Mapped[str] = mapped_column(String(8), primary_key=True)
    last_order: Mapped[int] = mapped_column(Integer, nullable=False)


# Registers the before_insert/before_update mapper events that keep every
# `_bidx` column above in sync with its identity column automatically
# (KCH-229). Imported here, after the classes it targets exist, so that the
# mere act of importing `models` -- which every repository already does --
# is what wires the hooks up; no repository or caller has to remember to.
from loan_manager.infrastructure.database import blind_index_sync  # noqa: E402,F401
