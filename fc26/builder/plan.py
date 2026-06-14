"""Acquisition planner: an ordered, budget-phased buy ledger.

`build` answers "best XI for budget B" and `upgrade` answers "improve this
squad within B", but neither tells you *in what order* to spend or *what each
buy returns*. The planner reuses those engines unchanged and presents the
result as a step-by-step ledger: the cheapest legal XI to buy now (build mode),
then the ordered upgrade path with running spend, remaining budget, a
score/chem trajectory, and return-on-investment (squad score gained per coin).

No new optimizer: a globally-optimal knapsack is out of scope (the greedy
engines stay the single source of swap selection).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..chem.lineup import Lineup
from ..models import Card
from .build import build_squad
from .upgrade import DEFAULT_MAX_SWAPS, UpgradePlan, find_upgrades


@dataclass(frozen=True)
class SeedBuy:
    slot: str
    card_id: str
    player_name: str
    version: str
    price: int


@dataclass(frozen=True)
class PlanStep:
    index: int                 # 1-based acquisition order
    slot: str
    out_id: str
    out_name: str
    out_version: str
    out_resale: int
    in_id: str
    in_name: str
    in_version: str
    in_price: int
    net_cost: int              # in_price - resale(out); may be negative (profit)
    cumulative_spent: int      # running upgrade spend through this step
    remaining: int             # upgrade budget left after this step
    score_after: float
    chem_after: int
    roi: float | None          # score_delta / net_cost; None when net_cost <= 0


@dataclass(frozen=True)
class AcquisitionPlan:
    mode: str                       # "build" | "upgrade"
    formation: str
    seed: tuple[SeedBuy, ...]       # () in upgrade mode
    seed_cost: int                  # 0 in upgrade mode
    base_score: float               # seed/base squad composite score
    base_chem: int
    steps: tuple[PlanStep, ...]     # ordered upgrade buys
    budget: int                     # the user's total budget cap
    upgrade_spent: int
    total_spent: int                # seed_cost + upgrade_spent
    final_score: float
    final_chem: int
    warnings: tuple[str, ...]


def _steps_from_plan(plan: UpgradePlan) -> tuple[PlanStep, ...]:
    """Linearise an UpgradePlan's swaps into a running ledger.

    `plan.budget` is the budget handed to the swap search (total minus seed
    cost in build mode, the raw cap in upgrade mode), so `remaining` is the
    upgrade budget left after each step in both modes.
    """
    steps: list[PlanStep] = []
    cumulative = 0
    score = plan.score_before
    chem = plan.chem_before
    for i, swap in enumerate(plan.swaps, start=1):
        cumulative += swap.net_cost
        score += swap.score_delta
        chem += swap.chem_delta
        roi = swap.score_delta / swap.net_cost if swap.net_cost > 0 else None
        steps.append(PlanStep(
            index=i,
            slot=swap.slot,
            out_id=swap.out_id,
            out_name=swap.out_name,
            out_version=swap.out_version,
            out_resale=swap.out_resale,
            in_id=swap.in_id,
            in_name=swap.in_name,
            in_version=swap.in_version,
            in_price=swap.in_price,
            net_cost=swap.net_cost,
            cumulative_spent=cumulative,
            remaining=plan.budget - cumulative,
            score_after=score,
            chem_after=chem,
            roi=roi,
        ))
    return tuple(steps)


def plan_from_scratch(
    formation: str,
    pool: tuple[Card, ...],
    *,
    budget: int,
    league: str | None = None,
    name: str | None = None,
) -> AcquisitionPlan:
    """Build-mode plan: cheapest legal seed XI + ordered upgrade path."""
    result = build_squad(formation, pool, budget=budget, league=league, name=name)
    improve = result.improve_plan

    # The seed (the XI to buy now) is the final XI with every swap reverted to
    # its outgoing card. by_id covers every card the swaps could reference.
    by_id = {c.id: c for c in pool}
    seed_cards = dict(result.slot_cards)
    for swap in improve.swaps:
        seed_cards[swap.slot] = by_id[swap.out_id]

    seed = tuple(
        SeedBuy(slot=slot, card_id=card.id, player_name=card.player_name,
                version=card.version, price=card.price)
        for slot, card in ((s, seed_cards[s]) for s, _ in result.lineup.slots)
    )

    return AcquisitionPlan(
        mode="build",
        formation=formation,
        seed=seed,
        seed_cost=result.seed_cost,
        base_score=improve.score_before,
        base_chem=improve.chem_before,
        steps=_steps_from_plan(improve),
        budget=budget,
        upgrade_spent=improve.spent,
        total_spent=result.total_cost,
        final_score=improve.score_after,
        final_chem=improve.chem_after,
        warnings=improve.warnings,
    )


def plan_for_squad(
    lineup: Lineup,
    slot_cards: dict[str, Card],
    pool: tuple[Card, ...],
    *,
    budget: int,
    max_swaps: int = DEFAULT_MAX_SWAPS,
) -> AcquisitionPlan:
    """Upgrade-mode plan: an existing squad's swap path as a running ledger."""
    plan = find_upgrades(lineup, slot_cards, pool, budget=budget, max_swaps=max_swaps)
    return AcquisitionPlan(
        mode="upgrade",
        formation=lineup.formation,
        seed=(),
        seed_cost=0,
        base_score=plan.score_before,
        base_chem=plan.chem_before,
        steps=_steps_from_plan(plan),
        budget=budget,
        upgrade_spent=plan.spent,
        total_spent=plan.spent,
        final_score=plan.score_after,
        final_chem=plan.chem_after,
        warnings=plan.warnings,
    )
