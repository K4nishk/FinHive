"""main branch protection (KCH-86) -- acceptance is that the release flow
and the required protection ruleset are documented precisely enough to
apply verbatim, and that the two status-check names in that documentation
can't silently drift from what CI actually
publish. Actually flipping the GitHub setting is a one-time repo-admin
action outside this
suite's reach -- these tests pin the paper trail, not live GitHub state.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "AGENT_CONTRACT.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


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


def test_documented_status_check_matches_mvp1_regression_job_name() -> None:
    """KCH-88: the MVP1 regression gate must be one of the documented required
    checks, and its documented name must match the job's actual CI display name."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    job_name = workflow["jobs"]["mvp1-regression"]["name"]
    assert job_name in _protection_contexts(), (
        "docs/AGENT_CONTRACT.md's required_status_checks.checks must "
        f"name the mvp1-regression job as it actually reports: {job_name!r}"
    )


def test_mvp1_regression_job_runs_on_every_pr_path() -> None:
    """KCH-88 acceptance: a deliberate break in MVP1 domain code must block an
    unrelated MVP2 PR, so neither the workflow trigger nor the job itself may be
    gated behind a paths filter."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    # PyYAML parses the unquoted `on:` key as the boolean True (YAML 1.1), not
    # the string "on" -- look it up accordingly rather than via workflow["on"].
    triggers = workflow[True]
    pull_request_trigger = triggers["pull_request"]
    assert not pull_request_trigger or "paths" not in pull_request_trigger, (
        "the pull_request trigger must not filter by paths -- mvp1-regression has "
        "to run on every PR regardless of which files changed"
    )
    job = workflow["jobs"]["mvp1-regression"]
    assert "if" not in job, (
        "mvp1-regression must not be conditioned on changed paths -- it has to "
        "run on every PR regardless of which files changed"
    )


def test_documented_ruleset_does_not_require_the_retired_cli_gate() -> None:
    """CodeRabbit was removed on 2026-09-25. Only ops/pr_gate.sh (deleted 2026-09-25) running the
    CodeRabbit CLI ever published `coderabbit/cli-gate`, so nothing reports that
    context any more, and a ruleset requiring it blocks every merge indefinitely.

    This test used to REQUIRE the context, asserting it matched pr_gate.sh's
    GATE_CONTEXT. That enforced the one entry that would brick merging if the
    documented command were applied verbatim, so it is inverted: the command
    stays safe to apply as written."""
    contexts = _protection_contexts()
    assert "coderabbit/cli-gate" not in contexts, (
        "docs/AGENT_CONTRACT.md's documented ruleset requires "
        "`coderabbit/cli-gate`, which nothing publishes since CodeRabbit was "
        f"removed -- applying it would block every merge. Contexts: {contexts}"
    )


def test_documented_ruleset_binds_fast_gates_to_actions_app() -> None:
    """The Fast gates context must be bound to an app_id (resolved from the
    live GitHub Actions app, not hardcoded) so a same-named context from an
    unrelated app can't satisfy the required check."""
    text = _contract_text()
    assert 'GH_ACTIONS_APP_ID="$(gh api apps/github-actions' in text
    assert '"context": "Fast gates", "app_id": $GH_ACTIONS_APP_ID' in text


def test_documented_ruleset_binds_mvp1_regression_to_actions_app() -> None:
    """Same binding requirement as Fast gates (KCH-88): MVP1 regression also
    runs as a GitHub Actions job, so it must be bound to the Actions app's id
    rather than left open to any app with a same-named status."""
    assert (
        '"context": "MVP1 regression", "app_id": $GH_ACTIONS_APP_ID'
        in _contract_text()
    )


def test_documented_status_check_matches_postgres_integration_job_name() -> None:
    """KCH-230: the integration lane must be among the documented required
    checks. It exists because migrations 0001-0005 shipped unrunnable while the
    tests that would have caught them never ran in CI -- a lane that can be
    red at merge time does not close that."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    job_name = workflow["jobs"]["postgres-integration"]["name"]
    assert job_name in _protection_contexts(), (
        "docs/AGENT_CONTRACT.md's required_status_checks.checks must "
        f"name the postgres-integration job as it actually reports: {job_name!r}"
    )
