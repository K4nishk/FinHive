"""The developer agent operating contract (KCH-80) — acceptance is that it exists
and is referenced from CLAUDE.md, so that's what this asserts, not prose content.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "AGENT_CONTRACT.md"


def test_agent_contract_exists() -> None:
    assert CONTRACT.is_file()


def test_agent_contract_is_referenced_from_claude_md() -> None:
    claude_md = (ROOT / "CLAUDE.md").read_text()
    assert "docs/AGENT_CONTRACT.md" in claude_md


def test_agent_contract_covers_the_ard_18_loop() -> None:
    text = CONTRACT.read_text()
    required = [
        "development",
        "CodeRabbit",
        "two",
        "escalat",
    ]
    missing = [term for term in required if term.lower() not in text.lower()]
    assert not missing, f"contract is missing coverage of: {missing}"
