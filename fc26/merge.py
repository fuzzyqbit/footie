"""Merge rules for upserting cards.

Field-wise: the *primary* card's value wins unless it is missing
(None or empty tuple), in which case the *filler*'s value is used.
Primary is the incoming card, EXCEPT when the existing card came from
fut.gg and the incoming one did not — fut.gg data is richer and must
not be overwritten by a poorer source (spec merge rule).
"""

from __future__ import annotations

from dataclasses import fields

from .models import Card, FaceStats, FACE_STAT_NAMES


def _is_rich(card: Card) -> bool:
    return bool(card.source_url and "fut.gg" in card.source_url)


def _pick(primary_value, filler_value):
    if primary_value is None:
        return filler_value
    if isinstance(primary_value, tuple) and not primary_value:
        return filler_value
    return primary_value


def merge_cards(existing: Card, incoming: Card) -> Card:
    if _is_rich(existing) and not _is_rich(incoming):
        primary, filler = existing, incoming
    else:
        primary, filler = incoming, existing
    face = FaceStats(**{
        name: _pick(getattr(primary.face, name), getattr(filler.face, name))
        for name in FACE_STAT_NAMES
    })
    merged = {
        f.name: _pick(getattr(primary, f.name), getattr(filler, f.name))
        for f in fields(Card)
        if f.name != "face"
    }
    return Card(face=face, **merged)
