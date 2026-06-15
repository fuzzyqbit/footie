"""Value picks: good cards that are cheap on the market.

Ranks cards by quality-per-coin so underrated bargains float to the top. An OVR
floor keeps the list "good" (no fodder) and a price ceiling keeps it "cheap".
Quality is the best meta score across a card's positions (pace-meta-weighted
face stats), falling back to raw OVR when face stats are missing.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..models import Card
from .meta import meta_score

DEFAULT_MIN_OVR = 83          # "good" floor — skip low-rated fodder
DEFAULT_MAX_PRICE = 50_000    # "cheap" ceiling, in coins


@dataclass(frozen=True)
class ValuePick:
    card: Card
    best_pos: str
    quality: float   # best meta score (0-99), or OVR if no face stats
    value: float     # quality per 1000 coins — higher = better bargain


def _quality(card: Card) -> tuple[float, str]:
    """Best meta score across the card's positions, with the position it came
    from. Falls back to OVR (and primary position) when no face stats exist."""
    best: float | None = None
    best_pos = card.position
    for pos in (card.position, *card.alt_positions):
        score = meta_score(card, pos)
        if score is not None and (best is None or score > best):
            best, best_pos = score, pos
    if best is None:
        return float(card.ovr), card.position
    return best, best_pos


def value_picks(
    cards,
    *,
    min_ovr: int = DEFAULT_MIN_OVR,
    max_price: int | None = DEFAULT_MAX_PRICE,
    pos: str | None = None,
    positions: frozenset[str] | None = None,
    limit: int = 30,
    per_tier: int | None = None,
) -> list[ValuePick]:
    """Cards ranked by value (quality per 1000 coins), best bargain first.

    When `per_tier` is set, keep at most that many picks per OVR rating and
    order the result by rating (high to low) so the page shows the best
    bargain at each tier instead of a wall of the single cheapest rating.
    """
    wanted = pos.upper() if pos else None
    picks: list[ValuePick] = []
    for card in cards:
        if card.price is None or card.price <= 0:
            continue
        if card.ovr < min_ovr:
            continue
        if max_price is not None and card.price > max_price:
            continue
        if wanted and card.position != wanted and wanted not in card.alt_positions:
            continue
        if positions is not None and not (
            card.position in positions or positions.intersection(card.alt_positions)
        ):
            continue
        quality, best_pos = _quality(card)
        value = quality * 1000.0 / card.price
        picks.append(ValuePick(card=card, best_pos=best_pos, quality=quality, value=value))
    picks.sort(key=lambda p: p.value, reverse=True)

    if per_tier is not None:
        kept: list[ValuePick] = []
        seen: Counter[int] = Counter()
        for pick in picks:   # value-sorted, so first seen per rating is its best bargain
            if seen[pick.card.ovr] < per_tier:
                kept.append(pick)
                seen[pick.card.ovr] += 1
        kept.sort(key=lambda p: (p.card.ovr, p.value), reverse=True)
        picks = kept

    return picks[:limit]
