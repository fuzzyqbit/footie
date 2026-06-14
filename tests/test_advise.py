import json
from dataclasses import asdict, replace

import pytest

from fc26.builder.advise import (
    Advice,
    SlotNote,
    StyleAdvice,
    TierLeverage,
    advise_squad,
)
from fc26.builder.boost import boosted_stats
from fc26.builder.meta import meta_score
from fc26.chem.lineup import Lineup
from fc26.chem.styles import available_styles
from fc26.models import Card, FaceStats

FACE = FaceStats(pac=80, sho=80, pas=80, dri=80, def_=80, phy=80)
SLOTS = ("GK", "RB", "CB1", "CB2", "LB", "CDM1", "CDM2", "CAM", "RW", "LW", "ST")
POS_FOR_SLOT = {"GK": "GK", "RB": "RB", "CB1": "CB", "CB2": "CB", "LB": "LB",
                "CDM1": "CDM", "CDM2": "CDM", "CAM": "CAM", "RW": "RW", "LW": "LW", "ST": "ST"}


def _xi():
    """11 in-position cards, distinct club/nation, all Premier League (-> 33 chem)."""
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


def test_advise_returns_structured_advice():
    advice = advise_squad(*_xi())
    assert isinstance(advice, Advice)
    assert advice.formation == "4-2-3-1"
    assert advice.team_chem == 33
    assert advice.out_of_position == ()


def test_out_of_position_player_is_flagged():
    lineup, cards = _xi()
    cards = dict(cards)
    cards["ST"] = Card(id="keeper--base", player_name="Keeper", version="base", ovr=80,
                       position="GK", club="CK", nation="NK", league="Premier League", face=FACE)
    advice = advise_squad(lineup, cards)
    flagged = [n for n in advice.out_of_position if n.slot == "ST"]
    assert flagged and isinstance(flagged[0], SlotNote)
    assert flagged[0].chem == 0
    assert "ST" in flagged[0].reason


def test_tier_leverage_lists_groups_near_next_tier_sorted():
    advice = advise_squad(*_xi())
    assert advice.tier_leverage
    assert all(isinstance(lv, TierLeverage) and lv.needed > 0 for lv in advice.tier_leverage)
    # distinct clubs/nations each sit one short of the 2-count tier
    assert all(lv.needed == 1 for lv in advice.tier_leverage)
    needs = [lv.needed for lv in advice.tier_leverage]
    assert needs == sorted(needs)
    # the fully-stacked Premier League (count 11, maxed) is not a leverage point
    assert all(not (lv.kind == "league") for lv in advice.tier_leverage)


def test_weakest_slots_are_lowest_meta_first():
    lineup, cards = _xi()
    cards = dict(cards)
    cards["CB1"] = replace(cards["CB1"], face=FaceStats(pac=40, sho=40, pas=40, dri=40, def_=40, phy=40))
    advice = advise_squad(lineup, cards)
    assert advice.weakest_slots
    assert advice.weakest_slots[0].slot == "CB1"
    metas = [n.meta for n in advice.weakest_slots]
    assert metas == sorted(metas)


def test_best_style_is_real_and_maximizes_meta():
    lineup, cards = _xi()
    advice = advise_squad(lineup, cards)
    st = next(s for s in advice.style_advice if s.slot == "ST")
    assert isinstance(st, StyleAdvice)
    assert st.chem == 3
    assert st.recommended_style in available_styles()
    assert st.meta_gain > 0
    # it really is the argmax over all styles at chem 3
    card = cards["ST"]
    base = meta_score(card, "ST")
    best = max(meta_score(replace(card, face=boosted_stats(card, sty, 3).face), "ST")
               for sty in available_styles())
    assert st.meta_gain == pytest.approx(best - base)


def test_gk_gets_no_style_pick():
    advice = advise_squad(*_xi())
    gk = next(s for s in advice.style_advice if s.slot == "GK")
    assert gk.recommended_style is None
    assert gk.note and "GK" in gk.note


def test_zero_chem_slot_style_is_inert():
    lineup, cards = _xi()
    cards = dict(cards)
    # out-of-position outfield card -> 0 chem -> style inert
    cards["ST"] = Card(id="oop--base", player_name="OOP", version="base", ovr=80,
                       position="CB", club="CO", nation="NO", league="Premier League", face=FACE)
    advice = advise_squad(lineup, cards)
    st = next(s for s in advice.style_advice if s.slot == "ST")
    assert st.chem == 0
    assert st.recommended_style is None
    assert st.note and "chem" in st.note.lower()


def test_advice_is_json_serializable():
    advice = advise_squad(*_xi())
    blob = json.dumps(asdict(advice))
    assert json.loads(blob)["team_chem"] == 33
