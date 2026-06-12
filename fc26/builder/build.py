"""Seed-and-improve full-XI builder.

Seed the cheapest legal XI for the formation, then hand the remaining budget
to the phase-5 greedy swap engine (max_swaps=11). All economics (95% resale on
replaced seeds) come from the upgrade engine unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..chem.aliases import canonical_league
from ..chem.formations import FORMATIONS, slot_position
from ..chem.lineup import Lineup
from ..errors import FC26Error
from ..models import Card
from .upgrade import UpgradePlan, _same_player, find_upgrades

BUILD_MAX_SWAPS = 11   # improve phase may touch every slot


class BuildError(FC26Error):
    """Cannot build a legal XI under the given constraints."""


@dataclass(frozen=True)
class BuildResult:
    lineup: Lineup
    slot_cards: dict[str, Card]    # final XI after improvement
    seed_cost: int                 # gross cost of the cheapest legal XI
    improve_plan: UpgradePlan
    total_cost: int                # seed_cost + improve_plan.spent


def _usable(card: Card) -> bool:
    face = card.face
    return card.price is not None and all(
        s is not None for s in (face.pac, face.sho, face.pas, face.dri, face.def_, face.phy)
    )


def _eligible(card: Card, position: str) -> bool:
    return card.position == position or position in card.alt_positions


def build_squad(
    formation: str,
    pool: tuple[Card, ...],
    *,
    budget: int,
    league: str | None = None,
    name: str | None = None,
) -> BuildResult:
    if formation not in FORMATIONS:
        available = ", ".join(sorted(FORMATIONS))
        raise BuildError(f"unknown formation {formation!r} - available: {available}")

    candidates = tuple(c for c in pool if _usable(c))
    if league is not None:
        wanted = canonical_league(league)
        candidates = tuple(
            c for c in candidates
            if c.league is not None and canonical_league(c.league) == wanted
        )
        if not candidates:
            raise BuildError(f"no priced cards match league {league!r}")

    # --- seed: cheapest legal card per slot, in formation order ---
    seed: dict[str, Card] = {}
    for slot in FORMATIONS[formation]:
        position = slot_position(slot)
        slot_options = sorted(
            (
                c for c in candidates
                if _eligible(c, position)
                and not any(_same_player(c.player_name, s.player_name) for s in seed.values())
            ),
            key=lambda c: c.price,
        )
        if not slot_options:
            raise BuildError(f"no eligible card for slot {slot} ({position})"
                             + (f" in league {league!r}" if league else ""))
        seed[slot] = slot_options[0]

    seed_cost = sum(card.price for card in seed.values())
    if seed_cost > budget:
        raise BuildError(
            f"budget too small to field a legal XI in {formation} "
            f"(cheapest legal XI costs {seed_cost})"
        )

    lineup = Lineup(
        name=name or f"Built {formation}",
        formation=formation,
        slots=tuple((slot, seed[slot].id) for slot in FORMATIONS[formation]),
    )

    # --- improve: existing greedy engine over the remaining budget ---
    improve = find_upgrades(lineup, seed, candidates,
                            budget=budget - seed_cost, max_swaps=BUILD_MAX_SWAPS)
    by_id = {c.id: c for c in candidates}
    final = dict(seed)
    for swap in improve.swaps:
        final[swap.slot] = by_id[swap.in_id]

    return BuildResult(
        lineup=lineup,
        slot_cards=final,
        seed_cost=seed_cost,
        improve_plan=improve,
        total_cost=seed_cost + improve.spent,
    )
