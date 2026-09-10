"""The M1a local launcher contract (KCH-90).

Acceptance is "a clean machine reaches a working local app from a single
command on both operating systems" — not something a unit test can drive
directly (it needs a real Python/Node/Postgres environment). What's checked
here instead: the two launchers and their setup guides exist, the shell
script is syntactically valid and executable, both scripts mirror the MVP1
version-check convention (readable failure message, 3.10 floor), and both
cover every step the issue lists. That's the contract a reviewer or a later
ticket can hold the scripts to without running a full environment bring-up.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAC_SCRIPT = ROOT / "run_local_mac.sh"
WINDOWS_SCRIPT = ROOT / "run_local_windows.bat"
MAC_GUIDE = ROOT / "docs" / "LOCAL_SETUP_MACOS.md"
WINDOWS_GUIDE = ROOT / "docs" / "LOCAL_SETUP_WINDOWS.md"

# Every step the issue's acceptance criteria name, checked as a substring
# present in each script (case-insensitive markers for the concept, not
# literal commands, since mac/bat spell them differently).
REQUIRED_STEPS = [
    "python",
    "venv",
    "npm install",
    "migrat",
    "seed",
    "uvicorn",
    "npm run dev",
]


def test_launcher_scripts_exist() -> None:
    assert MAC_SCRIPT.is_file()
    assert WINDOWS_SCRIPT.is_file()


def test_setup_guides_exist() -> None:
    assert MAC_GUIDE.is_file()
    assert WINDOWS_GUIDE.is_file()


def test_mac_script_is_executable() -> None:
    assert MAC_SCRIPT.stat().st_mode & 0o111, "run_local_mac.sh must be chmod +x"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")
def test_mac_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(MAC_SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("script", [MAC_SCRIPT, WINDOWS_SCRIPT])
def test_scripts_cover_every_required_step(script: Path) -> None:
    text = script.read_text().lower()
    missing = [step for step in REQUIRED_STEPS if step not in text]
    assert not missing, f"{script.name} is missing coverage of: {missing}"


@pytest.mark.parametrize("script", [MAC_SCRIPT, WINDOWS_SCRIPT])
def test_scripts_mirror_mvp1_version_check_convention(script: Path) -> None:
    """MVP1's launchers (src/Loan Manager/run_mac.sh, run_windows.bat) fail
    with 'ERROR: Python 3.10 or higher is required' rather than a bare
    traceback. The issue asks these scripts to mirror that convention.
    """
    text = script.read_text()
    assert "3.10" in text
    assert "Python 3.10 or higher is required" in text


@pytest.mark.parametrize(
    "guide,script_name",
    [(MAC_GUIDE, "run_local_mac.sh"), (WINDOWS_GUIDE, "run_local_windows.bat")],
)
def test_setup_guide_references_its_script(guide: Path, script_name: str) -> None:
    assert script_name in guide.read_text()


def test_windows_script_is_a_batch_file_not_powershell() -> None:
    text = WINDOWS_SCRIPT.read_text()
    assert text.startswith("@echo off")
