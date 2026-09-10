"""main branch protection (KCH-86) -- acceptance is that the release flow
and the required protection ruleset are documented precisely enough to
apply verbatim, and that the two status-check names in that documentation
can't silently drift from what CI and the CodeRabbit gate actually
publish. Actually flipping the GitHub setting is a one-time repo-admin
action (same category as `gh auth login` in ops/README.md) outside this
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


def _protection_contexts() -> list[str]:
    """Pull the required_status_checks.checks[].context values out of the
    documented `gh api .../protection` heredoc, rather than substring-matching
    the surrounding prose (which happens to repeat both status-check names).

    The heredoc interpolates $GH_ACTIONS_APP_ID (it's `<<JSON`, not the
    quoted `<<'JSON'`), so it isn't standalone JSON and can't be
    `json.loads`-ed whole -- extract the context strings directly instead."""
    match = re.search(r"<<JSON\n(.*?)\nJSON\n", _contract_text(), re.DOTALL)
    assert match, (
        "could not find the required_status_checks heredoc block in "
        "docs/AGENT_CONTRACT.md"
    )
    contexts = re.findall(r'"context":\s*"([^"]+)"', match.group(1))
    assert contexts, "no checks[].context entries found in the heredoc block"
    return contexts


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
    assert '"allow_deletions": false' in text


def test_documented_status_check_matches_ci_job_name() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    job_name = workflow["jobs"]["fast-gates"]["name"]
    assert job_name in _protection_contexts(), (
        "docs/AGENT_CONTRACT.md's required_status_checks.checks must "
        f"name the fast-gates job as it actually reports: {job_name!r}"
    )


def test_documented_status_check_matches_gate_context() -> None:
    match = re.search(
        r'GATE_CONTEXT="\$\{GATE_CONTEXT:-([^}]+)\}"', PR_GATE.read_text()
    )
    assert match, "could not find GATE_CONTEXT default in ops/pr_gate.sh"
    gate_context = match.group(1)
    assert gate_context in _protection_contexts(), (
        "docs/AGENT_CONTRACT.md's required_status_checks.checks must "
        "name the CLI gate context as ops/pr_gate.sh actually publishes "
        f"it: {gate_context!r}"
    )


def test_documented_ruleset_binds_fast_gates_to_actions_app() -> None:
    """The Fast gates context must be bound to an app_id (resolved from the
    live GitHub Actions app, not hardcoded) so a same-named context from an
    unrelated app can't satisfy the required check."""
    text = _contract_text()
    assert 'GH_ACTIONS_APP_ID="$(gh api apps/github-actions' in text
    assert '"context": "Fast gates", "app_id": $GH_ACTIONS_APP_ID' in text
