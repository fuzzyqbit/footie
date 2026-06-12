import pytest

from fc26.builder.boost import FACE_CONSTITUENTS, BoostResult, boosted_stats
from fc26.models import Card, FaceStats, SubStats

TESTSTYLE = {3: {"acceleration": 10, "sprint_speed": 6, "finishing": 8},
             2: {"acceleration": 6, "sprint_speed": 4, "finishing": 5},
             1: {"acceleration": 3, "sprint_speed": 2, "finishing": 2}}


@pytest.fixture(autouse=True)
def synthetic_style(monkeypatch):
    monkeypatch.setitem(
        __import__("fc26.chem.styles", fromlist=["STYLE_BOOSTS"]).STYLE_BOOSTS,
        "teststyle", TESTSTYLE,
    )


def _card(subs=None, face=None):
    return Card(id="x--base", player_name="X", version="base", ovr=88, position="ST",
                face=face or FaceStats(pac=80, sho=80, pas=80, dri=80, def_=80, phy=80),
                subs=subs)


def test_face_constituents_cover_all_29_subs_once():
    seen = [s for subs in FACE_CONSTITUENTS.values() for s in subs]
    assert len(seen) == len(set(seen)) == 29
    assert set(FACE_CONSTITUENTS) == {"pac", "sho", "pas", "dri", "def_", "phy"}


def test_no_style_or_zero_chem_is_noop():
    card = _card()
    for style, chem in ((None, 3), ("teststyle", 0)):
        result = boosted_stats(card, style, chem)
        assert result.face == card.face
        assert result.precision == "none"


def test_approx_tier_face_math():
    # no subs. teststyle@3: PAC constituents accel(+10)+sprint(+6) -> mean 8
    # SHO constituents: only finishing(+8) of 6 subs -> mean 8/6 = 1.333 -> rounds to 1
    card = _card()
    result = boosted_stats(card, "teststyle", 3)
    assert result.precision == "approx"
    assert result.face.pac == 88          # 80 + 8
    assert result.face.sho == 81          # 80 + round(8/6)
    assert result.face.pas == 80


def test_exact_tier_subs_boosted_and_capped():
    subs = SubStats(acceleration=95, sprint_speed=90, finishing=70)
    card = _card(subs=subs)
    result = boosted_stats(card, "teststyle", 3)
    assert result.precision == "subs"
    assert result.subs.acceleration == 99   # 95+10 capped
    assert result.subs.sprint_speed == 96
    assert result.subs.finishing == 78
    assert result.face.pac == 88            # face still mean-approximated: 80+8


def test_chem_level_changes_deltas():
    card = _card()
    assert boosted_stats(card, "teststyle", 1).face.pac == 83   # 80 + round((3+2)/2)
    assert boosted_stats(card, "teststyle", 2).face.pac == 85   # 80 + round((6+4)/2)


def test_unknown_style_raises():
    from fc26.errors import FC26Error

    with pytest.raises(FC26Error, match="nosuchstyle"):
        boosted_stats(_card(), "nosuchstyle", 3)


def test_face_cap_99():
    card = _card(face=FaceStats(pac=95, sho=95, pas=95, dri=95, def_=95, phy=95))
    assert boosted_stats(card, "teststyle", 3).face.pac == 99   # 95+8 capped
