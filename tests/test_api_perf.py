"""Phase 3 perf-mechanism tests: /api/meta caching, leaf memoization, handler offload.

These assert the optimizations are wired correctly. Behavior equivalence is
covered by the golden suite; these check the mechanisms (cache invalidation,
lru_cache presence, sync-vs-async handler registration).
"""

from __future__ import annotations

import inspect
import json
import os

import pytest
from fastapi.testclient import TestClient

from fc26.api.app import create_app

SLOTS_4231 = ("GK", "RB", "CB1", "CB2", "LB", "CDM1", "CDM2", "CAM", "RW", "LW", "ST")
POS_MAP = {
    "GK": "GK", "RB": "RB", "CB1": "CB", "CB2": "CB", "LB": "LB",
    "CDM1": "CDM", "CDM2": "CDM", "CAM": "CAM", "RW": "RW", "LW": "LW", "ST": "ST",
}


def _card(slot, league="Premier League"):
    return {
        "id": f"{slot.lower()}-test", "player_name": f"Player {slot}", "version": "base",
        "ovr": 85, "position": POS_MAP[slot], "alt_positions": [],
        "face": {"pac": 80, "sho": 80, "pas": 80, "dri": 80, "def_": 80, "phy": 80},
        "subs": None, "playstyles": [], "playstyles_plus": [], "accelerate": None,
        "skill_moves": None, "weak_foot": None, "club": "Test Club", "nation": "Brazil",
        "league": league, "price": 10000,
    }


def _write_db(path, cards):
    path.write_text(json.dumps({"schema_version": 1, "cards": cards}), encoding="utf-8")


@pytest.fixture
def tmp_db(tmp_path):
    db = tmp_path / "players.json"
    _write_db(db, [_card(s) for s in SLOTS_4231])
    return db


@pytest.fixture
def tmp_squads(tmp_path):
    d = tmp_path / "squads"
    d.mkdir()
    return d


def test_meta_cache_returns_identical_and_invalidates(tmp_db, tmp_squads):
    client = TestClient(create_app(tmp_db, tmp_squads))
    first = client.get("/api/meta").json()
    second = client.get("/api/meta").json()
    assert first == second
    assert "Premier League" in first["data"]["leagues"]
    assert "La Liga" not in first["data"]["leagues"]

    # external rewrite adds a new league; bump mtime to guarantee invalidation
    cards = [_card(s) for s in SLOTS_4231]
    cards.append(_card("ST", league="La Liga") | {"id": "st2-test"})
    _write_db(tmp_db, cards)
    st = tmp_db.stat()
    os.utime(tmp_db, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))

    after = client.get("/api/meta").json()
    assert "La Liga" in after["data"]["leagues"]  # cache invalidated on mtime change


def test_meta_versions_not_filtered_but_others_are(tmp_db, tmp_squads):
    # byte-identical contract: versions has no falsy filter; leagues/nations/clubs do
    client = TestClient(create_app(tmp_db, tmp_squads))
    data = client.get("/api/meta").json()["data"]
    assert data["versions"] == ["base"]
    assert all(data["leagues"]) and all(data["nations"]) and all(data["clubs"])


def test_leaf_functions_are_memoized():
    from fc26.models import slugify
    from fc26.chem.aliases import canonical_club, canonical_league, canonical_nation

    for fn in (slugify, canonical_club, canonical_league, canonical_nation):
        assert hasattr(fn, "cache_info"), f"{fn.__name__} is not lru_cache-wrapped"
    slugify("Some Name")
    slugify("Some Name")
    assert slugify.cache_info().hits >= 1


def test_heavy_post_handlers_offload_to_threadpool(tmp_db, tmp_squads):
    # The CPU-heavy POSTs (build/upgrade/chem/boost) read the body async then run
    # the blocking compute via run_in_threadpool so the event loop stays free.
    # Cheap GETs stay inline async (reads are cache-served post-Phase-2, so the
    # threadpool thread-hop would only add latency).
    app = create_app(tmp_db, tmp_squads)
    endpoints = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
    for path in ("/api/build", "/api/upgrade", "/api/chem", "/api/boost"):
        ep = endpoints[path]
        assert inspect.iscoroutinefunction(ep)
        assert "run_in_threadpool" in inspect.getsource(ep), f"{path} does not offload"
