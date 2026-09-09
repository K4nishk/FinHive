"""main branch protection (KCH-86) -- acceptance is that the release flow and the
required protection ruleset are documented precisely enough to apply verbatim, and that
the two status-check names in that documentation can't silently drift from what CI and
the CodeRabbit gate actually publish. Actually flipping the GitHub setting is a one-time
repo-admin action (same category as `gh auth login` in ops/README.md) outside this
suite's reach -- these tests pin the paper trail, not live GitHub state.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "AGENT_CONTRACT.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PR_GATE = ROOT / "ops" / "pr_gate.sh"


def _contract_text() -> str:
    return CONTRACT.read_text()


def test_branch_protection_section_exists() -> None:
    assert "## Branch protection" in _contract_text()


def test_release_flow_is_documented() -> None:
    text = _contract_text().lower()
    required = ["development", "main", "release pr", "always-deployable"]
    missing = [term for term in required if term not in text]
    assert not missing, f"release flow doc is missing coverage of: {missing}"


def test_documented_ruleset_requires_one_human_approval() -> None:
    assert '"required_approving_review_count": 1' in _contract_text()


def test_documented_ruleset_blocks_direct_pushes() -> None:
    text = _contract_text()
    assert '"enforce_admins": true' in text
    assert '"allow_force_pushes": false' in text


def test_documented_status_check_matches_ci_job_name() -> None:
    job_name = yaml.safe_load(WORKFLOW.read_text())["jobs"]["fast-gates"]["name"]
    assert f'"{job_name}"' in _contract_text(), (
        f"docs/AGENT_CONTRACT.md's required_status_checks must name the fast-gates "
        f"job as it actually reports: {job_name!r}"
    )


def test_documented_status_check_matches_gate_context() -> None:
    match = re.search(r'GATE_CONTEXT="\$\{GATE_CONTEXT:-([^}]+)\}"', PR_GATE.read_text())
    assert match, "could not find GATE_CONTEXT default in ops/pr_gate.sh"
    gate_context = match.group(1)
    assert f'"{gate_context}"' in _contract_text(), (
        f"docs/AGENT_CONTRACT.md's required_status_checks must name the CLI gate "
        f"context as ops/pr_gate.sh actually publishes it: {gate_context!r}"
    )
