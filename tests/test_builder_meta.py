import pytest

from fc26.builder.market import BudgetError, net_cost, parse_budget, resale_value
from fc26.builder.meta import CHEM_WEIGHT, META_WEIGHTS, meta_score
from fc26.models import VALID_POSITIONS, Card, FaceStats


def test_every_position_has_weights_summing_to_one():
    assert set(META_WEIGHTS) == set(VALID_POSITIONS)
    for position, weights in META_WEIGHTS.items():
        assert len(weights) == 6, position
        assert abs(sum(weights) - 1.0) < 1e-9, position


def test_meta_score_hand_checked_striker():
    # ST weights (.30, .35, .05, .20, .00, .10) on 90/80/70/85/40/75:
    # 27 + 28 + 3.5 + 17 + 0 + 7.5 = 83.0
    card = Card(id="s--base", player_name="S", version="base", ovr=88, position="ST",
                face=FaceStats(pac=90, sho=80, pas=70, dri=85, def_=40, phy=75))
    assert meta_score(card, "ST") == pytest.approx(83.0)


def test_meta_score_position_changes_score():
    card = Card(id="s--base", player_name="S", version="base", ovr=88, position="ST",
                face=FaceStats(pac=90, sho=80, pas=70, dri=85, def_=40, phy=75))
    assert meta_score(card, "CB") != meta_score(card, "ST")


def test_meta_score_missing_face_stat_returns_none():
    card = Card(id="s--base", player_name="S", version="base", ovr=88, position="ST",
                face=FaceStats(pac=90))
    assert meta_score(card, "ST") is None


def test_chem_weight_is_visible_constant():
    assert CHEM_WEIGHT == 3.0


def test_parse_budget_forms():
    assert parse_budget("100K") == 100_000
    assert parse_budget("1.2M") == 1_200_000
    assert parse_budget("50000") == 50_000
    with pytest.raises(BudgetError, match="garbage"):
        parse_budget("garbage")


def test_parse_budget_tolerates_millions_typed_loosely():
    # Forms a user with a big bank actually types for "5 million coins".
    assert parse_budget("5 000 000") == 5_000_000
    assert parse_budget("5,000,000") == 5_000_000
    assert parse_budget("5 M") == 5_000_000
    assert parse_budget("5m") == 5_000_000
    assert parse_budget("$5M") == 5_000_000
    assert parse_budget("5M coins") == 5_000_000


def test_resale_and_net_cost_with_five_percent_tax():
    assert resale_value(100_000) == 95_000
    assert resale_value(None) == 0
    assert net_cost(150_000, 100_000) == 55_000     # 150000 - 95000
    assert net_cost(50_000, 100_000) == -45_000     # downgrade-for-profit allowed
    assert net_cost(150_000, None) == 150_000       # unknown resale -> 0
