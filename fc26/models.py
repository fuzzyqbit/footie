"""Immutable card data model and boundary validation."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field

from .errors import FC26Error

VALID_POSITIONS = frozenset({
    "GK", "RB", "RWB", "CB", "LB", "LWB",
    "CDM", "CM", "CAM", "RM", "LM", "RW", "LW", "ST", "CF",
})

FACE_STAT_NAMES = ("pac", "sho", "pas", "dri", "def_", "phy")  # shared with merge.py - single source for the face-stat field list


class ValidationError(FC26Error, ValueError):
    """Card data failed boundary validation."""


@dataclass(frozen=True)
class FaceStats:
    pac: int | None = None
    sho: int | None = None
    pas: int | None = None
    dri: int | None = None
    def_: int | None = None
    phy: int | None = None


@dataclass(frozen=True)
class SubStats:
    acceleration: int | None = None
    sprint_speed: int | None = None
    positioning: int | None = None
    finishing: int | None = None
    shot_power: int | None = None
    long_shots: int | None = None
    volleys: int | None = None
    penalties: int | None = None
    vision: int | None = None
    crossing: int | None = None
    fk_accuracy: int | None = None
    short_passing: int | None = None
    long_passing: int | None = None
    curve: int | None = None
    agility: int | None = None
    balance: int | None = None
    reactions: int | None = None
    ball_control: int | None = None
    dribbling: int | None = None
    composure: int | None = None
    interceptions: int | None = None
    heading_accuracy: int | None = None
    def_awareness: int | None = None
    standing_tackle: int | None = None
    sliding_tackle: int | None = None
    jumping: int | None = None
    stamina: int | None = None
    strength: int | None = None
    aggression: int | None = None


@dataclass(frozen=True)
class Card:
    id: str
    player_name: str
    version: str
    ovr: int
    position: str
    alt_positions: tuple[str, ...] = ()
    face: FaceStats = field(default_factory=FaceStats)
    subs: SubStats | None = None
    playstyles: tuple[str, ...] = ()
    playstyles_plus: tuple[str, ...] = ()
    accelerate: str | None = None
    skill_moves: int | None = None
    weak_foot: int | None = None
    club: str | None = None
    league: str | None = None
    nation: str | None = None
    height_cm: int | None = None
    age: int | None = None
    price: int | None = None
    source_url: str | None = None
    crawled_at: str | None = None


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def make_card_id(player_name: str, version: str) -> str:
    return f"{slugify(player_name)}--{slugify(version)}"


def validate_card(card: Card) -> Card:
    errors: list[str] = []
    if not card.id:
        errors.append("id is empty")
    if not card.player_name.strip():
        errors.append("player_name is empty")
    if not card.version.strip():
        errors.append("version is empty")
    if not 1 <= card.ovr <= 99:
        errors.append(f"ovr {card.ovr} out of range 1-99")
    if card.position not in VALID_POSITIONS:
        errors.append(f"unknown position {card.position!r}")
    for pos in card.alt_positions:
        if pos not in VALID_POSITIONS:
            errors.append(f"unknown alt position {pos!r}")
    for name, value in asdict(card.face).items():
        if value is not None and not 1 <= value <= 99:
            errors.append(f"face.{name} {value} out of range 1-99")
    if card.subs is not None:
        for name, value in asdict(card.subs).items():
            if value is not None and not 1 <= value <= 99:
                errors.append(f"subs.{name} {value} out of range 1-99")
    for star_field in ("skill_moves", "weak_foot"):
        value = getattr(card, star_field)
        if value is not None and not 1 <= value <= 5:
            errors.append(f"{star_field} {value} out of range 1-5")
    if errors:
        raise ValidationError("; ".join(errors))
    return card
