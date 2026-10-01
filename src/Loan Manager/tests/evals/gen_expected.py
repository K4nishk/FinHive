"""Derive the generated half of each eval case (KCH-248).

    python -m tests.evals.gen_expected            # rewrite cases/*.jsonl
    python -m tests.evals.gen_expected --check    # exit 1 if any file differs

For every case: seed a fresh `:memory:` database with the eval book at the
case's own `frozen_today`, through the encrypting repository; read the active
loans back; keep those matching `where`; derive status with `StatusEngine`
(never the persisted column); write `expected_ref_ids` (sorted) and
`expected_facts` (count, 2dp `ROUND_HALF_UP` total, overdue_undated). A case
with no `where` is a no-query case: no refs, no facts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.infrastructure.seed.demo_fixture import FixtureLoan

from tests.evals.fixture import ALL_LOANS, seeded_container, use_ephemeral_key_ring
from tests.evals.schema import CASES_DIR, KEY_ORDER, Case, read_rows, to_case

_CENT = Decimal("0.01")


def expected_for(
    case: Case, loans: tuple[FixtureLoan, ...] = ALL_LOANS
) -> tuple[list[str], dict[str, Any]]:
    """`(expected_ref_ids, expected_facts)` for one case against `loans`."""
    if not case.where:
        return [], {}
    where = case.where
    status = where.get("status", "overdue")
    today: date = case.frozen_today
    with seeded_container(today, loans) as container, container.get_uow() as uow:
        active = uow.loans.get_all_active()
    matched = []
    for loan in active:
        if "borrower_group" in where and loan.borrower_group != where["borrower_group"]:
            continue
        if "depositor_group" in where and loan.depositor_group != where["depositor_group"]:
            continue
        derived = StatusEngine.compute(loan.giving_date, loan.due_date, today)
        if derived.value.lower() == status:
            matched.append(loan)
    total = sum((Decimal(int(loan.amount)) for loan in matched), start=Decimal("0"))
    facts = {
        "count": len(matched),
        "total_amount": str(total.quantize(_CENT, rounding=ROUND_HALF_UP)),
        "overdue_undated": sum(
            1
            for loan in matched
            if loan.due_date is None
            and StatusEngine.compute(loan.giving_date, loan.due_date, today).value == "Overdue"
        ),
    }
    return sorted(str(loan.reference_id) for loan in matched), facts


def render_file(path: Path, loans: tuple[FixtureLoan, ...] = ALL_LOANS) -> str:
    """The file's canonical text with generated keys re-derived."""
    lines = []
    for row in read_rows(path):
        refs, facts = expected_for(to_case(row), loans)
        row = {**row, "expected_ref_ids": refs, "expected_facts": facts}
        ordered = {key: row[key] for key in KEY_ORDER if key in row}
        lines.append(json.dumps(ordered, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tests.evals.gen_expected")
    parser.add_argument("--check", action="store_true", help="exit 1 if a file would change")
    args = parser.parse_args(argv)

    if not os.environ.get("PYTEST_CURRENT_TEST"):
        use_ephemeral_key_ring()

    stale = []
    for path in sorted(CASES_DIR.glob("*.jsonl")):
        text = render_file(path)
        if path.read_text() != text:
            stale.append(path.name)
            if not args.check:
                path.write_text(text)
    if stale and args.check:
        sys.stderr.write(f"stale generated keys: {', '.join(stale)}; run gen_expected\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
