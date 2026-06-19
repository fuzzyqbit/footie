"""Greedy budgeted swap search over an existing lineup.

Greedy is not globally optimal: each round applies the single best affordable
swap and re-evaluates. The trade-off is transparency (every suggestion is
independently justified by its own deltas) and speed.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..chem.engine import compute_chemistry
from ..chem.formations import slot_position
from ..chem.lineup import Lineup
from ..models import Card, slugify
from .market import net_cost, resale_value
from .meta import CHEM_WEIGHT, RATING_CHEM_WEIGHT, meta_score

DEFAULT_MAX_SWAPS = 3
DEFAULT_OBJECTIVE = "meta"


@dataclass(frozen=True)
class Swap:
    slot: str
    out_id: str
    out_name: str
    out_version: str
    out_resale: int
    in_id: str
    in_name: str
    in_version: str
    in_price: int
    net_cost: int
    meta_delta: float
    chem_delta: int
    score_delta: float


@dataclass(frozen=True)
class UpgradePlan:
    swaps: tuple[Swap, ...]
    spent: int
    budget: int
    score_before: float
    score_after: float
    chem_before: int
    chem_after: int
    warnings: tuple[str, ...]


def _same_player(name_a: str, name_b: str) -> bool:
    """Same real player across name-vocabulary variants.

    Exact slug match, or one slug extends the other at a token boundary
    ("cristiano-ronaldo" -> "cristiano-ronaldo-dos-santos-aveiro"). Bare
    substring matching is deliberately avoided: "rodri" must NOT match
    "rodrigo-de-paul". Known miss: nickname forms ("Vini Jr." vs
    "Vinicius Junior") - documented limitation.
    """
    slug_a, slug_b = slugify(name_a), slugify(name_b)
    if slug_a == slug_b:
        return True
    return slug_b.startswith(slug_a + "-") or slug_a.startswith(slug_b + "-")


def _squad_state(
    lineup: Lineup, slot_cards: dict[str, Card], objective: str = DEFAULT_OBJECTIVE
) -> tuple[float, int]:
    """(composite score, team chem) for a candidate XI.

    objective="meta": pace-meta-weighted faces + CHEM_WEIGHT * chem.
    objective="rating": raw squad OVR + RATING_CHEM_WEIGHT * chem (chem breaks ties).
    """
    chem = compute_chemistry(lineup, slot_cards).team_total
    if objective == "rating":
        ovr_total = sum(slot_cards[s].ovr for s, _ in lineup.slots)
        return ovr_total + RATING_CHEM_WEIGHT * chem, chem
    meta_total = 0.0
    for slot_key, _card_id in lineup.slots:
        score = meta_score(slot_cards[slot_key], slot_position(slot_key))
        if score is not None:
            meta_total += score
    return meta_total + CHEM_WEIGHT * chem, chem


def find_upgrades(
    lineup: Lineup,
    slot_cards: dict[str, Card],
    pool: tuple[Card, ...],
    *,
    budget: int,
    max_swaps: int = DEFAULT_MAX_SWAPS,
    objective: str = DEFAULT_OBJECTIVE,
) -> UpgradePlan:
    warnings: list[str] = []
    current = dict(slot_cards)
    score_before, chem_before = _squad_state(lineup, current, objective)
    remaining = budget
    swaps: list[Swap] = []
    swapped_slots: set[str] = set()

    # Precompute once (order-preserving, pure): per-position eligible candidates
    # (priced + position-eligible, in original pool order) and their meta_score.
    # The inner loop then scans only the cards eligible for a slot's position --
    # not the full pool every round -- and reads meta_score from a table instead
    # of recomputing it. Candidate ORDER is preserved (pool order) so the
    # delta/cost tie-break resolves identically, and the price/position/meta-None
    # skip conditions are unchanged.
    positions = {slot_position(slot_key) for slot_key, _ in lineup.slots}
    eligible: dict[str, list[Card]] = {p: [] for p in positions}
    meta_table: dict[tuple[str, str], float | None] = {}
    for card in pool:
        if card.price is None:
            continue   # unbuyable
        for position in positions:
            if position == card.position or position in card.alt_positions:
                eligible[position].append(card)
                meta_table[(card.id, position)] = meta_score(card, position)

    for _round in range(max_swaps):
        base_score, base_chem = _squad_state(lineup, current, objective)
        best: Swap | None = None
        best_card: Card | None = None
        for slot_key, _card_id in lineup.slots:
            if slot_key in swapped_slots:
                continue
            position = slot_position(slot_key)
            outgoing = current[slot_key]
            out_meta = meta_score(outgoing, position)
            # one real player per XI - but the OUTGOING card leaves, so exclude
            # its own slot from the comparison (self-upgrades legal). Hoisted out
            # of the candidate loop; the prefix-aware _same_player check is kept.
            other_names = [
                card.player_name
                for other_slot, card in current.items()
                if other_slot != slot_key
            ]
            for candidate in eligible.get(position, ()):
                if any(_same_player(candidate.player_name, name) for name in other_names):
                    continue
                cost = net_cost(candidate.price, outgoing.price)
                if cost > remaining:
                    continue
                candidate_meta = meta_table.get((candidate.id, position))
                if candidate_meta is None:
                    continue
                trial = {**current, slot_key: candidate}
                trial_score, trial_chem = _squad_state(lineup, trial, objective)
                delta = trial_score - base_score
                if delta <= 0:
                    continue
                better = best is None or delta > best.score_delta or (
                    delta == best.score_delta and cost < best.net_cost
                )
                if better:
                    best = Swap(
                        slot=slot_key,
                        out_id=outgoing.id, out_name=outgoing.player_name,
                        out_version=outgoing.version,
                        out_resale=resale_value(outgoing.price),
                        in_id=candidate.id, in_name=candidate.player_name,
                        in_version=candidate.version, in_price=candidate.price,
                        net_cost=cost,
                        meta_delta=candidate_meta - (out_meta or 0.0),
                        chem_delta=trial_chem - base_chem,
                        score_delta=delta,
                    )
                    best_card = candidate
        if best is None or best_card is None:
            break
        if current[best.slot].price is None:
            warnings.append(f"{best.out_id}: resale unknown - treated as 0")
        current[best.slot] = best_card
        swapped_slots.add(best.slot)
        remaining -= best.net_cost
        swaps.append(best)

    score_after, chem_after = _squad_state(lineup, current, objective)
    return UpgradePlan(
        swaps=tuple(swaps), spent=budget - remaining, budget=budget,
        score_before=score_before, score_after=score_after,
        chem_before=chem_before, chem_after=chem_after,
        warnings=tuple(warnings),
    )
