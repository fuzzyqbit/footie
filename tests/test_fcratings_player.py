from pathlib import Path

import pytest

from fc26.ingest.fcratings_player import parse_player_page

FIXTURE = Path(__file__).parent / "fixtures" / "fcratings_mbappe.html"
URL = "https://www.fcratings.com/kylian-mbappe-231747"


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


def test_junk_page_raises_parse_error():
    from fc26.errors import ParseError

    with pytest.raises(ParseError, match="fcratings"):
        parse_player_page("<html><body>nope</body></html>", source_url=URL)
