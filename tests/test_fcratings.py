from pathlib import Path

import pytest

from fc26.ingest.fcratings import parse_top100_page

FIXTURE = Path(__file__).parent / "fixtures" / "fcratings_top100.html"
URL = "https://www.fcratings.com/lists/top-100-players"


@pytest.fixture()
def top100_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parses_100_base_cards(top100_html):
    cards = parse_top100_page(top100_html, source_url=URL)
    assert len(cards) == 100
    mbappe = cards[0]
    assert mbappe.player_name == "Kylian Mbappé"
    assert mbappe.ovr == 91
    assert mbappe.position == "ST"
    assert mbappe.club == "Real Madrid CF"
    assert mbappe.version == "base"
    assert mbappe.id == "kylian-mbappe--base"
    assert mbappe.source_url == URL
    rodri = next(c for c in cards if c.player_name == "Rodri")
    assert rodri.ovr == 89
    assert rodri.position == "CDM"


def test_unrecognized_page_raises_parse_error():
    from fc26.errors import ParseError

    with pytest.raises(ParseError, match="fcratings"):
        parse_top100_page("<html><body>nope</body></html>", source_url=URL)
