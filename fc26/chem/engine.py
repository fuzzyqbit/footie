"""Pure chemistry computation: Lineup + resolved Cards -> ChemReport."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..models import Card
from .aliases import PSEUDO_LEAGUES, canonical_club, canonical_league, canonical_nation
from .formations import slot_position
from .lineup import Lineup, Manager
from .rules import (
    CLUB_TIERS,
    HERO_LEAGUE_WEIGHT,
    ICON_NATION_WEIGHT,
    LEAGUE_TIERS,
    MANAGER_BONUS,
    MAX_PLAYER_CHEM,
    NATION_TIERS,
    is_hero,
    is_icon,
)


@dataclass(frozen=True)
class SlotChem:
    slot: str
    position: str
    card_id: str
    player_name: str
    version: str
    in_position: bool
    chem: int


@dataclass(frozen=True)
class TierStatus:
    kind: str              # "club" | "league" | "nation"
    name: str              # first-seen display string
    count: int             # weighted contributor count
    points: int
    next_tier_at: int | None


@dataclass(frozen=True)
class ChemReport:
    players: tuple[SlotChem, ...]
    team_total: int        # max 33
    tiers: tuple[TierStatus, ...]
    warnings: tuple[str, ...]


def _tier_points(count: int, tiers: tuple[tuple[int, int], ...]) -> int:
    points = 0
    for needed, pts in tiers:
        if count >= needed:
            points = pts
    return points


def _next_tier_at(count: int, tiers: tuple[tuple[int, int], ...]) -> int | None:
    for needed, _pts in tiers:
        if count < needed:
            return needed
    return None


def _manager_matches(manager: Manager | None, card: Card) -> bool:
    if manager is None:
        return False
    if manager.nation and card.nation and canonical_nation(manager.nation) == canonical_nation(card.nation):
        return True
    if manager.league and card.league and canonical_league(manager.league) == canonical_league(card.league):
        return True
    return False


def compute_chemistry(lineup: Lineup, slot_cards: dict[str, Card]) -> ChemReport:
    entries = []
    for slot_key, _card_id in lineup.slots:
        card = slot_cards[slot_key]
        position = slot_position(slot_key)
        in_position = position == card.position or position in card.alt_positions
        entries.append((slot_key, position, card, in_position))

    warnings: list[str] = []
    club_counts: Counter[str] = Counter()
    nation_counts: Counter[str] = Counter()
    league_counts: Counter[str] = Counter()
    icon_league_bonus = 0      # icons add +1 to EVERY league's count
    display: dict[tuple[str, str], str] = {}

    for _slot, _pos, card, in_position in entries:
        if not in_position:
            continue   # out-of-position players contribute nothing (verified rule)
        icon = is_icon(card)
        hero = is_hero(card)
        if card.club:
            key = canonical_club(card.club)
            club_counts[key] += 1
            display.setdefault(("club", key), card.club)
        if card.nation:
            key = canonical_nation(card.nation)
            nation_counts[key] += ICON_NATION_WEIGHT if icon else 1
            display.setdefault(("nation", key), card.nation)
        else:
            warnings.append(f"{card.id}: nation unknown - run `fc26 add <fut.gg URL>` to enrich")
        if icon:
            icon_league_bonus += 1
        elif card.league is None:
            warnings.append(f"{card.id}: league unknown - run `fc26 add <fut.gg URL>` to enrich")
        else:
            key = canonical_league(card.league)
            if key not in PSEUDO_LEAGUES:
                league_counts[key] += HERO_LEAGUE_WEIGHT if hero else 1
                display.setdefault(("league", key), card.league)

    def league_count(key: str) -> int:
        return league_counts.get(key, 0) + icon_league_bonus

    players: list[SlotChem] = []
    total = 0
    for slot_key, position, card, in_position in entries:
        if not in_position:
            chem = 0
        elif is_icon(card) or is_hero(card):
            chem = MAX_PLAYER_CHEM   # flat max in position (verified rule)
        else:
            chem = 0
            if card.club:
                chem += _tier_points(club_counts[canonical_club(card.club)], CLUB_TIERS)
            if card.nation:
                chem += _tier_points(nation_counts[canonical_nation(card.nation)], NATION_TIERS)
            if card.league:
                league_key = canonical_league(card.league)
                if league_key not in PSEUDO_LEAGUES:
                    chem += _tier_points(league_count(league_key), LEAGUE_TIERS)
            if _manager_matches(lineup.manager, card):
                chem += MANAGER_BONUS
            chem = min(chem, MAX_PLAYER_CHEM)
        total += chem
        players.append(SlotChem(
            slot=slot_key, position=position, card_id=card.id,
            player_name=card.player_name, version=card.version,
            in_position=in_position, chem=chem,
        ))

    tiers: list[TierStatus] = []
    for key, count in sorted(club_counts.items()):
        tiers.append(TierStatus("club", display[("club", key)], count,
                                _tier_points(count, CLUB_TIERS), _next_tier_at(count, CLUB_TIERS)))
    for key in sorted(league_counts):
        count = league_count(key)
        tiers.append(TierStatus("league", display[("league", key)], count,
                                _tier_points(count, LEAGUE_TIERS), _next_tier_at(count, LEAGUE_TIERS)))
    for key, count in sorted(nation_counts.items()):
        tiers.append(TierStatus("nation", display[("nation", key)], count,
                                _tier_points(count, NATION_TIERS), _next_tier_at(count, NATION_TIERS)))

    return ChemReport(tuple(players), total, tuple(tiers), tuple(warnings))
