"""Canonicalize league/nation/club strings across the DB's three vocabularies.

The DB mixes fcratings (enrichment), fut.gg (per-card adds), and futbin
(bulk expansion) display strings. All chemistry equality checks compare
canonical slugs produced here. Alias pairs were enumerated against the live
2,434-card DB during the phase-3 final review.
"""

from __future__ import annotations

from ..models import slugify

# slugified source string -> canonical slug
_LEAGUE_ALIASES = {
    "english-premier-league": "premier-league",
    "german-bundesliga": "bundesliga",
    "french-ligue-1": "ligue-1",
    "ligue-1-mcdonald-s": "ligue-1",
    "italian-serie-a": "serie-a",
    "serie-a-tim": "serie-a",
    "spanish-la-liga": "la-liga",
    "laliga-ea-sports": "la-liga",
    "usa-major-league-soccer": "mls",
    "roshn-saudi-league": "saudi-pro-league",
    "liga-portugal": "primeira-liga",
    "portuguese-primeira-liga": "primeira-liga",
}

# canonical slugs that are NOT real chemistry leagues
PSEUDO_LEAGUES = frozenset({"icons", "men-s-national"})

_NATION_ALIASES: dict[str, str] = {}   # byte-identical across sources today

_CLUB_SUFFIXES = ("-f-c", "-fc", "-cf")

# NOT aliased on purpose (verified different clubs despite similar names):
# levante-ud (men, La Liga) vs levante-lp (women, Liga F);
# independiente (ARG) vs independiente-dv (Independiente del Valle, ECU);
# inter-miami vs inter-milan; houston-dash vs houston-dynamo;
# newcastle-jets (AUS) vs newcastle-united; san-diego vs san-diego-wave
_CLUB_ALIASES = {
    "al-fayha-club": "al-fayha",
    "al-hilal-sfc": "al-hilal",
    "al-ittihad-club": "al-ittihad",
    "atletico-de-madrid": "atletico-madrid",
    "brighton-hove-albion": "brighton",
    "fc-bayern-munich": "fc-bayern-munchen",
    "manchester-utd": "manchester-united",
    "newcastle-utd": "newcastle-united",
    "sunderland-a": "sunderland",
}


def canonical_league(name: str) -> str:
    slug = slugify(name)
    return _LEAGUE_ALIASES.get(slug, slug)


def canonical_nation(name: str) -> str:
    slug = slugify(name)
    return _NATION_ALIASES.get(slug, slug)


def canonical_club(name: str) -> str:
    """Slugify, strip F.C./FC/CF suffixes, then apply abbreviation aliases."""
    slug = slugify(name)
    for suffix in _CLUB_SUFFIXES:
        if slug.endswith(suffix):
            slug = slug[: -len(suffix)]
            break
    return _CLUB_ALIASES.get(slug, slug)
