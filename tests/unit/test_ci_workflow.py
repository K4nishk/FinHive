"""The fast gate tier (KCH-82) — acceptance is that ci.yml exists, runs the required
gates in cheapest-first order as one job (so a failure stops the job instead of racing
independent jobs), and is budgeted to fail fast. Not a YAML schema check.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# Order matters: this must match the cheapest-first order asserted below.
GATE_RUN_MARKERS = ["ruff check", "mypy --strict", "prettier --check", "npm run lint"]


def _fast_gates_job() -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    return workflow["jobs"]["fast-gates"]


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


def test_no_gate_step_swallows_its_own_failure() -> None:
    """A `continue-on-error: true` step would let a cheap gate fail silently and
    let the job carry on to later, more expensive checks -- exactly the loophole
    that makes text-position checks pass even when a gate is toothless.
    """
    job = _fast_gates_job()
    offenders = [
        step.get("name", step.get("uses", "<unnamed>"))
        for step in job["steps"]
        if step.get("continue-on-error")
    ]
    assert not offenders, f"continue-on-error swallows a gate failure in: {offenders}"


def test_lint_failure_stops_the_job_before_later_gates(tmp_path: Path) -> None:
    """Actually run the fast-gate commands, in order, against a deliberately
    broken ruff target and prove the job stops there: later gate commands never
    execute, and the whole thing fails well inside the tier's 30s fail-fast
    budget rather than the full 2-minute job timeout.
    """
    job = _fast_gates_job()
    run_by_marker = {
        marker: step["run"]
        for step in job["steps"]
        if "run" in step
        for marker in GATE_RUN_MARKERS
        if marker in step["run"]
    }
    assert list(run_by_marker) == GATE_RUN_MARKERS, "fast-gates run steps changed shape"

    workspace = tmp_path / "workspace"
    (workspace / "finhive").mkdir(parents=True)
    (workspace / "tests").mkdir()
    (workspace / "finhive" / "__init__.py").write_text("")
    (workspace / "tests" / "__init__.py").write_text("")
    # An unused import trips ruff's F401 by default -- a deliberate lint failure.
    (workspace / "finhive" / "_deliberately_broken.py").write_text("import os\n")

    markers = tmp_path / "markers"
    markers.mkdir()
    commands = [run_by_marker[marker] for marker in GATE_RUN_MARKERS]
    script = " && ".join(f"{cmd} && touch {markers}/{i}.done" for i, cmd in enumerate(commands))

    started = time.monotonic()
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=30,
    )
    elapsed = time.monotonic() - started

    assert result.returncode != 0, "expected the deliberately broken ruff target to fail the job"
    assert list(markers.iterdir()) == [], "a later gate ran after the lint failure"
    assert elapsed < 30, f"fast-gate short-circuit took {elapsed:.1f}s, over the 30s budget"
