from pathlib import Path

import pytest

from fc26.ingest.futgg import parse_futgg_card

FIXTURE = Path(__file__).parent / "fixtures" / "futgg_rodri_ptg.html"
URL = "https://www.fut.gg/players/231866-rodri/26-84117946/"


@pytest.fixture()
def rodri_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parses_known_rodri_ptg_values(rodri_html):
    card = parse_futgg_card(rodri_html, source_url=URL)
    assert card.player_name == "Rodri"
    assert card.ovr == 96
    assert card.position == "CDM"
    assert card.face.pac == 90
    assert card.face.sho == 88
    assert card.face.pas == 96
    assert card.face.dri == 95
    assert card.face.def_ == 94
    assert card.face.phy == 92
    assert card.accelerate == "Controlled"
    assert card.skill_moves == 5
    assert card.weak_foot == 5
    assert card.nation == "Spain"
    assert card.league == "Premier League"
    assert "Manchester City" in (card.club or "")
    assert card.subs is not None
    assert card.subs.acceleration == 91
    assert card.subs.sprint_speed == 90
    assert card.subs.standing_tackle == 95
    assert card.subs.interceptions == 95
    # live fut.gg ground truth (verified 2026-06-10): four PlayStyles+;
    # Incisive Pass and Press Proven are plain PlayStyles on this card
    assert card.playstyles_plus == (
        "Intercept", "Anticipate", "Pinged Pass", "Tiki Taka",
    )
    assert card.playstyles == (
        "Power Shot", "Incisive Pass", "Long Ball", "Aerial Fortress", "Technical", "Press Proven", "Bruiser",
    )
    assert card.source_url == URL
    assert card.crawled_at is not None


def test_unrecognized_page_raises_parse_error():
    from fc26.errors import ParseError

    with pytest.raises(ParseError, match="fut.gg"):
        parse_futgg_card("<html><body>nothing here</body></html>", source_url="https://www.fut.gg/x/")


@pytest.mark.live
def test_live_fetch_rodri_ptg():
    from fc26.ingest.futgg import fetch_futgg_card

    card = fetch_futgg_card(URL)
    assert card.player_name == "Rodri"
    assert card.ovr == 96
