"""JSON card repository with atomic writes."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .errors import DatabaseError
from .merge import merge_cards
from .models import Card, FaceStats, SubStats, validate_card

SCHEMA_VERSION = 1


def card_to_dict(card: Card) -> dict[str, Any]:
    data = asdict(card)
    data["alt_positions"] = list(card.alt_positions)
    data["playstyles"] = list(card.playstyles)
    data["playstyles_plus"] = list(card.playstyles_plus)
    return data


def card_from_dict(data: dict[str, Any]) -> Card:
    payload = dict(data)
    payload["face"] = FaceStats(**payload.get("face") or {})
    subs = payload.get("subs")
    payload["subs"] = SubStats(**subs) if subs else None
    payload["alt_positions"] = tuple(payload.get("alt_positions") or ())
    payload["playstyles"] = tuple(payload.get("playstyles") or ())
    payload["playstyles_plus"] = tuple(payload.get("playstyles_plus") or ())
    return Card(**payload)


class CardRepository:
    """Load/save/search/upsert cards in a JSON file."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def find_all(self) -> tuple[Card, ...]:
        if not self._path.exists():
            return ()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return tuple(card_from_dict(item) for item in data["cards"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise DatabaseError(f"cannot read {self._path}: {exc}") from exc

    def find_by_id(self, card_id: str) -> Card | None:
        for card in self.find_all():
            if card.id == card_id:
                return card
        return None

    def search(self, text: str) -> tuple[Card, ...]:
        needle = text.lower()
        return tuple(
            card
            for card in self.find_all()
            if needle in card.player_name.lower()
            or needle in (card.club or "").lower()
            or needle in card.version.lower()
        )

    def upsert(self, card: Card) -> Card:
        validate_card(card)
        cards = {existing.id: existing for existing in self.find_all()}
        if card.id in cards:
            card = merge_cards(cards[card.id], card)
        cards[card.id] = card
        self._save(tuple(cards.values()))
        return card

    def _save(self, cards: tuple[Card, ...]) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "cards": [card_to_dict(card) for card in sorted(cards, key=lambda c: c.id)],
        }
        _atomic_write(self._path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
