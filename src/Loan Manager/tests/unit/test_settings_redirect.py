"""Autouse `_redirect_data_paths` fixture (tests/conftest.py) also patches
BY-VALUE imports of config constants in modules that copied them at their own
module load (KCH-231 fix cycle 2, item 3) -- patching `config.SETTINGS_FILE`
/ `config.DATA_DIR` alone never reaches `settings_tab.py`'s or
`csv_to_sqlite.py`'s own already-bound names, both of which do
`from loan_manager.config import ...` at module scope.
"""

from __future__ import annotations

import loan_manager.config as config
import loan_manager.infrastructure.migrations.csv_to_sqlite as csv_to_sqlite
import loan_manager.presentation.tabs.settings_tab as settings_tab


def test_settings_tab_settings_file_is_redirected_away_from_real_data_dir() -> None:
    # `config.DATA_DIR` is itself a per-test tmp path (KCH-231 review 1, item
    # 1c) -- if `settings_tab`'s own bound `SETTINGS_FILE` were still the
    # REAL `src/Loan Manager/data/settings.json`, it would not sit under it.
    assert settings_tab.SETTINGS_FILE.is_relative_to(config.DATA_DIR)
    assert settings_tab.SETTINGS_FILE == config.SETTINGS_FILE


def test_settings_tab_data_dir_is_redirected() -> None:
    assert settings_tab.DATA_DIR == config.DATA_DIR


def test_csv_to_sqlite_data_dir_is_redirected() -> None:
    assert csv_to_sqlite.DATA_DIR == config.DATA_DIR
