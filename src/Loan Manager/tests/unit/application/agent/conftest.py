"""Shared fixtures for the KCH-235 agent tool-args/registry tests."""
from __future__ import annotations

from typing import Any

# One minimal, VALID payload per tool name, reused across test_tool_args.py
# and test_tool_registry.py so the two files can't drift on what "valid"
# means for a given tool.
VALID_PAYLOADS: dict[str, dict[str, Any]] = {
    "get_current_context": {},
    "resolve_entity": {"text": "sharma group"},
    "query_loans": {"status": "overdue"},
    "get_portfolio_summary": {},
    "calculate_interest": {"ref_id": "2026_03_004", "rate": 12, "months": 3},
    "format_inr": {"amount": "1500.50"},
    "extend_loan": {"ref_id": "2026_03_004", "months": 3, "rate": 12},
    "create_loan": {
        "borrower_name": "Ravi Kumar",
        "borrower_group": "sharma-group",
        "depositor_name": "Meena Shah",
        "amount": 150000,
    },
    "update_loan": {"ref_id": "2026_03_004", "amount": 200000},
    "extend_overdue_batch": {"borrower_group": "sharma-group", "months": 3, "rate": 12},
}
