"""Keeps each identity column's `_bidx` companion in sync automatically
(KCH-229, ADR-2.3/ADR-2.4).

`_ct` columns encrypt with a random IV, so equality lookups move to the
paired `_bidx` column instead -- HMAC-SHA256(key_index, normalize(plaintext))
[:16], `finhive/db/blind_index.py`, computed here from `key_ring.key_index()`
(never `key_data()` -- the two are derived independently from the master
precisely so leaking one never leaks the other).

This is a SQLAlchemy mapper event, not a step a repository remembers to
call, because a caller who forgets writes a row that can never be found by
any filter again. `before_insert`/`before_update` fire for every ORM-level
write to `LoanModel`, `LoanHistoryModel` and `ReportRecordModel`, and
recompute every `_bidx` column on the target from its paired identity
column's *current* plaintext attribute -- unconditionally, whether or not
that particular field actually changed, since re-hashing a handful of short
strings is not a cost worth tracking dirty state to avoid.

Registered by importing this module once, at the bottom of `models.py`,
after the three classes exist -- see the comment there.

Bulk updates (`Query.update()`, used by `bulk_update_status`,
`bulk_update_dates` and `set_inactive` in `sqlalchemy_loan_repo.py`) do NOT
fire mapper events and so do NOT go through this module -- but none of them
ever assigns an identity column, only status/date/is_active fields, so their
rows' `_bidx` values (set correctly at the original instance-level insert or
`save()` update) never go stale.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event

from finhive.db.blind_index import compute_blind_index
from loan_manager.infrastructure.database.models import (
    LoanHistoryModel,
    LoanModel,
    ReportRecordModel,
)
from loan_manager.infrastructure.security.key_provider import (
    active_key_index,
    active_key_version,
)

# column -> nothing; just the set of identity columns each model carries a
# `_bidx` companion for. Mirrors migrations/0004_add_identity_blind_index.sql
# exactly, including that report_records has no borrower_group (it never
# had one).
_BIDX_SOURCE_COLUMNS: dict[type, tuple[str, ...]] = {
    LoanModel: ("borrower_name", "borrower_group", "depositor_name", "depositor_group"),
    LoanHistoryModel: ("borrower_name", "borrower_group", "depositor_name", "depositor_group"),
    ReportRecordModel: ("borrower_name", "depositor_name", "depositor_group"),
}


def _sync_blind_indexes(mapper: Any, connection: Any, target: Any) -> None:
    """`before_insert`/`before_update` handler: recompute `target`'s
    `_bidx` columns, and stamp the key version this row is being written
    under.

    Runs before SQLAlchemy's own bind-parameter processing for this INSERT/
    UPDATE, so `target.borrower_name` etc. are still the plain `str`/`None`
    values the caller assigned -- the `EncryptedString` TypeDecorator that
    turns them into ciphertext for the `_ct` column hasn't run yet.
    """
    key_index = active_key_index()
    for column in _BIDX_SOURCE_COLUMNS[type(target)]:
        plaintext = getattr(target, column)
        bidx = (
            compute_blind_index(plaintext, key_index, column=column)
            if plaintext is not None
            else None
        )
        setattr(target, f"{column}_bidx", bidx)

    # Stamp the version actually in use, not a literal. models.py previously
    # carried `default=1`, which recorded "1" no matter which master had
    # encrypted the row -- an authoritative-looking value that could be
    # false, which is worse than recording nothing. Writes always use the
    # CURRENT key (see EncryptedString.process_bind_param), so the current
    # version is by construction the right stamp, on update as well as
    # insert: an UPDATE re-encrypts every mapped column through the same
    # decorator, so the row's ciphertext is wholly current afterwards.
    target.key_version = active_key_version()


for _model in _BIDX_SOURCE_COLUMNS:
    event.listens_for(_model, "before_insert")(_sync_blind_indexes)
    event.listens_for(_model, "before_update")(_sync_blind_indexes)


# --- Enforcement for the paths that bypass the events above -------------

IDENTITY_COLUMNS = frozenset(
    {"borrower_name", "borrower_group", "depositor_name", "depositor_group"}
)


class BlindIndexBypassError(RuntimeError):
    """A bulk UPDATE tried to change an identity column.

    `Query.update()` issues SQL directly and does NOT fire the mapper events
    above, so a row updated that way keeps its OLD `_bidx` while its `_ct`
    becomes new ciphertext. Nothing errors. The row simply stops matching
    every filter, autocomplete and group auto-fill, permanently and
    silently, and no amount of re-reading the database reveals it.

    This used to be "enforced" by a docstring saying the existing bulk
    methods happen not to touch identity columns. A docstring enforces
    nothing -- it is a note about today that the next edit silently
    invalidates. This raises instead.
    """


def assert_no_identity_columns(values: dict) -> dict:
    """Gate every bulk UPDATE payload. Returns it unchanged if safe.

    Use `checked_update` rather than calling this directly; it exists
    separately so a caller building a payload dynamically can check it
    before deciding what to do.
    """
    offending = sorted(IDENTITY_COLUMNS & set(values))
    if offending:
        raise BlindIndexBypassError(
            f"bulk UPDATE would set {offending} without recomputing the "
            f"matching blind index, leaving the row unfindable by every "
            f"filter. Load the row through the ORM and assign the attribute "
            f"-- the before_update event then keeps `_ct` and `_bidx` "
            f"consistent -- or recompute `<column>_bidx` in the same "
            f"statement."
        )
    return values


def checked_update(query: Any, values: dict, **kwargs: Any) -> Any:
    """`Query.update(values)` with the identity-column guard applied."""
    return query.update(assert_no_identity_columns(values), **kwargs)
