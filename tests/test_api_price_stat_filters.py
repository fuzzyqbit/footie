"""/api/cards price range + price sort, and /api/value stat + min-price filters."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fc26.api.app import create_app


def _card(card_id: str, ovr: int, price: int | None, pac: int) -> dict:
    return {
        "id": card_id, "player_name": card_id, "version": "base", "ovr": ovr,
        "position": "ST", "alt_positions": [],
        "face": {"pac": pac, "sho": 80, "pas": 80, "dri": 80, "def_": 40, "phy": 70},
        "subs": None, "playstyles": [], "playstyles_plus": [], "accelerate": None,
        "skill_moves": None, "weak_foot": None, "club": "C", "nation": "N",
        "league": "L", "price": price,
    }


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "players.json"
    cards = [
        _card("cheap-slow", 84, 5_000, 70),
        _card("cheap-fast", 84, 9_000, 92),
        _card("mid-fast", 86, 40_000, 90),
        _card("pricey", 90, 900_000, 88),
        _card("untradeable", 88, None, 95),
    ]
    db.write_text(json.dumps({"schema_version": 1, "cards": cards}), encoding="utf-8")
    squads = tmp_path / "squads"
    squads.mkdir()
    return TestClient(create_app(db, squads))


def _ids(response) -> list[str]:
    body = response.json()
    assert body["ok"], body
    return [c["id"] for c in body["data"].get("cards", body["data"].get("picks"))]


def test_cards_price_range_excludes_unpriced(client):
    assert set(_ids(client.get("/api/cards?min_price=8000&max_price=50000"))) == {"cheap-fast", "mid-fast"}
    assert "untradeable" not in _ids(client.get("/api/cards?max_price=10000000"))
    assert "untradeable" in _ids(client.get("/api/cards"))           # no range: untouched


def test_cards_sort_by_price_is_cheapest_first_unpriced_last(client):
    assert _ids(client.get("/api/cards?sort=price")) == [
        "cheap-slow", "cheap-fast", "mid-fast", "pricey", "untradeable",
    ]


def test_cards_inverted_price_range_is_a_400(client):
    r = client.get("/api/cards?min_price=50000&max_price=1000")
    assert r.status_code == 400 and "price" in r.json()["error"]


def test_value_stat_and_min_price_filters(client):
    everything = set(_ids(client.get("/api/value?min_ovr=80&max_price=100000")))
    assert {"cheap-slow", "cheap-fast", "mid-fast"} <= everything
    fast = set(_ids(client.get("/api/value?min_ovr=80&max_price=100000&stat=pac&stat_min=90")))
    assert fast == {"cheap-fast", "mid-fast"}
    ranged = set(_ids(client.get("/api/value?min_ovr=80&max_price=100000&min_price=8000&stat=pac&stat_min=90")))
    assert ranged == {"cheap-fast", "mid-fast"}
    assert set(_ids(client.get("/api/value?min_ovr=80&max_price=100000&min_price=20000"))) == {"mid-fast"}


def test_value_bad_stat_and_bad_range_are_400s(client):
    assert client.get("/api/value?stat=speed&stat_min=90").status_code == 400
    assert client.get("/api/value?max_price=1000&min_price=5000").status_code == 400
