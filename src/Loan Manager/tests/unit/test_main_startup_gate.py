"""main.py Step 3c startup gate (KCH-242, ORCH RULING).

Mirrors Step 3b's existing (untested-at-this-level, but identically shaped)
refuse-and-instruct behaviour for `encrypt_existing_rows`: a database that
predates the report-proposal columns must make the app refuse to start,
print the exact migration command to stderr, and exit 1 -- NEVER run the
migration itself from app startup, since it rewrites `report_records` on
the operator's real ledger.

Every path here is redirected to `tmp_path` by the autouse
`_redirect_data_paths` fixture in `tests/conftest.py`; this file further
points `DB_PATH` at a database THIS test builds and owns, so main() never
touches anything under the real `src/Loan Manager/data/` tree (HARD RULE).
"""
from __future__ import annotations

import base64

import loan_manager.config as config
import loan_manager.infrastructure.database.session as db_session_module
import pytest

from tests.unit.test_report_proposal_migration import M1, _pre_kch242_db, _ring


@pytest.fixture(autouse=True)
def _key_env(monkeypatch):
    """Step 3a now proves the key can decrypt a stored row (F-006 review
    #3), so this must be the key the rows were written under: `_ring()`'s
    master `M1`."""
    monkeypatch.setenv("FINHIVE_KEY_VERSION", "1")
    monkeypatch.setenv("FINHIVE_MASTER_KEY_V1", base64.b64encode(M1).decode())


def _point_db_at(monkeypatch, path) -> None:
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(db_session_module, "DB_PATH", path)


def test_main_refuses_and_instructs_when_report_proposal_migration_is_needed(
    tmp_path, monkeypatch, capsys
):
    import sqlite3

    from loan_manager.application.use_cases.loans.recompute_statuses import (
        RecomputeAllStatuses,
    )
    from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
        needs_migration,
    )

    db_path = tmp_path / "loans.db"
    _pre_kch242_db(db_path, _ring())  # post-KCH-227, pre-KCH-242
    assert needs_migration(db_path) is True

    _point_db_at(monkeypatch, db_path)

    # KCH-242 review, test gap M10: Step 4 (RecomputeAllStatuses) and Step 5
    # (a real Qt event loop) must never run for a gate that is actually
    # doing its job -- but if the gate is REMOVED, main() would sail past
    # Step 3c into Step 4/5 and this test would just HANG on
    # `QApplication.exec()` instead of failing. The sentinel turns that hang
    # into a loud, fast assertion failure below.
    class _ReachedStep4(Exception):
        pass

    def _sentinel(self):
        raise _ReachedStep4

    monkeypatch.setattr(RecomputeAllStatuses, "execute", _sentinel)

    from loan_manager import main

    with pytest.raises(SystemExit) as exc_info:
        main.main()

    assert exc_info.value.code == 1

    stderr = capsys.readouterr().err
    expected_command = (
        "python -m loan_manager.infrastructure.migrations."
        f'add_report_proposal_columns --db "{db_path}"'
    )
    assert expected_command in stderr
    assert "backup" in stderr.lower()
    # KCH-242 review, MINOR: must include `cd "<app_dir>"` before the
    # command, exactly like Step 3b's own printed instructions -- the
    # migration is `python -m loan_manager....`, a package-relative
    # invocation that only resolves from the app's own directory.
    # Cycle-2 test gap (MINOR-4): `'cd "' in stderr` alone still passes if
    # the printed dir were wrong (e.g. `loan_manager/` itself instead of its
    # parent, the actual dir `-m loan_manager....` must run from) -- only
    # the exact path proves main.py's `app_dir` computation is right.
    from pathlib import Path

    app_dir = Path(main.__file__).resolve().parent.parent
    assert f'cd "{app_dir}"' in stderr

    # The migration itself must never have run: `reports`/`report_records`
    # must still be in the exact OLD shape (main() only prints the command,
    # never runs it). Step 2 (`DatabaseSession.initialize()`) legitimately
    # touches the file before this gate even runs -- it creates the OTHER,
    # still-missing tables (loans, loan_meta, ...) and switches on WAL mode,
    # which does change raw bytes -- so schema state, not byte-for-byte
    # file identity, is what "untouched by the migration" means here.
    assert needs_migration(db_path) is True
    conn = sqlite3.connect(db_path)
    try:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(reports)")}
    finally:
        conn.close()
    assert "actor" not in columns
    assert not (tmp_path / "loans.db.pre-kch242-backup").exists()


def test_main_does_not_refuse_on_an_already_migrated_database(tmp_path, monkeypatch):
    """Negative control: a database that already has the KCH-242 columns
    must sail past Step 3c into Step 4 -- proves the gate is actually
    conditional, not an unconditional refusal that would happen to make the
    positive test above pass for the wrong reason.

    Step 4 (RecomputeAllStatuses) is short-circuited with a distinct sentinel
    exception rather than letting main() reach Step 5 and start a real Qt
    event loop (`QApplication.exec()`), which would hang this test.
    """
    from loan_manager.application.use_cases.loans.recompute_statuses import (
        RecomputeAllStatuses,
    )
    from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
        migrate,
        needs_migration,
    )

    db_path = tmp_path / "loans.db"
    ring = _ring()
    _pre_kch242_db(db_path, ring)
    migrate(db_path, ring)
    assert needs_migration(db_path) is False

    _point_db_at(monkeypatch, db_path)

    class _ReachedStep4(Exception):
        pass

    def _sentinel(self):
        raise _ReachedStep4

    monkeypatch.setattr(RecomputeAllStatuses, "execute", _sentinel)

    from loan_manager import main

    with pytest.raises(_ReachedStep4):
        main.main()
