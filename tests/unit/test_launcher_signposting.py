"""Startup contract for the four launchers (F-001, F-002, F-003).

The desktop app (MVP1 / MVP1.1 Ask FinHive) is the product people test, so:

- the repo-root `run_local_windows.bat` / `run_local_mac.sh` start the desktop
  app by default, passing their arguments through; the paused MVP2 web flow
  sits behind `--web`;
- the desktop launchers take `demo` / `demo-reset`, which seed a demo ledger
  outside `data/` with the launcher's own venv Python and launch on it -- no
  manual venv activation, no `python` vs `python3`, no Windows env var that
  only reaches the window it was set in (F-003: a Mac user's seed command ran
  on the system python3 and failed with `No module named 'sqlalchemy'`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src" / "Loan Manager"
ROOT_LAUNCHERS = {
    ROOT / "run_local_windows.bat": "run_windows.bat",
    ROOT / "run_local_mac.sh": "run_mac.sh",
}
DESKTOP_LAUNCHERS = [APP / "run_windows.bat", APP / "run_mac.sh"]
_CASES = list(ROOT_LAUNCHERS.items())
_IDS = [script.name for script, _ in _CASES]


def _executable_lines(script: Path) -> list[str]:
    """Lines that run: comments stripped."""
    out = []
    for line in script.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("::", "REM ", "rem ", "#")):
            continue
        out.append(line)
    return out


def _first(lines: list[str], needle: str) -> int:
    return next(i for i, line in enumerate(lines) if needle in line)


@pytest.mark.parametrize("script,desktop", _CASES, ids=_IDS)
def test_root_launcher_starts_the_desktop_app_by_default(script: Path, desktop: str) -> None:
    lines = _executable_lines(script)
    handoff = [i for i, line in enumerate(lines) if desktop in line and "echo" not in line]
    assert handoff, f"{script.name} must hand off to src/Loan Manager/{desktop} by default"
    assert handoff[0] < _first(lines, "Installing"), (
        f"{script.name} must hand off before installing anything for the web app"
    )


@pytest.mark.parametrize("script,desktop", _CASES, ids=_IDS)
def test_root_launcher_keeps_the_web_flow_behind_a_flag(script: Path, desktop: str) -> None:
    lines = _executable_lines(script)
    assert any("--web" in line for line in lines[: _first(lines, "Installing")]), (
        f"{script.name} must keep the MVP2 web flow reachable with --web"
    )


@pytest.mark.parametrize("script,desktop", _CASES, ids=_IDS)
def test_web_refusal_comes_before_the_frontend_install(script: Path, desktop: str) -> None:
    """F-002: a refusal must not wait behind a slow npm install."""
    lines = _executable_lines(script)
    assert _first(lines, "KCH-90 is not fully satisfiable") < _first(lines, "npm install")


@pytest.mark.parametrize("script", DESKTOP_LAUNCHERS, ids=lambda p: p.name)
def test_desktop_launcher_has_a_demo_mode_that_seeds_with_its_own_python(script: Path) -> None:
    lines = _executable_lines(script)
    text = "\n".join(lines)
    assert "demo-reset" in text and "FINHIVE_DB_PATH" in text, (
        f"{script.name} must accept demo / demo-reset and point FINHIVE_DB_PATH at the demo ledger"
    )
    seed = _first(lines, "loan_manager.infrastructure.seed")
    launch = _first(lines, "loan_manager.main")
    assert seed < launch, f"{script.name} must seed before launching"
    assert "--replace" in lines[seed], f"{script.name}: demo-reset must reseed with --replace"


def test_desktop_windows_launcher_points_to_the_mvp11_guide() -> None:
    text = (APP / "run_windows.bat").read_text(encoding="utf-8")
    assert "AskFinHive_instructions.md" in text
    assert "LOCAL_SETUP_WINDOWS.md" not in text


@pytest.mark.parametrize("script", DESKTOP_LAUNCHERS, ids=lambda p: p.name)
def test_desktop_launcher_names_the_key_file_instead_of_blocking(script: Path) -> None:
    """F-006: the key is created by the app on first launch; the launcher
    says where it lives instead of warning that the app will refuse."""
    text = "\n".join(_executable_lines(script))
    assert "master_key.key" in text.replace("\\", "/"), f"{script.name} must name the key file"
    assert "will refuse to start" not in text
