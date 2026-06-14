"""Market economics: budget parsing and net swap cost (EA 5% sell tax)."""

from __future__ import annotations

import re

from ..errors import FC26Error
from ..ingest.futbin import parse_price

SELL_TAX = 0.05


class BudgetError(FC26Error):
    """Unparseable budget string."""


def parse_budget(raw: str) -> int:
    # Users type big budgets in many shapes ("5 000 000", "5 M", "$5M", "5m coins").
    # Strip whitespace, a currency symbol, and a trailing "coins"/"coin" word, then
    # defer to parse_price (handles K/M units, comma grouping, plain integers).
    normalized = re.sub(r"\s+", "", raw or "").lstrip("$£€")
    normalized = re.sub(r"coins?$", "", normalized, flags=re.IGNORECASE)
    coins = parse_price(normalized)
    if coins is None:
        raise BudgetError(f"cannot parse budget {raw!r} (use forms like 100K, 1.2M, 50000)")
    return coins


def resale_value(price: int | None) -> int:
    """Coins recovered by selling a card; unknown price -> 0 (flagged upstream)."""
    if price is None:
        return 0
    return int((1 - SELL_TAX) * price)


def net_cost(incoming_price: int, outgoing_price: int | None) -> int:
    """Cost of a swap when the outgoing card is sold to fund it."""
    return incoming_price - resale_value(outgoing_price)
