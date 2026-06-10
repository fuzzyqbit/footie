from pathlib import Path

import pytest

from fc26.ingest.discovery import find_player_link, parse_all_clubs

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def all_clubs_html() -> str:
    return (FIXTURES / "fcratings_all_clubs.html").read_text(encoding="utf-8")


@pytest.fixture()
def dortmund_html() -> str:
    return (FIXTURES / "fcratings_club_dortmund.html").read_text(encoding="utf-8")


def test_parse_all_clubs_maps_names_and_slug_aliases(all_clubs_html):
    clubs = parse_all_clubs(all_clubs_html)
    assert clubs["Borussia Dortmund"].startswith("https://www.fcratings.com/clubs/borussia-dortmund-")
    assert clubs["borussia-dortmund"] == clubs["Borussia Dortmund"]
    assert len(set(clubs.values())) >= 50


def test_find_player_link_exact_slug_match(dortmund_html):
    url = find_player_link(dortmund_html, "Karim Adeyemi")
    assert url == "https://www.fcratings.com/karim-adeyemi-251852"


def test_find_player_link_absent_returns_none(dortmund_html):
    assert find_player_link(dortmund_html, "Lionel Messi") is None


def test_find_player_link_ambiguous_returns_none():
    html = (
        '<a href="https://www.fcratings.com/john-smith-11111">x</a>'
        '<a href="https://www.fcratings.com/john-smith-22222">y</a>'
    )
    assert find_player_link(html, "John Smith") is None


def test_parse_all_clubs_prefers_mens_club_on_gender_duplicate(all_clubs_html):
    clubs = parse_all_clubs(all_clubs_html)
    assert clubs["Athletic club"] == "https://www.fcratings.com/clubs/athletic-club-448"


def test_parse_all_clubs_drops_colliding_display_names():
    html = (
        '<div data-gender="0"><a href="https://www.fcratings.com/clubs/x-club-1">X Club</a></div>'
        '<div data-gender="0"><a href="https://www.fcratings.com/clubs/x-club-2">X Club</a></div>'
        '<div data-gender="0"><a href="https://www.fcratings.com/clubs/liverpool-9">Liverpool</a></div>'
    )
    clubs = parse_all_clubs(html)
    assert "X Club" not in clubs and "x-club" not in clubs
    assert clubs["Liverpool"] == "https://www.fcratings.com/clubs/liverpool-9"


def test_parse_all_clubs_ignores_womens_clubs():
    html = '<div data-gender="1"><a href="https://www.fcratings.com/clubs/w-club-5">W Club</a></div>'
    assert parse_all_clubs(html) == {}


def test_parse_all_clubs_ignores_anchors_without_text():
    html = '<div data-gender="0"><a href="https://www.fcratings.com/clubs/empty-1234"></a></div>'
    assert parse_all_clubs(html) == {}


def test_parse_all_clubs_same_club_twice_is_not_a_collision():
    html = (
        '<div data-gender="0"><a href="https://www.fcratings.com/clubs/liverpool-9">Liverpool</a></div>'
        '<div data-gender="0"><a href="https://www.fcratings.com/clubs/liverpool-9">Liverpool</a></div>'
    )
    clubs = parse_all_clubs(html)
    assert clubs["Liverpool"] == "https://www.fcratings.com/clubs/liverpool-9"
