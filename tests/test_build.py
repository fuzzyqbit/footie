import pytest

from fc26.builder.build import BuildError, BuildResult, build_squad
from fc26.models import Card, FaceStats

FACE = FaceStats(pac=80, sho=80, pas=80, dri=80, def_=80, phy=80)
GOOD = FaceStats(pac=92, sho=92, pas=92, dri=92, def_=92, phy=92)

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


def test_build_seeds_cheapest_legal_xi():
    result = build_squad("4-2-3-1", _basic_pool(), budget=50_000)
    assert isinstance(result, BuildResult)
    assert len(result.slot_cards) == 11
    # 11 cheapest (CB/CDM need two distinct cards: 1_000 + 2_000... pool has
    # TWO 1_000 cards per CB/CDM (built per-slot) -> all 11 at 1_000 = 11_000)
    assert result.seed_cost == 11_000
    assert result.total_cost <= 50_000
    names = [c.player_name for c in result.slot_cards.values()]
    assert len(set(names)) == 11          # no duplicate real players


def test_build_improves_with_remaining_budget():
    pool = _basic_pool() + (
        _pool_card(999, "ST", price=20_000, name="Star", face=GOOD),
    )
    result = build_squad("4-2-3-1", pool, budget=40_000)
    assert result.slot_cards["ST"].player_name == "Star"
    assert result.total_cost <= 40_000
    assert result.improve_plan.spent > 0


def test_build_infeasible_budget_names_cheapest_cost():
    with pytest.raises(BuildError, match="11000"):
        build_squad("4-2-3-1", _basic_pool(), budget=5_000)


def test_build_unknown_formation_lists_available():
    with pytest.raises(BuildError, match="4-2-3-1"):
        build_squad("9-9-9", _basic_pool(), budget=50_000)


def test_build_league_filter_is_alias_aware():
    pool = _basic_pool()
    # all pool cards carry "Premier League"; filter with the fcratings variant
    result = build_squad("4-2-3-1", pool, budget=50_000,
                         league="English Premier League")
    assert len(result.slot_cards) == 11
    with pytest.raises(BuildError, match="Bundesliga"):
        build_squad("4-2-3-1", pool, budget=50_000, league="Bundesliga")


def test_build_missing_slot_candidate_errors():
    pool = tuple(c for c in _basic_pool() if c.position != "GK")
    with pytest.raises(BuildError, match="GK"):
        build_squad("4-2-3-1", pool, budget=50_000)


def test_build_excludes_unpriced_and_faceless_cards():
    pool = _basic_pool() + (
        Card(id="free--base", player_name="Freebie", version="base", ovr=99,
             position="ST", face=GOOD, price=None, club="CX", nation="NX", league="Premier League"),
        Card(id="noface--base", player_name="NoFace", version="base", ovr=99,
             position="ST", face=FaceStats(pac=99), price=100, club="CY", nation="NY",
             league="Premier League"),
    )
    result = build_squad("4-2-3-1", pool, budget=50_000)
    ids = {c.id for c in result.slot_cards.values()}
    assert "free--base" not in ids and "noface--base" not in ids
