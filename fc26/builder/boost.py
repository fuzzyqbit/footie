"""Boosted-stats engine: apply a chem style at a chem level to a card.

Faces are ALWAYS estimates (EA's true face weights are internal): face delta =
mean of the style's deltas over that face's constituent subs (unboosted = 0),
rounded half-up, capped 99. When the card carries sub-stats, each sub is
boosted exactly (capped 99) - precision tier "subs"; otherwise "approx".
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..chem.styles import STYLE_BOOSTS, available_styles
from ..errors import FC26Error
from ..models import Card, FaceStats, SubStats

FACE_CONSTITUENTS: dict[str, tuple[str, ...]] = {
    "pac": ("acceleration", "sprint_speed"),
    "sho": ("positioning", "finishing", "shot_power", "long_shots", "volleys", "penalties"),
    "pas": ("vision", "crossing", "fk_accuracy", "short_passing", "long_passing", "curve"),
    "dri": ("agility", "balance", "reactions", "ball_control", "dribbling", "composure"),
    "def_": ("interceptions", "heading_accuracy", "def_awareness", "standing_tackle", "sliding_tackle"),
    "phy": ("jumping", "stamina", "strength", "aggression"),
}


class StyleError(FC26Error):
    """Unknown chemistry style."""


@dataclass(frozen=True)
class BoostResult:
    face: FaceStats
    subs: SubStats | None
    precision: str          # "subs" | "approx" | "none"
    style: str | None
    chem_level: int


def _round_half_up(value: float) -> int:
    return int(value + 0.5)


def boosted_stats(card: Card, style: str | None, chem_level: int) -> BoostResult:
    if style is None or chem_level <= 0:
        return BoostResult(card.face, card.subs, "none", style, chem_level)
    if style not in STYLE_BOOSTS:
        raise StyleError(
            f"unknown style {style!r} - available: {', '.join(available_styles())}"
        )
    boosts = STYLE_BOOSTS[style][chem_level]

    face_values = {}
    for face_name, constituents in FACE_CONSTITUENTS.items():
        current = getattr(card.face, face_name)
        if current is None:
            face_values[face_name] = None
            continue
        mean_delta = sum(boosts.get(sub, 0) for sub in constituents) / len(constituents)
        face_values[face_name] = min(99, current + _round_half_up(mean_delta))
    face = FaceStats(**face_values)

    if card.subs is None:
        return BoostResult(face, None, "approx", style, chem_level)
    boosted = {
        name: (min(99, value + boosts.get(name, 0)) if value is not None else None)
        for name, value in card.subs.__dict__.items()
    }
    return BoostResult(face, SubStats(**boosted), "subs", style, chem_level)
