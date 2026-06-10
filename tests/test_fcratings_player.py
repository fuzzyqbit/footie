from pathlib import Path

import pytest

from fc26.ingest.fcratings_player import parse_player_page

FIXTURE = Path(__file__).parent / "fixtures" / "fcratings_mbappe.html"
URL = "https://www.fcratings.com/kylian-mbappe-231747"

GK_FIXTURE = Path(__file__).parent / "fixtures" / "fcratings_courtois.html"
GK_URL = "https://www.fcratings.com/thibaut-courtois-192119"


@pytest.fixture()
def mbappe_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parses_mbappe_player_page(mbappe_html):
    card = parse_player_page(mbappe_html, source_url=URL)
    assert card.player_name == "Kylian Mbappé"
    assert card.id == "kylian-mbappe--base"
    assert card.version == "base"
    assert card.ovr == 91
    assert card.position == "ST"
    assert card.nation == "France"
    assert card.club == "Real Madrid CF"
    assert card.league == "Spanish La Liga"
    assert card.face.pac == 96
    assert card.face.sho == 91
    assert card.face.pas == 81
    assert card.face.dri == 92
    assert card.face.def_ == 37
    assert card.face.phy == 76
    assert card.skill_moves == 5
    assert card.weak_foot == 4
    assert card.source_url == URL
    assert card.crawled_at is not None


def test_parses_gk_page_with_gk_stat_labels():
    """GK page has 7 attr-groups (Goalkeeping + 6 outfield labels).
    Ordinal mapping would shift all stats one slot right; label-based
    extraction must skip the Goalkeeping group and map Pace→pac etc.
    """
    card = parse_player_page(GK_FIXTURE.read_text(encoding="utf-8"), source_url=GK_URL)
    assert card.player_name == "Thibaut Courtois"
    assert card.position == "GK"
    assert card.ovr == 90
    # Outfield labels appear as slots 1-6 on a GK page (slot 0 = Goalkeeping).
    # Label-based extraction picks the correct values:
    assert card.face.pac == 86   # Pace
    assert card.face.sho == 89   # Shooting
    assert card.face.pas == 78   # Passing
    assert card.face.dri == 90   # Dribbling
    assert card.face.def_ == 46  # Defending
    assert card.face.phy == 88   # Physicality


def test_junk_page_raises_parse_error():
    from fc26.errors import ParseError

    with pytest.raises(ParseError, match="fcratings"):
        parse_player_page("<html><body>nope</body></html>", source_url=URL)
