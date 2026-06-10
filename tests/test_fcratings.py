from pathlib import Path

import pytest

from fc26.errors import ParseError
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
    with pytest.raises(ParseError, match="fcratings"):
        parse_top100_page("<html><body>nope</body></html>", source_url=URL)


def test_too_few_rows_raises_parse_error():
    rows = "".join(
        f'<tr>'
        f'<td class="custom-rank text-center" data-sort-value="{i}">{i}</td>'
        f'<td class="custom-profile" data-sort-value="Player{i}">'
        f'<div class="custom-name">Player {i}</div>'
        f'</td>'
        f'<td class="custom-stat" data-sort-value="90">'
        f'<span>90</span>'
        f'</td>'
        f'<td class="custom-stat"><div>96</div></td>'
        f'<td class="custom-stat"><div>90</div></td>'
        f'<td class="custom-stat"><div>80</div></td>'
        f'<td class="custom-stat"><div>91</div></td>'
        f'<td class="custom-stat"><div>35</div></td>'
        f'<td class="custom-stat"><div>75</div></td>'
        f'<a class="custom-pos-badge">ST</a>'
        f'<a class="custom-roster-team">Club {i}</a>'
        f'</tr>'
        for i in range(1, 3)
    )
    html = f'<html><body><table class="custom-table">{rows}</table></body></html>'
    with pytest.raises(ParseError, match="yielded only"):
        parse_top100_page(html, source_url=URL)


@pytest.mark.live
def test_live_fetch_top100():
    from fc26.ingest.fcratings import fetch_top100

    cards = fetch_top100()
    assert len(cards) >= 50
