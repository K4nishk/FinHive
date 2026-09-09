"""The fast gate tier (KCH-82) — acceptance is that ci.yml exists, runs the required
gates in cheapest-first order as one job (so a failure stops the job instead of racing
independent jobs), and is budgeted to fail fast. Not a YAML schema check.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_ci_workflow_runs_on_pull_request() -> None:
    text = WORKFLOW.read_text()
    assert "pull_request" in text


def test_ci_workflow_is_budgeted_under_two_minutes() -> None:
    text = WORKFLOW.read_text()
    assert "timeout-minutes: 2" in text


def test_fast_gates_run_cheapest_first_in_one_job() -> None:
    """Issue order: ruff, mypy --strict on domain/calc, prettier, eslint, gitleaks.

    One job with sequential steps (not parallel jobs) so a ruff failure stops the
    job immediately rather than waiting on prettier/eslint/gitleaks to finish too.
    """
    text = WORKFLOW.read_text()
    gates = [
        "ruff check",
        "mypy --strict",
        "prettier --check",
        "npm run lint",
        "uses: gitleaks",
    ]
    positions = [text.index(gate) for gate in gates]
    assert positions == sorted(positions), "gates are not ordered cheapest-first"


def test_mypy_strict_targets_domain_and_calc() -> None:
    text = WORKFLOW.read_text()
    assert "mypy --strict finhive/domain finhive/calc" in text
