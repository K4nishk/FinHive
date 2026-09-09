"""CodeRabbit repo config (KCH-83) — acceptance is that .coderabbit.yaml exists,
declares path filters, restates CLAUDE.md conventions via path_instructions, and
sets the blocking/advisory split so opening a PR both triggers a review and lets a
high-severity finding block merge. Not a full schema check against CodeRabbit's
JSON schema (unreachable without network) -- see `coderabbit config validate`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".coderabbit.yaml"


def _load() -> dict:
    return yaml.safe_load(CONFIG.read_text())


def test_coderabbit_config_exists() -> None:
    assert CONFIG.is_file()


def test_coderabbit_config_is_valid_yaml() -> None:
    data = _load()
    assert isinstance(data, dict)
    assert "reviews" in data


def test_auto_review_triggers_on_pr_open() -> None:
    data = _load()
    assert data["reviews"]["auto_review"]["enabled"] is True


def test_blocking_findings_use_request_changes_workflow() -> None:
    """This is the mechanism that lets a high-severity finding block merge: CodeRabbit
    submits a GitHub "Request changes" review instead of a plain comment.
    """
    data = _load()
    assert data["reviews"]["request_changes_workflow"] is True


def test_path_filters_exclude_generated_and_vendored_paths() -> None:
    data = _load()
    filters = data["reviews"]["path_filters"]
    assert any("output/" in f for f in filters)
    assert any("node_modules" in f for f in filters)
    assert any(".lock" in f for f in filters)


def test_path_instructions_cover_each_architecture_layer() -> None:
    data = _load()
    paths = [entry["path"] for entry in data["reviews"]["path_instructions"]]
    for layer in ("domain", "application", "infrastructure", "presentation"):
        assert any(layer in p for p in paths), f"no path_instructions entry for {layer}"


def test_path_instructions_restate_key_business_rules() -> None:
    data = _load()
    combined = " ".join(entry["instructions"] for entry in data["reviews"]["path_instructions"])
    for term in ("giving_date", "Decimal", "QTableWidget", "raw SQL"):
        assert term in combined, f"path_instructions missing coverage of: {term}"
