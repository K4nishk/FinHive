"""KCH-241 presentation hygiene, by static scan of the files this issue adds or
edits: no hard-coded hex, no QTableWidget, no persistence imports."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PRESENTATION = Path(__file__).resolve().parents[3] / "loan_manager" / "presentation"
NEW_FILES = [
    PRESENTATION / "widgets" / "trace_model.py",
    PRESENTATION / "workers" / "agent_worker.py",
    PRESENTATION / "workers" / "__init__.py",
    PRESENTATION / "tabs" / "ask_finhive_tab.py",
]
TOUCHED_FILES = [PRESENTATION / "themes" / "theme_manager.py",
                 PRESENTATION / "main_window.py"]
HEX = re.compile(r"""["']#[0-9a-fA-F]{3,8}["']""")
FORBIDDEN_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+(?:sqlalchemy|loan_manager\.infrastructure\.(?:repositories|database))",
    re.MULTILINE,
)


@pytest.mark.parametrize("path", NEW_FILES + TOUCHED_FILES, ids=lambda p: p.name)
def test_no_hard_coded_hex_colour(path: Path) -> None:
    hits = [m.group(0) for m in HEX.finditer(path.read_text())]
    # theme_manager.py's pre-existing status fallback is not this issue's code
    if path.name == "theme_manager.py":
        hits = [h for h in hits if h not in ('"#888888"', '"#ffffff"')]
    assert not hits, f"{path.name} hard-codes a colour: {hits}"


@pytest.mark.parametrize("path", NEW_FILES + TOUCHED_FILES, ids=lambda p: p.name)
def test_no_table_widget_and_no_persistence_imports(path: Path) -> None:
    source = path.read_text()
    assert "QTableWidget" not in source
    assert not FORBIDDEN_IMPORT.findall(source), f"{path.name} imports persistence"


def test_presentation_never_imports_the_llm_infrastructure() -> None:
    llm_import = re.compile(
        r"^\s*(?:from|import)\s+loan_manager\.infrastructure\.llm", re.MULTILINE
    )
    offenders = [
        str(p.relative_to(PRESENTATION))
        for p in PRESENTATION.rglob("*.py")
        if llm_import.search(p.read_text())
    ]
    assert offenders == []
