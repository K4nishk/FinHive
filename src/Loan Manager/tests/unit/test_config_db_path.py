"""`resolve_db_path` / `DEFAULT_DB_PATH` (KCH-231).

`FINHIVE_DB_PATH` lets the demo seeder (and manual testing) point the app at
a throwaway database without touching `data/loans.db`. These pin the
fallback and override behaviour `demo_seed.assert_seed_target` depends on.
"""

from __future__ import annotations

from pathlib import Path

import loan_manager.config as config
from loan_manager.config import resolve_db_path

# `config.DATA_DIR`/`config.DEFAULT_DB_PATH` are read through the `config`
# MODULE inside every test below, never imported by value at module load --
# the tests/conftest.py autouse fixture (KCH-231 review 1, item 1c)
# monkeypatches both, per test, to keep this suite off the real
# `src/Loan Manager/data/` tree. A `from loan_manager.config import
# DEFAULT_DB_PATH` at the top of this file would bind the REAL value once at
# collection time, before that fixture ever runs, and every assertion below
# would then compare `resolve_db_path()`'s (correctly patched) return value
# against a stale constant -- failing for a reason that has nothing to do
# with the fallback behaviour these tests exist to pin.


def test_default_is_data_loans_db() -> None:
    assert config.DEFAULT_DB_PATH == config.DATA_DIR / "loans.db"


def test_finhive_db_path_overrides() -> None:
    # Not an actual temp-file write (S108 false positive here) -- the path
    # is never opened, only resolved and compared as a string.
    resolved = resolve_db_path({"FINHIVE_DB_PATH": "/tmp/somewhere/demo.db"})  # noqa: S108

    assert resolved == Path("/tmp/somewhere/demo.db").resolve()  # noqa: S108
    assert resolved != config.DEFAULT_DB_PATH


def test_finhive_db_path_expands_user() -> None:
    resolved = resolve_db_path({"FINHIVE_DB_PATH": "~/demo.db"})

    assert "~" not in str(resolved)
    assert resolved.is_absolute()


def test_blank_env_falls_back() -> None:
    assert resolve_db_path({"FINHIVE_DB_PATH": ""}) == config.DEFAULT_DB_PATH


def test_whitespace_only_env_falls_back() -> None:
    # A stray space/tab in an env file or shell export, not an intentional
    # path -- `Path("  ").expanduser().resolve()` would otherwise silently
    # resolve to the current working directory (KCH-231 review 1, item 4).
    assert resolve_db_path({"FINHIVE_DB_PATH": "   "}) == config.DEFAULT_DB_PATH
    assert resolve_db_path({"FINHIVE_DB_PATH": "\t"}) == config.DEFAULT_DB_PATH


def test_unset_env_falls_back() -> None:
    assert resolve_db_path({}) == config.DEFAULT_DB_PATH
