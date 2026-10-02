"""Master key file: created on first launch, reused after (F-006).

A Windows tester set `FINHIVE_MASTER_KEY_V1` with `$env:` in one PowerShell
window. It lived only as long as that window, so the next launch was blocked
and data encrypted under the old key was unreadable. The app now keeps its
key in `data/encryption/master_key.key`, creating it when no key exists yet:

1. A key in the environment wins (existing macOS `ops/.env.local` users).
2. Otherwise the key file is used.
3. Otherwise a NEW key is created -- but never when a database it would be
   used for already holds encrypted data. A new key cannot read that data,
   and writing beside it under a second key is indistinguishable from loss.

Every test points the key file and the databases at `tmp_path`.
"""

from __future__ import annotations

import base64
import os
import stat
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from loan_manager.infrastructure.security.key_provider import (
    KeyConfigurationError,
    load_or_create_keys,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_KEY_A = base64.b64encode(b"A" * 32).decode()
_KEY_B = base64.b64encode(b"B" * 32).decode()


def _env_key(value: str = _KEY_A) -> dict[str, str]:
    return {"FINHIVE_KEY_VERSION": "1", "FINHIVE_MASTER_KEY_V1": value}


def _write_key_file(path: Path, value: str = _KEY_A) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# comment\nFINHIVE_KEY_VERSION=1\nFINHIVE_MASTER_KEY_V1={value}\n",
        encoding="utf-8",
    )


def _encrypted_db(path: Path) -> Path:
    """A database holding one encrypted loan row, written through the ORM's
    encrypting column types (the autouse test key ring is active)."""
    from loan_manager.infrastructure.database.models import Base, LoanModel

    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    now = datetime(2026, 1, 1)
    with sessionmaker(bind=engine)() as session:
        session.add(
            LoanModel(
                reference_id="2026_01_001",
                borrower_name="rakesh sharma",
                borrower_group="sharma group",
                depositor_name="arjun rao",
                depositor_group="rao",
                amount=250000,
                giving_date=date(2026, 1, 1),
                due_date=date(2026, 7, 1),
                status="Active",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    engine.dispose()
    return path


def _empty_db(path: Path) -> Path:
    from loan_manager.infrastructure.database.models import Base

    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    return path


# ── precedence ──────────────────────────────────────────────────────────────


def test_environment_key_wins_and_no_file_is_created(tmp_path: Path) -> None:
    key_file = tmp_path / "encryption" / "master_key.key"
    ring = load_or_create_keys(env=_env_key(), key_file=key_file, db_paths=[])
    assert ring.current_version == 1
    assert not key_file.exists()


def test_key_file_is_used_when_the_environment_has_no_key(tmp_path: Path) -> None:
    key_file = tmp_path / "encryption" / "master_key.key"
    _write_key_file(key_file, _KEY_B)
    from_file = load_or_create_keys(env={}, key_file=key_file, db_paths=[])
    from_env = load_or_create_keys(env=_env_key(_KEY_B), key_file=tmp_path / "x", db_paths=[])
    assert from_file.key_data() == from_env.key_data()


def test_env_and_file_with_different_keys_for_one_version_refuse(tmp_path: Path) -> None:
    """Two different masters both called V1 would leave rows written under
    one unreadable under the other. Refuse rather than pick one."""
    key_file = tmp_path / "master_key.key"
    _write_key_file(key_file, _KEY_A)
    with pytest.raises(KeyConfigurationError, match="two different"):
        load_or_create_keys(env=_env_key(_KEY_B), key_file=key_file, db_paths=[])


def test_env_and_file_with_the_same_key_are_fine(tmp_path: Path) -> None:
    key_file = tmp_path / "master_key.key"
    _write_key_file(key_file, _KEY_A)
    ring = load_or_create_keys(env=_env_key(_KEY_A), key_file=key_file, db_paths=[])
    assert ring.current_version == 1


def test_key_file_tolerates_export_quotes_and_a_notepad_bom(tmp_path: Path) -> None:
    key_file = tmp_path / "master_key.key"
    key_file.write_text(
        f'﻿export FINHIVE_KEY_VERSION=1\r\nexport FINHIVE_MASTER_KEY_V1="{_KEY_A}"\r\n',
        encoding="utf-8",
    )
    ring = load_or_create_keys(env={}, key_file=key_file, db_paths=[])
    assert ring.key_data() == load_or_create_keys(
        env=_env_key(_KEY_A), key_file=tmp_path / "x", db_paths=[]
    ).key_data()


def test_a_damaged_key_file_names_the_file_and_never_echoes_its_contents(tmp_path: Path) -> None:
    key_file = tmp_path / "master_key.key"
    key_file.write_text("FINHIVE_KEY_VERSION=1\nFINHIVE_MASTER_KEY_V1=not-base64!!\n")
    with pytest.raises(KeyConfigurationError) as excinfo:
        load_or_create_keys(env={}, key_file=key_file, db_paths=[])
    assert str(key_file) in str(excinfo.value)
    assert "not-base64!!" not in str(excinfo.value)
    # and a damaged file is never replaced by a fresh key
    assert "not-base64!!" in key_file.read_text()


# ── creation ────────────────────────────────────────────────────────────────


def test_creates_a_key_file_when_there_is_no_key_and_no_encrypted_data(
    tmp_path: Path, capsys
) -> None:
    key_file = tmp_path / "data" / "encryption" / "master_key.key"
    db = _empty_db(tmp_path / "loans.db")

    ring = load_or_create_keys(env={}, key_file=key_file, db_paths=[db, tmp_path / "missing.db"])

    assert key_file.is_file()
    assert ring.current_version == 1
    # the next launch reads the same key back
    again = load_or_create_keys(env={}, key_file=key_file, db_paths=[db])
    assert again.key_data() == ring.key_data()
    # the person is told where it is and to back it up
    err = capsys.readouterr().err
    assert str(key_file) in err
    assert "back" in err.lower()


def test_each_created_key_is_random(tmp_path: Path) -> None:
    a = load_or_create_keys(env={}, key_file=tmp_path / "a" / "k.key", db_paths=[])
    b = load_or_create_keys(env={}, key_file=tmp_path / "b" / "k.key", db_paths=[])
    assert a.key_data() != b.key_data()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_created_key_file_is_readable_by_the_owner_only(tmp_path: Path) -> None:
    key_file = tmp_path / "encryption" / "master_key.key"
    load_or_create_keys(env={}, key_file=key_file, db_paths=[])
    assert stat.S_IMODE(os.stat(key_file).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(key_file.parent).st_mode) == 0o700


def test_no_temporary_file_is_left_beside_the_key(tmp_path: Path) -> None:
    key_file = tmp_path / "encryption" / "master_key.key"
    load_or_create_keys(env={}, key_file=key_file, db_paths=[])
    assert sorted(p.name for p in key_file.parent.iterdir()) == ["master_key.key"]


# ── the one refusal: encrypted data, no key ─────────────────────────────────


def test_refuses_to_create_a_key_when_a_database_already_holds_encrypted_data(
    tmp_path: Path,
) -> None:
    key_file = tmp_path / "encryption" / "master_key.key"
    db = _encrypted_db(tmp_path / "demo.db")

    with pytest.raises(KeyConfigurationError) as excinfo:
        load_or_create_keys(env={}, key_file=key_file, db_paths=[db])

    assert not key_file.exists()
    msg = str(excinfo.value)
    assert str(db) in msg
    assert str(key_file) in msg  # where to restore the key to
    assert "demo-reset" in msg  # the way out for the synthetic demo ledger


def test_plaintext_mvp1_database_does_not_block_creation(tmp_path: Path) -> None:
    """An MVP1 ledger has no `_ct` columns: no key has ever encrypted it, so
    creating one is safe -- and the migration needs one."""
    import sqlite3

    db = tmp_path / "mvp1.db"
    # Schema only, no rows: the MVP1 column layout is what is under test.
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE loans (id INTEGER PRIMARY KEY, borrower_name TEXT)")
    conn.commit()
    conn.close()
    key_file = tmp_path / "master_key.key"

    load_or_create_keys(env={}, key_file=key_file, db_paths=[db])

    assert key_file.exists()


def test_checking_a_missing_database_does_not_create_it(tmp_path: Path) -> None:
    missing = tmp_path / "nowhere" / "loans.db"
    load_or_create_keys(env={}, key_file=tmp_path / "k.key", db_paths=[missing])
    assert not missing.exists()
    assert not missing.parent.exists()


# ── wiring ──────────────────────────────────────────────────────────────────


def test_container_creates_the_key_file_at_the_configured_path(
    tmp_path: Path, monkeypatch
) -> None:
    from loan_manager import config
    from loan_manager.container import Container

    for name in list(os.environ):
        if name.startswith("FINHIVE_KEY_VERSION") or name.startswith("FINHIVE_MASTER_KEY_V"):
            monkeypatch.delenv(name)
    key_file = tmp_path / "encryption" / "master_key.key"
    monkeypatch.setattr(config, "KEY_FILE", key_file)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "loans.db")

    Container().get_key_ring()

    assert key_file.is_file()


def test_default_key_file_lives_under_data_encryption_and_is_git_ignored() -> None:
    from loan_manager import config

    assert config.KEY_FILE == config.DATA_DIR / "encryption" / "master_key.key"
    gitignore = (Path(__file__).resolve().parents[4] / ".gitignore").read_text()
    assert "/src/Loan Manager/data/*" in gitignore
