"""FC 26 chemistry rules as verified constants.

Source: https://fifauteam.com/fc-26-chemistry/ (fetched 2026-06-10), cross-checked
against TheGamer's FC26 chemistry guide. Out-of-position players receive zero
chemistry and contribute nothing. Counts include the player themself.
"""

from __future__ import annotations

import re

from ..models import Card

# (players_needed, chem_points) — points granted to every in-position sharer
CLUB_TIERS = ((2, 1), (4, 2), (7, 3))
NATION_TIERS = ((2, 1), (5, 2), (8, 3))
LEAGUE_TIERS = ((3, 1), (5, 2), (8, 3))

MAX_PLAYER_CHEM = 3
ICON_NATION_WEIGHT = 2    # icons count twice toward their nation
HERO_LEAGUE_WEIGHT = 2    # heroes count twice toward their league
MANAGER_BONUS = 1         # single +1 for nation-or-league sharers

_ICON_WORD = re.compile(r"\bicon\b", re.IGNORECASE)
_HERO_WORD = re.compile(r"\bhero(es)?\b", re.IGNORECASE)


def is_icon(card: Card) -> bool:
    """Icons: flat 3 chem in position; 2x nation weight; +1 to every league.

    Heuristic until a schema flag exists: futbin gives icons the pseudo-league
    "Icons" and version strings like "Thunderstruck Icon".
    """
    if card.league == "Icons":
        return True
    return bool(_ICON_WORD.search(card.version))


def is_hero(card: Card) -> bool:
    """Heroes: flat 3 chem in position; 2x weight toward their own league."""
    return bool(_HERO_WORD.search(card.version))
