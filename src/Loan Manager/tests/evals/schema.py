"""Eval case file format (KCH-248): one JSON object per line.

Authored keys (a human writes and reviews these):
  id, suite, question, frozen_today (ISO date), expected_trace (ordered
  subsequence of ACTION tool names), expected_entity ({"slug": s} XOR
  {"ambiguous": [a, b]} -- authored, never generated: generating it with the
  resolver under test would be circular), focus ({entity, metric, period}),
  must_not_call (tool names that must never appear), where (optional; INPUT to
  `gen_expected` only: {"borrower_group"?, "depositor_group"?, "status"?}, the
  same filter the case's `query_loans` call is expected to make).

Generated keys (`python -m tests.evals.gen_expected` writes them; never hand
edit): expected_ref_ids (sorted ref_ids), expected_facts ({count, total_amount
as a 2dp Decimal string, overdue_undated}). Derived from the fixture and
`StatusEngine` at `frozen_today`, so a fixture edit re-derives them.

`validate` reports every problem as a string; it never raises, so a bad file
lists all of its errors in one run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

AUTHORED_KEYS: tuple[str, ...] = (
    "id",
    "suite",
    "question",
    "frozen_today",
    "expected_trace",
    "expected_entity",
    "focus",
    "must_not_call",
)
OPTIONAL_KEYS: tuple[str, ...] = ("where",)
GENERATED_KEYS: tuple[str, ...] = ("expected_ref_ids", "expected_facts")
# Canonical on-disk key order: `gen_expected` rewrites files in this order.
KEY_ORDER: tuple[str, ...] = AUTHORED_KEYS + OPTIONAL_KEYS + GENERATED_KEYS
ALLOWED_KEYS = frozenset(KEY_ORDER)
FOCUS_KEYS = frozenset({"entity", "metric", "period"})
WHERE_KEYS = frozenset({"borrower_group", "depositor_group", "status"})
FACT_KEYS = frozenset({"count", "total_amount", "overdue_undated"})

CASES_DIR = Path(__file__).parent / "cases"


class CaseFileError(ValueError):
    """A case file with one or more invalid rows."""


@dataclass(frozen=True)
class Case:
    id: str
    suite: str
    question: str
    frozen_today: date
    expected_trace: tuple[str, ...]
    expected_entity: dict[str, Any]
    focus: dict[str, Any]
    must_not_call: tuple[str, ...]
    where: dict[str, Any] | None = None
    expected_ref_ids: tuple[str, ...] | None = None
    expected_facts: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def validate(row: Any) -> list[str]:
    """Every problem with one decoded row, as `key: reason` strings."""
    if not isinstance(row, dict):
        return ["row is not a JSON object"]
    errors: list[str] = []
    for key in row:
        if key not in ALLOWED_KEYS:
            errors.append(f"{key}: unknown key")
    for key in AUTHORED_KEYS:
        if key not in row:
            errors.append(f"{key}: missing key")
    for key in ("id", "suite", "question"):
        if key in row and not (isinstance(row[key], str) and row[key].strip()):
            errors.append(f"{key}: must be a non-empty string")
    if "frozen_today" in row:
        try:
            date.fromisoformat(row["frozen_today"])
        except (TypeError, ValueError):
            errors.append("frozen_today: not an ISO date (YYYY-MM-DD)")
    for key in ("expected_trace", "must_not_call"):
        if key in row and not _is_str_list(row[key]):
            errors.append(f"{key}: must be a list of tool names")
    entity = row.get("expected_entity")
    if "expected_entity" in row:
        if not isinstance(entity, dict) or not set(entity) <= {"slug", "ambiguous"}:
            errors.append("expected_entity: must be {slug} or {ambiguous}")
        elif "slug" in entity and "ambiguous" in entity:
            errors.append("expected_entity: slug and ambiguous are mutually exclusive")
        elif "slug" in entity:
            if not (isinstance(entity["slug"], str) and entity["slug"]):
                errors.append("expected_entity: slug must be a non-empty string")
        elif "ambiguous" in entity:
            if not (_is_str_list(entity["ambiguous"]) and len(entity["ambiguous"]) == 2):
                errors.append("expected_entity: ambiguous must list exactly two slugs")
        else:
            errors.append("expected_entity: needs slug or ambiguous")
    focus = row.get("focus")
    if "focus" in row and (not isinstance(focus, dict) or set(focus) != FOCUS_KEYS):
        errors.append("focus: must have exactly entity, metric, period")
    where = row.get("where")
    if (
        "where" in row
        and where is not None
        and (not isinstance(where, dict) or not set(where) <= WHERE_KEYS)
    ):
        errors.append("where: only borrower_group, depositor_group, status")
    if "expected_ref_ids" in row and not _is_str_list(row["expected_ref_ids"]):
        errors.append("expected_ref_ids: must be a list of ref_ids")
    facts = row.get("expected_facts")
    if "expected_facts" in row and (
        not isinstance(facts, dict) or not set(facts) <= FACT_KEYS
    ):
        errors.append("expected_facts: only count, total_amount, overdue_undated")
    return errors


def read_rows(path: Path) -> list[dict[str, Any]]:
    """Decoded, validated rows of one JSONL file, in file order."""
    rows: list[dict[str, Any]] = []
    problems: list[str] = []
    for number, line in enumerate(Path(path).read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"{path.name}:{number}: invalid JSON ({exc.msg})")
            continue
        problems.extend(f"{path.name}:{number}: {e}" for e in validate(row))
        rows.append(row)
    if problems:
        raise CaseFileError("; ".join(problems))
    return rows


def to_case(row: dict[str, Any]) -> Case:
    refs = row.get("expected_ref_ids")
    return Case(
        id=row["id"],
        suite=row["suite"],
        question=row["question"],
        frozen_today=date.fromisoformat(row["frozen_today"]),
        expected_trace=tuple(row["expected_trace"]),
        expected_entity=dict(row["expected_entity"]),
        focus=dict(row["focus"]),
        must_not_call=tuple(row["must_not_call"]),
        where=row.get("where"),
        expected_ref_ids=None if refs is None else tuple(refs),
        expected_facts=row.get("expected_facts"),
        raw=row,
    )


def load_cases(path: Path | None = None) -> list[Case]:
    """Every case in `path`, or in every `cases/*.jsonl` (sorted by file name).
    Duplicate ids across files are an error."""
    paths = [Path(path)] if path else sorted(CASES_DIR.glob("*.jsonl"))
    cases = [to_case(row) for p in paths for row in read_rows(p)]
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise CaseFileError(f"duplicate case id {case.id!r}")
        seen.add(case.id)
    return cases
