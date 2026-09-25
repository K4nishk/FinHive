"""This repository is public, and the Loan Manager writes plaintext NPI under
src/Loan Manager/data/: Settings -> Export CSV/XLSX, legacy CSV imports and their
.bak copies, backups, logs and the approval recovery file. The encrypted database
was ignored on 2026-09-25; these must be too, or one `git add` publishes the loan
book in clear. settings.json is the one file there that belongs in git.

The patterns are checked in a throwaway repository that holds only this repo's
.gitignore, with core.excludesFile disabled. A developer's global excludes or
.git/info/exclude therefore cannot make a wrong .gitignore look right, and the
answer does not depend on which files exist in this checkout.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA = "src/Loan Manager/data"

PLAINTEXT_OUTPUTS = [
    f"{DATA}/loans.db",
    f"{DATA}/demo.db",
    f"{DATA}/loans.db.pre-encryption-backup",
    f"{DATA}/exports/loans_export_20260925_000000.csv",
    f"{DATA}/exports/loans_export_20260925_000000.xlsx",
    f"{DATA}/loans.csv",
    f"{DATA}/loans.csv.bak",
    f"{DATA}/history.csv",
    f"{DATA}/backups/loans_backup_1.db",
    f"{DATA}/logs/app.log",
    f"{DATA}/approval_recovery.tmp",
]


@pytest.fixture(scope="module")
def gitignore_only(tmp_path_factory: pytest.TempPathFactory) -> Path:
    repo = tmp_path_factory.mktemp("gitignore_only")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    shutil.copy(ROOT / ".gitignore", repo / ".gitignore")
    return repo


def _ignored(repo: Path, path: str) -> bool:
    r = subprocess.run(
        ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "--no-index", "-q", path],
        cwd=repo,
    )
    assert r.returncode in (0, 1), f"git check-ignore failed on {path}"
    return r.returncode == 0


def test_plaintext_app_output_under_data_is_ignored(gitignore_only: Path) -> None:
    exposed = [p for p in PLAINTEXT_OUTPUTS if not _ignored(gitignore_only, p)]
    assert not exposed, f"committable plaintext NPI paths in a public repo: {exposed}"


def test_settings_json_is_not_ignored(gitignore_only: Path) -> None:
    assert not _ignored(gitignore_only, f"{DATA}/settings.json"), (
        "data/settings.json is ignored -- edits to it would silently stop reaching git"
    )


def test_settings_json_is_tracked() -> None:
    r = subprocess.run(["git", "ls-files", "--error-unmatch", f"{DATA}/settings.json"],
                       cwd=ROOT, capture_output=True)
    assert r.returncode == 0, "data/settings.json must stay tracked"
