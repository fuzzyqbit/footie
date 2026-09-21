"""A player's own objective page beats the generic category page that also shows them."""

from __future__ import annotations

from fc26.db import CardRepository
from fc26.ingest.objectives import build_objectives
from fc26.models import Card, FaceStats


def _untradeable(card_id: str, name: str) -> Card:
    return Card(id=card_id, player_name=name, version="Objective", ovr=84, position="ST",
                face=FaceStats(pac=80, sho=80, pas=80, dri=80, def_=40, phy=70), price=None)


def test_generic_category_record_dropped_when_specific_page_matches(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_untradeable("kostoulas--objective", "Charalampos Kostoulas"))
    repo.upsert(_untradeable("lonely--objective", "Lonely Player"))
    pages = [
        {"url": "https://www.fut.gg/objectives/foundations/", "group": "Objectives",
         "tasks": ["Category blurb."], "player_alts": ["Charalampos Kostoulas", "Lonely Player"]},
        {"url": "https://www.fut.gg/objectives/foundations/12-total-football", "group": "Total Football",
         "tasks": ["Score 5 goals."], "player_alts": ["Charalampos Kostoulas"]},
    ]
    records = build_objectives(repo, pages=pages)
    by_card = {r["card_id"]: r for r in records}
    assert len(records) == 2
    assert by_card["kostoulas--objective"]["objective"] == "Total Football"
    assert by_card["kostoulas--objective"]["tasks"] == ["Score 5 goals."]
    assert by_card["lonely--objective"]["objective"] == "Objectives"   # only match: kept
