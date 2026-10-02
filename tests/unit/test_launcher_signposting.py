"""Startup signposting: the repo has two apps and four launchers.

The repo-root `run_local_*` scripts launch the paused MVP2 *web* app (KCH-90)
and refuse to finish until KCH-91/94/102 land. The Loan Manager *desktop* app
(MVP1 / MVP1.1 Ask FinHive) launches from `src/Loan Manager/run_*`. A Windows
user testing MVP1.1 ran the root script, sat through a frontend install, and
got "KCH-90 is not fully satisfiable" with nothing pointing at the right one.
These tests pin the signposts that prevent that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB_LAUNCHERS = {
    ROOT / "run_local_windows.bat": r"src\Loan Manager\run_windows.bat",
    ROOT / "run_local_mac.sh": "src/Loan Manager/run_mac.sh",
}
_CASES = list(WEB_LAUNCHERS.items())
_IDS = [script.name for script, _ in _CASES]
DESKTOP_WINDOWS = ROOT / "src" / "Loan Manager" / "run_windows.bat"


def _executable_lines(script: Path) -> list[str]:
    """Lines the user actually sees run: comments stripped."""
    out = []
    for line in script.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("::", "REM ", "rem ", "#")):
            continue
        out.append(line)
    return out


@pytest.mark.parametrize("script,desktop", _CASES, ids=_IDS)
def test_web_launcher_names_the_desktop_app_before_installing_anything(
    script: Path, desktop: str
) -> None:
    lines = _executable_lines(script)
    first_install = next(i for i, line in enumerate(lines) if "Installing" in line)
    banner = [i for i, line in enumerate(lines[:first_install]) if desktop in line]
    assert banner, (
        f"{script.name} must tell the user, before its first install step, that the "
        f"Loan Manager desktop app is started with {desktop}"
    )


@pytest.mark.parametrize("script,desktop", _CASES, ids=_IDS)
def test_web_launcher_refusal_points_to_the_desktop_app(script: Path, desktop: str) -> None:
    lines = _executable_lines(script)
    start = next(i for i, line in enumerate(lines) if "KCH-90 is not fully satisfiable" in line)
    end = next(i for i in range(start, len(lines)) if "exit" in lines[i])
    assert any(desktop in line for line in lines[start:end]), (
        f"{script.name}'s KCH-90 refusal must point to {desktop}"
    )


def test_desktop_windows_launcher_points_to_the_mvp11_guide() -> None:
    text = DESKTOP_WINDOWS.read_text(encoding="utf-8")
    assert "AskFinHive_instructions.md" in text
    assert "LOCAL_SETUP_WINDOWS.md" not in text, (
        "LOCAL_SETUP_WINDOWS.md documents the MVP2 web app, not the desktop app"
    )


@pytest.mark.parametrize("script,desktop", _CASES, ids=_IDS)
def test_web_launcher_refuses_before_the_frontend_install(script: Path, desktop: str) -> None:
    """F-002: the refusal (and its desktop pointer) must not wait behind a slow
    `npm install` whose output scrolls the top-of-run banner off screen."""
    lines = _executable_lines(script)
    refusal = next(i for i, line in enumerate(lines) if "KCH-90 is not fully satisfiable" in line)
    npm_install = next(i for i, line in enumerate(lines) if "npm install" in line)
    assert refusal < npm_install, f"{script.name} runs npm install before its KCH-90 refusal"
