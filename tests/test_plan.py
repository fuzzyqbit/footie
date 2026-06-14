import json
from dataclasses import asdict

import pytest

from fc26.builder.build import BuildError
from fc26.builder.plan import (
    AcquisitionPlan,
    PlanStep,
    SeedBuy,
    plan_for_squad,
    plan_from_scratch,
)
from fc26.chem.lineup import Lineup
from fc26.models import Card, FaceStats

FACE = FaceStats(pac=80, sho=80, pas=80, dri=80, def_=80, phy=80)
GOOD = FaceStats(pac=92, sho=92, pas=92, dri=92, def_=92, phy=92)

SLOTS = ("GK", "RB", "CB1", "CB2", "LB", "CDM1", "CDM2", "CAM", "RW", "LW", "ST")
POS_FOR_SLOT = {"GK": "GK", "RB": "RB", "CB1": "CB", "CB2": "CB", "LB": "LB",
                "CDM1": "CDM", "CDM2": "CDM", "CAM": "CAM", "RW": "RW", "LW": "LW", "ST": "ST"}


def _pool_card(i, position, *, price=1_000, name=None, face=FACE, league="Premier League"):
    return Card(id=f"p{i}--base", player_name=name or f"Player {i}", version="base",
                ovr=80, position=position, face=face, price=price,
                club=f"C{i}", nation=f"N{i}", league=league)


def _basic_pool():
    """Two distinct players per needed position, prices 1_000 and 2_000."""
    cards = []
    i = 0
    for pos in ("GK", "RB", "CB", "CB", "LB", "CDM", "CDM", "CAM", "RW", "LW", "ST"):
        cards.append(_pool_card(i, pos, price=1_000))
        cards.append(_pool_card(i + 100, pos, price=2_000))
        i += 1
    return tuple(cards)


def _xi_lineup():
    """A resolved 4-2-3-1 XI of base cards @10_000 each, plus pool + lineup."""
    cards = {}
    for slot in SLOTS:
        cards[slot] = Card(
            id=f"{slot.lower()}--base", player_name=f"P{slot}", version="base",
            ovr=80, position=POS_FOR_SLOT[slot], club=f"C{slot}", nation=f"N{slot}",
            league="Premier League", price=10_000, face=FACE,
        )
    lineup = Lineup(name="X", formation="4-2-3-1",
                    slots=tuple((slot, cards[slot].id) for slot in SLOTS))
    return lineup, cards


# --- build mode ---

def test_plan_from_scratch_seeds_and_orders_upgrades():
    pool = _basic_pool() + (_pool_card(999, "ST", price=20_000, name="Star", face=GOOD),)
    plan = plan_from_scratch("4-2-3-1", pool, budget=40_000)
    assert isinstance(plan, AcquisitionPlan)
    assert plan.mode == "build"
    assert plan.formation == "4-2-3-1"
    assert len(plan.seed) == 11
    assert all(isinstance(sb, SeedBuy) for sb in plan.seed)
    assert plan.seed_cost == 11_000
    assert any(s.in_name == "Star" and s.slot == "ST" for s in plan.steps)
    assert plan.total_spent <= 40_000


def test_seed_is_the_cheapest_legal_xi():
    plan = plan_from_scratch("4-2-3-1", _basic_pool(), budget=50_000)
    assert len(plan.seed) == 11
    assert {sb.price for sb in plan.seed} == {1_000}
    assert {sb.slot for sb in plan.seed} == set(SLOTS)


def test_plan_with_no_improvements_has_empty_steps():
    plan = plan_from_scratch("4-2-3-1", _basic_pool(), budget=50_000)
    assert plan.steps == ()
    assert plan.total_spent == 11_000
    assert plan.final_score == plan.base_score
    assert plan.final_chem == plan.base_chem


def test_steps_carry_running_cashflow_score_and_roi():
    pool = _basic_pool() + (_pool_card(999, "ST", price=20_000, name="Star", face=GOOD),)
    plan = plan_from_scratch("4-2-3-1", pool, budget=40_000)
    assert plan.steps
    step = plan.steps[0]
    assert isinstance(step, PlanStep)
    assert step.index == 1
    assert step.slot == "ST"
    assert step.in_name == "Star"
    # seed ST is the cheapest ST @1_000 -> resale 950; net = 20_000 - 950
    assert step.net_cost == 19_050
    assert step.cumulative_spent == 19_050
    # build budget for upgrades = 40_000 - seed_cost(11_000) = 29_000
    assert step.remaining == 29_000 - 19_050
    assert step.roi is not None and step.roi > 0
    # trajectory lands on the plan's authoritative final score/chem
    assert plan.steps[-1].score_after == pytest.approx(plan.final_score)
    assert plan.steps[-1].chem_after == plan.final_chem


def test_plan_from_scratch_infeasible_budget_propagates():
    with pytest.raises(BuildError, match="11000"):
        plan_from_scratch("4-2-3-1", _basic_pool(), budget=5_000)


# --- upgrade mode ---

def test_plan_for_squad_orders_swaps_as_ledger():
    lineup, slot_cards = _xi_lineup()
    star = _pool_card(999, "ST", price=50_000, name="Star", face=GOOD)
    pool = tuple(slot_cards.values()) + (star,)
    plan = plan_for_squad(lineup, slot_cards, pool, budget=100_000)
    assert plan.mode == "upgrade"
    assert plan.seed == ()
    assert plan.seed_cost == 0
    assert plan.steps and plan.steps[0].in_name == "Star"
    assert plan.total_spent == plan.upgrade_spent <= 100_000
    assert plan.steps[0].remaining == 100_000 - plan.steps[0].net_cost


def test_roi_is_none_for_free_or_profit_buys():
    lineup, slot_cards = _xi_lineup()
    # ST seed is expensive + weak; a cheaper, stronger ST exists -> negative net cost
    slot_cards = dict(slot_cards)
    weak = Card(id="st--base", player_name="PST", version="base", ovr=80, position="ST",
                club="CST", nation="NST", league="Premier League", price=100_000, face=FACE)
    slot_cards["ST"] = weak
    strong = _pool_card(777, "ST", price=50_000, name="Cheap Star", face=GOOD)
    pool = tuple(c for c in slot_cards.values()) + (strong,)
    plan = plan_for_squad(lineup, slot_cards, pool, budget=100_000)
    step = plan.steps[0]
    assert step.in_name == "Cheap Star"
    assert step.net_cost < 0          # sells weak (resale 95k) to buy strong (50k) -> profit
    assert step.roi is None


def test_acquisition_plan_is_json_serializable():
    pool = _basic_pool() + (_pool_card(999, "ST", price=20_000, name="Star", face=GOOD),)
    plan = plan_from_scratch("4-2-3-1", pool, budget=40_000)
    blob = json.dumps(asdict(plan))   # must not raise: roi is None, never inf/nan
    assert json.loads(blob)["mode"] == "build"
