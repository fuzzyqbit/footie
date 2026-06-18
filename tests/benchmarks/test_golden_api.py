"""BENCH-03 — API response equivalence via TestClient.

Goldens the JSON of the read + compute endpoints over the frozen corpus. Phases
2-3 change how these are computed/cached; the responses must stay identical
(including the /api/meta version-filter quirk: versions unfiltered, while
leagues/nations/clubs drop falsy values).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fc26.api.app import create_app
from fc26.builder.build import build_squad
from fc26.db import CardRepository

from .corpus import corpus_path, golden_check


@pytest.fixture
def api_client(tmp_path):
    db = Path(tmp_path) / "players.json"
    db.write_text(corpus_path().read_text(encoding="utf-8"), encoding="utf-8")
    squads = Path(tmp_path) / "squads"
    squads.mkdir()
    return TestClient(create_app(db, squads))


@pytest.mark.golden
def test_golden_api_cards(api_client):
    r = api_client.get("/api/cards")
    assert r.status_code == 200
    golden_check("api_cards.json", r.json())


@pytest.mark.golden
def test_golden_api_meta(api_client):
    r = api_client.get("/api/meta")
    assert r.status_code == 200
    golden_check("api_meta.json", r.json())


@pytest.mark.golden
def test_golden_api_build(api_client):
    r = api_client.post("/api/build", json={
        "formation": "4-2-3-1", "budget": "500000000", "objective": "meta"})
    assert r.status_code == 200
    golden_check("api_build.json", r.json())


@pytest.mark.golden
def test_golden_api_upgrade(api_client):
    pool = CardRepository(corpus_path()).find_all()
    seed = build_squad("4-2-3-1", pool, budget=500_000_000, objective="meta")
    squad = {
        "name": "golden-squad",
        "formation": seed.lineup.formation,
        "starting_xi": {slot: card.id for slot, card in seed.slot_cards.items()},
    }
    r = api_client.post("/api/upgrade", json={
        "squad": squad, "budget": "500000000", "swaps": 3})
    assert r.status_code == 200
    golden_check("api_upgrade.json", r.json())
