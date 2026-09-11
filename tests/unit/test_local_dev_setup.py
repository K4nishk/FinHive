"""The M1a local launcher contract (KCH-90).

Acceptance is "a clean machine reaches a working local app from a single
command on both operating systems" — not something most of these tests can
drive directly (it needs a real Python/Node/Postgres environment). Most of
what's checked here is structural: the two launchers and their setup guides
exist, the shell script is syntactically valid and executable, both scripts
mirror the MVP1 version-check convention (readable failure message, 3.10
floor), and both at least mention every step the issue lists. That
substring check is a floor, not KCH-90 acceptance evidence — it would pass
just as happily if a step appeared only in a comment or a skip notice.
The one test that actually exercises the launcher end-to-end,
``test_mac_launcher_brings_up_a_reachable_spa``, is opt-in (see
FINHIVE_LOCAL_SETUP_INTEGRATION below) because it needs Node, and either a
reachable database or a container runtime, to actually run the app.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAC_SCRIPT = ROOT / "run_local_mac.sh"
WINDOWS_SCRIPT = ROOT / "run_local_windows.bat"
MAC_GUIDE = ROOT / "docs" / "LOCAL_SETUP_MACOS.md"
WINDOWS_GUIDE = ROOT / "docs" / "LOCAL_SETUP_WINDOWS.md"

RUN_INTEGRATION = os.environ.get("FINHIVE_LOCAL_SETUP_INTEGRATION") == "1"

# Every step the issue's acceptance criteria name, checked as a substring
# present in each script (case-insensitive markers for the concept, not
# literal commands, since mac/bat spell them differently). This only proves
# the step is mentioned somewhere — see the module docstring.
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
    assert MAC_SCRIPT.stat().st_mode & 0o111, (
        "run_local_mac.sh must be chmod +x"
    )


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
    [
        (MAC_GUIDE, "run_local_mac.sh"),
        (WINDOWS_GUIDE, "run_local_windows.bat"),
    ],
)
def test_setup_guide_references_its_script(
    guide: Path, script_name: str,
) -> None:
    assert script_name in guide.read_text()


def test_windows_script_is_a_batch_file_not_powershell() -> None:
    text = WINDOWS_SCRIPT.read_text()
    assert text.startswith("@echo off")


def _port_is_open(host: str, port: int) -> bool:
    with contextlib.closing(
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


def _spa_responds(host: str, port: int) -> bool:
    """True only if something at host:port actually serves HTTP, not just
    accepts a TCP connection -- an unrelated process squatting on the port
    would satisfy `_port_is_open` but not this.
    """
    try:
        url = f"http://{host}:{port}/"
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


@pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason=(
        "opt-in: set FINHIVE_LOCAL_SETUP_INTEGRATION=1 to actually launch "
        "run_local_mac.sh and verify the SPA serves real traffic. Requires "
        "Python 3.10+, Node 20+, and either DATABASE_URL or a running "
        "Supabase CLI plus a container runtime."
    ),
)
def test_mac_launcher_brings_up_a_reachable_spa() -> None:
    if _port_is_open("127.0.0.1", 5173):
        pytest.fail(
            "port 5173 is already occupied before launch -- this test "
            "cannot tell the launcher's SPA apart from whatever else is "
            "listening; free the port and re-run"
        )
    proc = subprocess.Popen(
        ["bash", str(MAC_SCRIPT), "--allow-partial"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 300
        spa_up = False
        while time.monotonic() < deadline:
            if _spa_responds("127.0.0.1", 5173):
                spa_up = True
                break
            if proc.poll() is not None:
                pytest.fail(
                    "launcher exited before the SPA "
                    f"came up:\n{proc.stdout.read()}"
                )
            time.sleep(1)
        assert spa_up, (
            "SPA did not serve an HTTP response on "
            ":5173 within 300s"
        )
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            with contextlib.suppress(
                subprocess.TimeoutExpired,
            ):
                proc.wait(timeout=10)
