"""Lineup model: load and validate squad JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..db import CardRepository
from ..errors import FC26Error
from ..models import Card
from .formations import FORMATIONS


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


def load_lineup(path: Path | str) -> Lineup:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LineupError(f"cannot read squad file {path}: {exc}") from exc

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

    ids = [xi[slot] for slot in expected if slot in xi]
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
        name=data.get("name", path.stem),
        formation=formation,
        slots=tuple((slot, xi[slot]) for slot in expected),
        manager=manager,
    )


def resolve_cards(lineup: Lineup, repo: CardRepository) -> dict[str, Card]:
    """slot_key -> Card; raises LineupError naming ALL unknown ids."""
    by_id = {card.id: card for card in repo.find_all()}
    missing = [card_id for _slot, card_id in lineup.slots if card_id not in by_id]
    if missing:
        raise LineupError(f"cards not in DB: {', '.join(missing)}")
    return {slot: by_id[card_id] for slot, card_id in lineup.slots}
