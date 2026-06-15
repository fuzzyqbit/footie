from fc26.builder.value import DEFAULT_MAX_PRICE, value_picks
from fc26.models import Card, FaceStats

FACE = FaceStats(pac=90, sho=90, pas=90, dri=90, def_=90, phy=90)


def _card(i, *, ovr, price, position="ST", face=FACE, alt=()):
    return Card(id=f"p{i}--base", player_name=f"Player {i}", version="base",
                ovr=ovr, position=position, face=face, alt_positions=alt, price=price)


def test_ranks_by_quality_per_coin():
    # same quality, cheaper card wins
    cheap = _card(1, ovr=86, price=1_000)
    dear = _card(2, ovr=86, price=10_000)
    picks = value_picks([dear, cheap])
    assert [p.card.id for p in picks] == ["p1--base", "p2--base"]
    assert picks[0].value > picks[1].value


def test_min_ovr_floor_excludes_fodder():
    fodder = _card(1, ovr=80, price=200)       # cheap but below floor
    good = _card(2, ovr=85, price=5_000)
    picks = value_picks([fodder, good], min_ovr=83)
    assert [p.card.id for p in picks] == ["p2--base"]


def test_max_price_ceiling_excludes_expensive():
    cheap = _card(1, ovr=88, price=20_000)
    pricey = _card(2, ovr=99, price=2_000_000)
    picks = value_picks([cheap, pricey], max_price=50_000)
    assert [p.card.id for p in picks] == ["p1--base"]


def test_skips_cards_without_price():
    no_price = _card(1, ovr=90, price=None)
    priced = _card(2, ovr=85, price=3_000)
    picks = value_picks([no_price, priced])
    assert [p.card.id for p in picks] == ["p2--base"]


def test_pos_filter_matches_primary_or_alt():
    st = _card(1, ovr=86, price=2_000, position="ST")
    cb = _card(2, ovr=86, price=1_000, position="CB", alt=("CDM",))
    picks = value_picks([st, cb], pos="cdm")
    assert [p.card.id for p in picks] == ["p2--base"]


def test_quality_uses_ovr_when_face_missing():
    bare = _card(1, ovr=84, price=1_000, face=FaceStats())
    picks = value_picks([bare])
    assert picks[0].quality == 84.0


def test_per_tier_keeps_best_bargain_per_rating():
    # two 87s + two 88s; per_tier=1 keeps cheapest of each, ordered rating desc
    a87 = _card(1, ovr=87, price=1_000)
    b87 = _card(2, ovr=87, price=2_000)
    a88 = _card(3, ovr=88, price=3_000)
    b88 = _card(4, ovr=88, price=9_000)
    picks = value_picks([b88, a87, a88, b87], per_tier=1)
    assert [p.card.id for p in picks] == ["p3--base", "p1--base"]   # 88 then 87
    assert [p.card.ovr for p in picks] == [88, 87]


def test_default_max_price_is_cheap_ceiling():
    assert DEFAULT_MAX_PRICE == 50_000
