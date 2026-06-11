from fc26.chem.aliases import (
    PSEUDO_LEAGUES,
    canonical_club,
    canonical_league,
    canonical_nation,
)
from fc26.chem.rules import (
    CLUB_TIERS,
    LEAGUE_TIERS,
    MAX_PLAYER_CHEM,
    NATION_TIERS,
    is_hero,
    is_icon,
)
from fc26.models import Card


def _card(**overrides) -> Card:
    base = dict(id="x--base", player_name="X", version="base", ovr=90, position="ST")
    base.update(overrides)
    return Card(**base)


def test_tier_constants_match_verified_rules():
    assert CLUB_TIERS == ((2, 1), (4, 2), (7, 3))
    assert NATION_TIERS == ((2, 1), (5, 2), (8, 3))
    assert LEAGUE_TIERS == ((3, 1), (5, 2), (8, 3))
    assert MAX_PLAYER_CHEM == 3


def test_icon_detection():
    assert is_icon(_card(version="Thunderstruck Icon"))
    assert is_icon(_card(version="Future Stars Icon"))
    assert is_icon(_card(version="base", league="Icons"))
    assert not is_icon(_card(version="TOTS", league="Premier League"))
    assert not is_icon(_card(version="Iconic Moment Lookalike"))  # word-boundary: "Iconic" != "Icon"


def test_hero_detection():
    assert is_hero(_card(version="Base Heroes"))
    assert is_hero(_card(version="Hero"))
    assert not is_hero(_card(version="TOTY"))


def test_league_aliases_resolve_real_db_pairs():
    # pinned to REAL strings present in data/players.json (both vocabularies)
    pairs = [
        ("Premier League", "English Premier League"),
        ("Bundesliga", "German Bundesliga"),
        ("Ligue 1 McDonald's", "French Ligue 1"),
        ("Serie A TIM", "Italian Serie A"),
        ("LALIGA EA SPORTS", "Spanish La Liga"),
        ("MLS", "USA Major League Soccer"),
        ("ROSHN Saudi League", "Saudi Pro League"),
    ]
    for left, right in pairs:
        assert canonical_league(left) == canonical_league(right), (left, right)


def test_pseudo_leagues():
    assert canonical_league("Icons") in PSEUDO_LEAGUES
    assert canonical_league("Men's National") in PSEUDO_LEAGUES
    assert canonical_league("Premier League") not in PSEUDO_LEAGUES


def test_club_aliases_resolve_real_db_pairs():
    pairs = [
        ("Arsenal", "Arsenal F.C."),
        ("Real Madrid", "Real Madrid CF"),
        ("Manchester City", "Manchester City F.C."),
        ("Juventus", "Juventus FC"),
        ("Aston Villa", "Aston Villa F.C."),
        ("Everton", "Everton F.C."),
        ("Celtic", "Celtic F.C."),
        ("Al Nassr", "Al-Nassr FC"),
        ("Athletic Club", "Athletic club"),
        ("Atlético de Madrid", "Atlético Madrid"),
        ("Newcastle United F.C.", "Newcastle Utd"),
        ("Al Fayha", "Al-Fayha Club"),
        ("Al Hilal", "Al Hilal SFC"),
        ("Al Ittihad", "Al-Ittihad Club"),
        ("Brighton", "Brighton & Hove Albion F.C."),
        ("FC Bayern München", "FC Bayern Munich"),
        ("Manchester United F.C.", "Manchester Utd"),
        ("Sunderland", "Sunderland A.F.C."),
    ]
    for left, right in pairs:
        assert canonical_club(left) == canonical_club(right), (left, right)


def test_similar_named_clubs_stay_distinct():
    assert canonical_club("Levante UD") != canonical_club("Levante LP")
    assert canonical_club("Independiente") != canonical_club("Independiente DV")
    assert canonical_club("Inter Miami") != canonical_club("Inter Milan")
    assert canonical_club("Newcastle Jets") != canonical_club("Newcastle United F.C.")


def test_nation_aliases_resolve_real_db_pairs():
    assert canonical_nation("Holland") == canonical_nation("Netherlands")
    assert canonical_nation("Czech Republic") == canonical_nation("Czechia")


def test_similar_nations_stay_distinct():
    assert canonical_nation("Australia") != canonical_nation("Austria")
    assert canonical_nation("Guinea") != canonical_nation("Guinea-Bissau")
    assert canonical_nation("Slovakia") != canonical_nation("Slovenia")


def test_unknown_strings_pass_through_slugified():
    assert canonical_league("Some New League 2027") == "some-new-league-2027"
    assert canonical_club("Brand New FC") == "brand-new"  # suffix stripped consistently
