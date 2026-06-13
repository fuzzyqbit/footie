"""Lineup model: load and validate squad JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..db import CardRepository
from ..errors import FC26Error
from ..models import Card
from .formations import FORMATIONS
from .styles import available_styles


class LineupError(FC26Error):
    """A squad file failed validation; message lists ALL problems."""


@dataclass(frozen=True)
class Manager:
    league: str | None = None
    nation: str | None = None


@dataclass(frozen=True)
class Lineup:
    name: str
    formation: str
    slots: tuple[tuple[str, str], ...]   # (slot_key, card_id) in formation order
    manager: Manager | None = None
    styles: dict[str, str] = field(default_factory=dict)


def lineup_from_dict(data: dict, name: str = "inline") -> Lineup:
    """Parse a squad dict (same shape as squad JSON files) into a Lineup.

    Raises LineupError listing ALL problems found.
    """
    errors: list[str] = []
    formation = data.get("formation", "")
    if formation not in FORMATIONS:
        available = ", ".join(sorted(FORMATIONS))
        raise LineupError(
            f"unknown formation {formation!r} - available: {available}"
        )

    expected = FORMATIONS[formation]
    xi = data.get("starting_xi") or {}
    missing = [slot for slot in expected if slot not in xi]
    extra = [slot for slot in xi if slot not in expected]
    if missing:
        errors.append(f"missing slots: {', '.join(missing)}")
    if extra:
        errors.append(f"unknown slots for {formation}: {', '.join(extra)}")

    # Normalize slot values: string -> id, dict -> {"id": ..., "style": ...}
    # Collect ids for duplicate checking and styles for the Lineup field.
    slot_ids: dict[str, str] = {}
    slot_styles: dict[str, str] = {}
    for slot, value in xi.items():
        if isinstance(value, dict):
            slot_ids[slot] = value["id"]
            raw_style = value.get("style")
            if raw_style is not None:
                slot_styles[slot] = str(raw_style).lower()
        else:
            slot_ids[slot] = value

    # Validate styles
    valid = available_styles()
    for slot, style in slot_styles.items():
        if style not in valid:
            errors.append(
                f"unknown style {style!r} for slot {slot} - available: {', '.join(valid)}"
            )

    ids = [slot_ids[slot] for slot in expected if slot in slot_ids]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        errors.append(f"duplicate cards across slots: {', '.join(duplicates)}")

    if errors:
        raise LineupError("; ".join(errors))

    manager_data = data.get("manager")
    manager = None
    if manager_data:
        manager = Manager(
            league=manager_data.get("league"),
            nation=manager_data.get("nation"),
        )

    return Lineup(
        name=data.get("name", name),
        formation=formation,
        slots=tuple((slot, slot_ids[slot]) for slot in expected),
        manager=manager,
        styles=slot_styles,
    )


def load_lineup(path: Path | str) -> Lineup:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LineupError(f"cannot read squad file {path}: {exc}") from exc
    return lineup_from_dict(data, name=path.stem)


def resolve_cards(lineup: Lineup, repo: CardRepository) -> dict[str, Card]:
    """slot_key -> Card; raises LineupError naming ALL unknown ids."""
    by_id = {card.id: card for card in repo.find_all()}
    missing = [card_id for _slot, card_id in lineup.slots if card_id not in by_id]
    if missing:
        raise LineupError(f"cards not in DB: {', '.join(missing)}")
    return {slot: by_id[card_id] for slot, card_id in lineup.slots}
