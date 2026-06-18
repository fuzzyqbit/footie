"""BENCH-01 — API endpoint benchmarks via TestClient.

Each handler reconstructs a CardRepository and re-parses the full pool per
request (Phase 2/3 territory). Benched against a corpus-seeded app.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fc26.api.app import create_app
from fc26.builder.build import build_squad

from .corpus import corpus_path


@pytest.fixture
def api_client(tmp_path):
    db = Path(tmp_path) / "players.json"
    db.write_text(corpus_path().read_text(encoding="utf-8"), encoding="utf-8")
    squads = Path(tmp_path) / "squads"
    squads.mkdir()
    return TestClient(create_app(db, squads))


@pytest.fixture
def corpus_squad():
    from fc26.db import CardRepository
    pool = CardRepository(corpus_path()).find_all()
    result = build_squad("4-2-3-1", pool, budget=500_000_000, objective="meta")
    return {
        "name": "bench-squad",
        "formation": result.lineup.formation,
        "starting_xi": {slot: card.id for slot, card in result.slot_cards.items()},
    }


@pytest.mark.benchmark
def test_bench_api_cards(benchmark, api_client):
    r = benchmark(lambda: api_client.get("/api/cards"))
    assert r.status_code == 200


@pytest.mark.benchmark
def test_bench_api_meta(benchmark, api_client):
    r = benchmark(lambda: api_client.get("/api/meta"))
    assert r.status_code == 200


@pytest.mark.benchmark
def test_bench_api_build(benchmark, api_client):
    payload = {"formation": "4-2-3-1", "budget": "500000000", "objective": "meta"}
    r = benchmark(lambda: api_client.post("/api/build", json=payload))
    assert r.status_code == 200


@pytest.mark.benchmark
def test_bench_api_upgrade(benchmark, api_client, corpus_squad):
    payload = {"squad": corpus_squad, "budget": "500000000", "swaps": 3}
    r = benchmark(lambda: api_client.post("/api/upgrade", json=payload))
    assert r.status_code == 200
