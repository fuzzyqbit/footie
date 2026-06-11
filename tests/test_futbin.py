from pathlib import Path

import pytest

from fc26.ingest.futbin import parse_futbin_page, parse_price

FIXTURE = Path(__file__).parent / "fixtures" / "futbin_list_87_p1.html"
URL = "https://www.futbin.com/players?player_rating=87-99&page=1"


@pytest.fixture()
def page_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parses_thirty_rows(page_html):
    cards = parse_futbin_page(page_html, source_url=URL)
    assert len(cards) == 30
    assert all(1 <= c.ovr <= 99 for c in cards)
    assert all(c.face.pac is not None for c in cards)


def test_dembele_toty_pinned_values(page_html):
    cards = parse_futbin_page(page_html, source_url=URL)
    dembele = next(c for c in cards if "dembele" in c.id and "toty" in c.id)
    assert dembele.player_name == "Ousmane Dembélé"
    assert dembele.version == "TOTY"
    assert dembele.ovr == 97
    assert dembele.position == "ST"
    assert dembele.alt_positions == ("CAM", "RW")
    assert dembele.face.pac == 97
    assert dembele.face.sho == 94
    assert dembele.face.pas == 90
    assert dembele.face.dri == 95
    assert dembele.face.def_ == 60
    assert dembele.face.phy == 77
    assert dembele.skill_moves == 5
    assert dembele.weak_foot == 5
    assert dembele.height_cm == 178
    assert dembele.accelerate == "Explosive"
    assert dembele.nation == "France"
    assert dembele.league == "Ligue 1 McDonald's"
    assert dembele.club == "Paris SG"
    assert dembele.price is not None and dembele.price > 100_000
    assert dembele.source_url == URL
    assert dembele.crawled_at is not None


def test_maradona_journey_of_nations_pinned(page_html):
    """Row 14: Maradona Journey of Nations — special version, Icon league, EA FC ICONS club."""
    cards = parse_futbin_page(page_html, source_url=URL)
    row = next(
        c for c in cards
        if "maradona" in c.id and "journey-of-nations" in c.id
    )
    assert row.player_name == "Maradona"
    assert row.version == "Journey of Nations"
    assert row.ovr == 97
    assert row.position == "CAM"
    assert row.alt_positions == ("ST",)
    assert row.nation == "Argentina"
    assert row.league == "Icons"
    assert row.club == "EA FC ICONS"
    assert row.face.pac == 97
    assert row.face.dri == 98


def test_parse_price_forms():
    assert parse_price("3.02M") == 3_020_000
    assert parse_price("750K") == 750_000
    assert parse_price("12,500") == 12_500
    assert parse_price("0") is None
    assert parse_price("") is None
    assert parse_price("-") is None
    assert parse_price("garbage") is None


def test_junk_page_raises_parse_error():
    from fc26.errors import ParseError

    with pytest.raises(ParseError, match="futbin"):
        parse_futbin_page("<html><body>nope</body></html>", source_url=URL)
