import pytest

from fc26.builder.upgrade import UpgradePlan, find_upgrades
from fc26.chem.lineup import Lineup
from fc26.models import Card, FaceStats

SLOTS = ("GK", "RB", "CB1", "CB2", "LB", "CDM1", "CDM2", "CAM", "RW", "LW", "ST")
POSITIONS = {"GK": "GK", "RB": "RB", "CB1": "CB", "CB2": "CB", "LB": "LB",
             "CDM1": "CDM", "CDM2": "CDM", "CAM": "CAM", "RW": "RW", "LW": "LW", "ST": "ST"}

WEAK = FaceStats(pac=70, sho=70, pas=70, dri=70, def_=70, phy=70)   # meta 70 at any position
STRONG = FaceStats(pac=90, sho=90, pas=90, dri=90, def_=90, phy=90)  # meta 90 at any position


def _xi_card(slot, *, name=None, price=10_000):
    return Card(id=f"{slot.lower()}--base", player_name=name or f"P{slot}", version="base",
                ovr=80, position=POSITIONS[slot], face=WEAK,
                club=f"C{slot}", nation=f"N{slot}", league=f"L{slot}", price=price)


def _squad():
    cards = {slot: _xi_card(slot) for slot in SLOTS}
    lineup = Lineup(name="U", formation="4-2-3-1",
                    slots=tuple((slot, cards[slot].id) for slot in SLOTS))
    return lineup, cards


def _candidate(card_id, name, position, *, price, face=STRONG, version="TOTS",
               alt=(), league="LX", nation="NX", club="CX"):
    return Card(id=card_id, player_name=name, version=version, ovr=90,
                position=position, alt_positions=alt, face=face,
                club=club, nation=nation, league=league, price=price)


def test_picks_best_affordable_swap():
    lineup, cards = _squad()
    pool = (
        _candidate("big--tots", "Big", "ST", price=200_000),     # too expensive net
        _candidate("good--tots", "Good", "ST", price=50_000),    # affordable, meta 90
    )
    # budget 60K; outgoing ST resale 9_500 -> net good = 40_500 ok; big = 190_500 no.
    plan = find_upgrades(lineup, cards, pool, budget=60_000, max_swaps=1)
    assert len(plan.swaps) == 1
    assert plan.swaps[0].in_id == "good--tots"
    assert plan.swaps[0].net_cost == 50_000 - 9_500
    assert plan.swaps[0].meta_delta == pytest.approx(20.0)   # 90 - 70
    assert plan.spent == plan.swaps[0].net_cost
    assert plan.score_after > plan.score_before


def test_self_upgrade_same_player_is_allowed():
    # Upgrading PST's base card to PST's TOTS is legal: the base leaves the XI.
    lineup, cards = _squad()
    pool = (_candidate("pst--tots", "PST", "ST", price=50_000),)
    plan = find_upgrades(lineup, cards, pool, budget=100_000, max_swaps=1)
    assert len(plan.swaps) == 1
    assert plan.swaps[0].in_id == "pst--tots"


def test_duplicate_other_player_is_blocked():
    # Candidate shares the name of the CURRENT RW (different slot) -> illegal XI.
    lineup, cards = _squad()
    pool = (_candidate("prw--tots", "PRW", "ST", price=50_000),)
    plan = find_upgrades(lineup, cards, pool, budget=100_000, max_swaps=1)
    assert plan.swaps == ()


def test_name_containment_variant_is_blocked():
    # "PRW dos Santos Aveiro" contains "PRW" (slug containment) -> blocked.
    lineup, cards = _squad()
    pool = (_candidate("prw-dos-santos-aveiro--tots", "PRW dos Santos Aveiro", "ST",
                       price=50_000),)
    plan = find_upgrades(lineup, cards, pool, budget=100_000, max_swaps=1)
    assert plan.swaps == ()


def test_out_of_position_candidate_excluded_alt_position_allowed():
    lineup, cards = _squad()
    pool = (
        _candidate("wrongpos--tots", "WP", "CB", price=10_000),               # CB can't play ST
        _candidate("altok--tots", "AO", "CAM", price=50_000, alt=("ST",)),     # alt ST ok
    )
    plan = find_upgrades(lineup, cards, pool, budget=100_000, max_swaps=1)
    assert len(plan.swaps) == 1
    assert plan.swaps[0].in_id == "altok--tots"


def test_chem_aware_choice_beats_raw_meta():
    # Two ST candidates: "meta-monster" (meta 90, alien league) vs "linker"
    # (meta 86, same league as 2 XI members -> league count 3 -> tier 1).
    # Current chem: all counts below thresholds -> 0.
    # Swap monster: meta +20, chem stays 0 -> delta 20.
    # Swap linker: meta +16, chem: Core league count 3 -> GK,RB,ST each +1 chem
    #   -> team chem 3 -> delta 16 + 3*3 = 25 > 20. Linker must win.
    lineup, cards = _squad()
    cards = dict(cards)
    cards["GK"] = Card(id="gk--base", player_name="PGK", version="base", ovr=80,
                       position="GK", face=WEAK, club="CGK", nation="NGK",
                       league="Core", price=10_000)
    cards["RB"] = Card(id="rb--base", player_name="PRB", version="base", ovr=80,
                       position="RB", face=WEAK, club="CRB", nation="NRB",
                       league="Core", price=10_000)
    monster_face = FaceStats(pac=90, sho=90, pas=90, dri=90, def_=90, phy=90)
    linker_face = FaceStats(pac=86, sho=86, pas=86, dri=86, def_=86, phy=86)
    pool = (
        _candidate("monster--tots", "Monster", "ST", price=50_000, face=monster_face,
                   league="Alien"),
        _candidate("linker--tots", "Linker", "ST", price=50_000, face=linker_face,
                   league="Core"),
    )
    plan = find_upgrades(lineup, cards, pool, budget=100_000, max_swaps=1)
    assert plan.swaps[0].in_id == "linker--tots"
    assert plan.swaps[0].chem_delta == 3


def test_swaps_cap_and_budget_depletion():
    lineup, cards = _squad()
    pool = tuple(
        _candidate(f"c{i}--tots", f"C{i}", "ST" if i == 0 else POSITIONS[SLOTS[i]],
                   price=40_000)
        for i in range(4)
    )
    # Each swap nets 40_000 - 9_500 = 30_500. Budget 70_000 affords 2.
    plan = find_upgrades(lineup, cards, pool, budget=70_000, max_swaps=3)
    assert len(plan.swaps) == 2
    assert plan.spent == 61_000
    assert plan.spent <= plan.budget


def test_no_positive_swap_returns_empty_plan():
    lineup, cards = _squad()
    pool = (_candidate("worse--tots", "Worse", "ST", price=1_000,
                       face=FaceStats(pac=50, sho=50, pas=50, dri=50, def_=50, phy=50)),)
    plan = find_upgrades(lineup, cards, pool, budget=100_000)
    assert plan.swaps == ()
    assert plan.score_after == plan.score_before


def test_unknown_resale_flagged():
    lineup, cards = _squad()
    cards = dict(cards)
    cards["ST"] = Card(id="st--base", player_name="PST", version="base", ovr=80,
                       position="ST", face=WEAK, club="CST", nation="NST",
                       league="LST", price=None)
    pool = (_candidate("good--tots", "Good", "ST", price=50_000),)
    plan = find_upgrades(lineup, cards, pool, budget=60_000, max_swaps=1)
    assert len(plan.swaps) == 1
    assert plan.swaps[0].net_cost == 50_000      # resale 0
    assert any("resale unknown" in w for w in plan.warnings)
