"""CI-blocking rule: no derived index of any kind on an amount column (KCH-96,
ADR-2.4).

ADR-2.4 states the hard rule in prose: "a blind index must NEVER be added to
an amount." A comment is not a rule -- nothing stops a future migration from
copy-pasting the identity-column `_bidx` pattern onto `amount` the same way
0003's own header comment warns against. This file is that rule made
mechanical: it statically scans every migration file (not just 0004) for a
`_bidx` column, or any `CREATE INDEX`, naming an amount column, and fails the
build if it finds one. `test_ci_runs_the_blind_index_lint_gate` below then
pins that this file is actually wired into `.github/workflows/ci.yml` as an
unconditional, non-swallowed step -- a rule nothing runs isn't a gate.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from finhive.db.blind_index import FORBIDDEN_BLIND_INDEX_COLUMNS
from finhive.db.migrations import discover_migrations

ROOT = Path(__file__).resolve().parents[2]
_MIGRATIONS_DIR = ROOT / "migrations"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# The exact, standalone invocation the gate requires.
_LINT_GATE_COMMAND = "pytest tests/unit/test_blind_index_lint.py -q"

# Matches `ADD COLUMN <name>_bidx` or a bare `<name>_bidx` reference (e.g.
# inside a CREATE INDEX target list), case-insensitively, for any amount
# column name -- catching both the column definition and an index built on
# a `_bidx` (or, more broadly, any indexed/derived-looking) amount column.
_BIDX_COLUMN_RE = re.compile(r"(\w+)_bidx\b", re.IGNORECASE)
_CREATE_INDEX_RE = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+\S+\s+ON\s+\S+\s*\(([^)]+)\)", re.IGNORECASE
)


def _all_migration_sql() -> dict[int, str]:
    return {m.version: m.sql for m in discover_migrations(_MIGRATIONS_DIR)}


def test_no_migration_adds_a_blind_index_on_an_amount_column() -> None:
    for version, sql in _all_migration_sql().items():
        for match in _BIDX_COLUMN_RE.finditer(sql):
            base_column = match.group(1).lower()
            assert base_column not in FORBIDDEN_BLIND_INDEX_COLUMNS, (
                f"migration {version:04d} adds a blind index on amount column "
                f"{base_column!r} -- ADR-2.4 forbids any derived index on an amount"
            )


def test_no_migration_creates_any_index_targeting_an_amount_column() -> None:
    """Broader than the `_bidx` check above: ADR-2.4 also forbids indexing an
    amount's ciphertext directly (which would still let a range or equality
    scan work at the database level, the exact consequence ADR-2.4 rules
    out) -- not only a dedicated blind-index column.
    """
    for version, sql in _all_migration_sql().items():
        for match in _CREATE_INDEX_RE.finditer(sql):
            target_columns = [c.strip().lower() for c in match.group(1).split(",")]
            for target in target_columns:
                for forbidden in FORBIDDEN_BLIND_INDEX_COLUMNS:
                    assert not target.startswith(forbidden), (
                        f"migration {version:04d} creates an index on {target!r} -- "
                        f"ADR-2.4 forbids any index (equality, range or sort) on the "
                        f"amount column {forbidden!r}"
                    )


def test_forbidden_columns_fixture_is_not_accidentally_empty() -> None:
    """A passing lint run must mean 'checked and clean', not 'checked
    nothing' -- guard against the allow-list silently losing every entry.
    """
    assert FORBIDDEN_BLIND_INDEX_COLUMNS


# ── the gate is wired into CI, not just present as a file ──────────────────


def _fast_gates_job() -> dict[str, Any]:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    return workflow["jobs"]["fast-gates"]


def test_ci_runs_the_blind_index_lint_gate() -> None:
    job = _fast_gates_job()
    assert job.get("if") is None, "fast-gates must run unconditionally for this gate to be real"
    assert not job.get("continue-on-error", False), "fast-gates must not tolerate failure"

    hits = [
        step
        for step in job["steps"]
        if step.get("run", "").strip() == _LINT_GATE_COMMAND
        and step.get("if") is None
        and not step.get("continue-on-error", False)
    ]
    assert hits, (
        f"no unconditional, non-swallowed step runs {_LINT_GATE_COMMAND!r} in fast-gates"
    )
