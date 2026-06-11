from pathlib import Path

import pytest

from fc26.errors import ParseError
from fc26.ingest.futbin import parse_futbin_page, parse_price, _clean_alt_positions, _normalize_version
from fc26.models import VALID_POSITIONS

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


def test_base_cards_map_to_version_base():
    """Base cards with 'Normal' badge must map to version 'base', not 'Normal'."""
    html = (Path(__file__).parent / "fixtures" / "futbin_list_87only_p1.html").read_text(encoding="utf-8")
    cards = parse_futbin_page(html, source_url="https://www.futbin.com/players?player_rating=87-87&page=1")
    base_cards = [c for c in cards if c.version == "base"]
    assert base_cards, "fixture contains Normal rows; they must map to version 'base'"
    assert all(c.id.endswith("--base") for c in base_cards)
    assert not any(c.version == "Normal" for c in cards)


def test_majority_bad_rows_raises_parse_error():
    html = (
        '<table>'
        '<tr class="player-row"><td>bad1</td></tr>'
        '<tr class="player-row"><td>bad2</td></tr>'
        '<tr class="player-row"><td>bad3</td></tr>'
        '</table>'
    )
    with pytest.raises(ParseError, match="futbin"):
        parse_futbin_page(html, source_url="http://test")


def test_clean_alt_positions_drops_overflow_tokens():
    """futbin appends '+N' tokens when a card has more alt positions than UI can display."""
    assert _clean_alt_positions(["CAM", "+1", "RW", ""]) == ("CAM", "RW")


def test_alt_position_overflow_token_is_dropped_invariant(page_html):
    """All parsed alt-positions must be in VALID_POSITIONS (regression for futbin '+1' token)."""
    cards = parse_futbin_page(page_html, source_url=URL)
    for card in cards:
        assert all(p in VALID_POSITIONS for p in card.alt_positions), (
            f"{card.id} has invalid alt position(s): {card.alt_positions}"
        )


def test_version_badge_mapping_is_case_insensitive():
    assert _normalize_version("Normal") == "base"
    assert _normalize_version("normal") == "base"
    assert _normalize_version("NORMAL") == "base"
    assert _normalize_version("  Normal ") == "base"
    assert _normalize_version("TOTY") == "TOTY"
    assert _normalize_version("Base Heroes") == "Base Heroes"  # hero class, not a base card
    assert _normalize_version("") == "base"
