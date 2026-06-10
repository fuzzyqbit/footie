"""Seed the card DB from this repo's crawled markdown docs (08, 10, 11)."""

from __future__ import annotations

from ..models import Card, FaceStats, make_card_id
from .markdown import extract_tables

TOP100_HEADERS = {"Rank", "Player", "OVR", "Pos", "Club"}
MASTER_HEADERS = {"PAC", "Player", "Pos", "OVR", "Club"}
SPECIAL_HEADERS = {"Player", "Card Version", "OVR", "Pos", "PAC", "SHO", "PAS", "DRI", "DEF", "PHY"}


def _split_positions(raw: str) -> tuple[str, tuple[str, ...]]:
    parts = [part.strip() for part in raw.split("/") if part.strip()]
    return parts[0], tuple(parts[1:])


def _tables_matching(markdown: str, required_headers: set[str]) -> list[list[dict[str, str]]]:
    return [
        table for table in extract_tables(markdown)
        if required_headers <= set(table[0].keys())
    ]


def parse_top100(markdown: str) -> list[Card]:
    cards: list[Card] = []
    for table in _tables_matching(markdown, TOP100_HEADERS):
        for row in table:
            if not row.get("OVR", "").strip().lstrip("-").isdigit():
                continue
            position, alts = _split_positions(row["Pos"])
            cards.append(Card(
                id=make_card_id(row["Player"], "base"),
                player_name=row["Player"],
                version="base",
                ovr=int(row["OVR"]),
                position=position,
                alt_positions=alts,
                club=row["Club"] or None,
            ))
    return cards


def parse_master_pace_list(markdown: str) -> list[Card]:
    cards: list[Card] = []
    for table in _tables_matching(markdown, MASTER_HEADERS):
        if "Source" in table[0]:  # the XI table, not the master list
            continue
        for row in table:
            if not row.get("PAC", "").strip().lstrip("-").isdigit():
                continue
            if not row.get("OVR", "").strip().lstrip("-").isdigit():
                continue
            position, alts = _split_positions(row["Pos"])
            cards.append(Card(
                id=make_card_id(row["Player"], "base"),
                player_name=row["Player"],
                version="base",
                ovr=int(row["OVR"]),
                position=position,
                alt_positions=alts,
                club=row["Club"] or None,
                face=FaceStats(pac=int(row["PAC"])),
            ))
    return cards


def _parse_stars(raw: str) -> tuple[int | None, int | None]:
    parts = [part.strip() for part in raw.split("/")]
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def parse_special_cards(markdown: str) -> list[Card]:
    cards: list[Card] = []
    for table in _tables_matching(markdown, SPECIAL_HEADERS):
        if "Rank" in table[0]:  # the pace-ranking table, not the tracker
            continue
        for row in table:
            if not row.get("OVR", "").strip().lstrip("-").isdigit():
                continue
            if not row.get("PAC", "").strip().lstrip("-").isdigit():
                continue
            position, alts = _split_positions(row["Pos"])
            skill_moves, weak_foot = _parse_stars(row.get("SM/WF", ""))
            playstyles_plus = tuple(
                part.strip()
                for part in row.get("Key PlayStyles+", "").split(",")
                if part.strip()
            )
            cards.append(Card(
                id=make_card_id(row["Player"], row["Card Version"]),
                player_name=row["Player"],
                version=row["Card Version"],
                ovr=int(row["OVR"]),
                position=position,
                alt_positions=alts,
                face=FaceStats(
                    pac=int(row["PAC"]),
                    sho=int(row["SHO"]),
                    pas=int(row["PAS"]),
                    dri=int(row["DRI"]),
                    def_=int(row["DEF"]),
                    phy=int(row["PHY"]),
                ),
                accelerate=row.get("AcceleRATE") or None,
                skill_moves=skill_moves,
                weak_foot=weak_foot,
                playstyles_plus=playstyles_plus,
            ))
    return cards


def seed_cards(top100_md: str, master_md: str, specials_md: str) -> list[Card]:
    """All seed cards, in upsert order: top-100 first, then pace (adds PAC), then specials."""
    return [
        *parse_top100(top100_md),
        *parse_master_pace_list(master_md),
        *parse_special_cards(specials_md),
    ]
