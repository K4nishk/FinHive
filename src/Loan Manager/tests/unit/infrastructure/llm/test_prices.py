"""KCH-234: price_version is a content hash, not a constant -- it must move
when prices.json's bytes move, or a cost figure could be silently
attributed to the wrong price table version (ARB:498-499)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from loan_manager.infrastructure.llm import pricing


def test_price_version_changes_when_file_changes(tmp_path: Path) -> None:
    path = tmp_path / "prices.json"
    path.write_text('{"as_of": "2026-01-01", "models": {}}')
    version_1 = pricing.price_version(path)

    path.write_text('{"as_of": "2026-01-02", "models": {}}')
    version_2 = pricing.price_version(path)

    assert len(version_1) == 12
    assert version_1 != version_2


def test_repo_prices_file_has_no_invented_numbers() -> None:
    """KCH-234's own prices.json ships with no evidenced per-Mtok price for
    qwen/qwen-2.5-72b-instruct (data/settings.json's measured_usd_per_call is
    a whole-call figure, not a rate) -- cost_for() must therefore return
    None, never a fabricated Decimal."""
    cost, version = pricing.cost_for("qwen/qwen-2.5-72b-instruct", 100, 20)
    assert cost is None
    assert version is None


def test_cost_for_arithmetic_uses_decimal_round_half_up(tmp_path: Path) -> None:
    """MINOR (review round 1, item 9); NONZERO completion leg (review round
    2, item 3); DIFFERENT prompt vs completion prices (KCH-234 fix cycle 3):
    a same-price table (0.1/0.1) cannot tell the correct arithmetic apart
    from the bug it guards against, because swapping in the wrong per-leg
    price is invisible when both legs charge the same rate. With prompt at
    $0.10/Mtok and completion at $0.30/Mtok: 10 prompt tokens is 1.0
    (millionths-of-a-dollar units before the final /1e6) and 25 completion
    tokens at $0.30/Mtok is 7.5, summing to exactly 8.5 USD-millionths
    (0.0000085 USD) before rounding -- a halfway case. ROUND_HALF_UP takes
    it to 0.000009; Python's default ROUND_HALF_EVEN would take it to
    0.000008 (8 is already even). Computing the completion leg from
    `prompt_usd_per_mtok` instead of `completion_usd_per_mtok` (the bug this
    guards against) gives 10*0.1 + 25*0.1 = 3.5 USD-millionths instead,
    rounding to the visibly different 0.000004 -- so this test now fails for
    that reason too, not just a dropped rounding mode."""
    path = tmp_path / "prices.json"
    path.write_text(json.dumps({
        "as_of": "2026-01-01",
        "models": {
            "test/model": {
                "prompt_usd_per_mtok": "0.1",
                "completion_usd_per_mtok": "0.3",
            }
        },
    }))

    cost, version = pricing.cost_for("test/model", 10, 25, path=path)

    assert cost == Decimal("0.000009")
    assert version == pricing.price_version(path)
