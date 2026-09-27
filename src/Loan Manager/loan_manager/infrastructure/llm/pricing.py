"""KCH-234: FinHive-maintained price table (ARB:498-499 — replaces
`litellm.completion_cost`; hash-versioned as `finhive.eval.price_version`).

`prices.json` lives beside this module, not under `data/` (`data/*` is
gitignored as plaintext app output; a price table is source, not output).
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

PRICES_FILE = Path(__file__).parent / "prices.json"

# Six places: an OpenRouter per-Mtok price times a handful of tokens divided
# by 1e6 is routinely a fraction of a cent (data/settings.json's own measured
# figure is $0.00037 for a whole call) — two-place cents rounding would floor
# every real cost to $0.00, which is the exact failure ARB:298-304 warns
# against. This is LLM-spend accounting, not loan money; CLAUDE.md's 2dp rule
# governs domain amounts, not this table.
_COST_PLACES = Decimal("0.000001")


def price_version(path: Path = PRICES_FILE) -> str:
    """sha256 of the raw file bytes, truncated to 12 hex chars. Changes
    exactly when the price table's content changes, so a `Usage.cost_usd`
    can be traced back to the table version that produced it."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def cost_for(
    model: str, prompt_tokens: int, completion_tokens: int, path: Path = PRICES_FILE
) -> tuple[Decimal | None, str | None]:
    """(cost_usd, price_version) for one completion. `cost_usd` is `None` —
    never `Decimal("0")` — for a model with no evidenced entry, so "we don't
    know the price" is never mistaken for "this call was free"."""
    data = json.loads(Path(path).read_text())
    entry = data.get("models", {}).get(model)
    if entry is None:
        return None, None

    prompt_price = Decimal(str(entry["prompt_usd_per_mtok"]))
    completion_price = Decimal(str(entry["completion_usd_per_mtok"]))
    million = Decimal(1_000_000)
    prompt_cost = Decimal(prompt_tokens) * prompt_price
    completion_cost = Decimal(completion_tokens) * completion_price
    cost = (prompt_cost + completion_cost) / million
    return cost.quantize(_COST_PLACES, rounding=ROUND_HALF_UP), price_version(path)
