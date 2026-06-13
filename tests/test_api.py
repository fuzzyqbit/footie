import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from fc26.api.app import create_app

SLOTS_4231 = ("GK", "RB", "CB1", "CB2", "LB", "CDM1", "CDM2", "CAM", "RW", "LW", "ST")
POS_MAP = {
    "GK": "GK", "RB": "RB", "CB1": "CB", "CB2": "CB", "LB": "LB",
    "CDM1": "CDM", "CDM2": "CDM", "CAM": "CAM", "RW": "RW", "LW": "LW", "ST": "ST",
}


def _card_dict(slot: str, ovr: int = 85, club: str = "Test Club",
               nation: str = "Brazil", league: str = "Premier League",
               version: str = "base") -> dict:
    return {
        "id": f"{slot.lower()}-test",
        "player_name": f"Player {slot}",
        "version": version,
        "ovr": ovr,
        "position": POS_MAP[slot],
        "alt_positions": [],
        "face": {"pac": 80, "sho": 80, "pas": 80, "dri": 80, "def_": 80, "phy": 80},
        "subs": None,
        "playstyles": [],
        "playstyles_plus": [],
        "accelerate": None,
        "skill_moves": None,
        "weak_foot": None,
        "club": club,
        "nation": nation,
        "league": league,
        "price": 10000,
    }


@pytest.fixture
def tmp_db(tmp_path):
    db = tmp_path / "players.json"
    cards = [_card_dict(slot) for slot in SLOTS_4231]
    db.write_text(json.dumps({"schema_version": 1, "cards": cards}), encoding="utf-8")
    return db


@pytest.fixture
def tmp_squads(tmp_path):
    squads_dir = tmp_path / "squads"
    squads_dir.mkdir()
    squad = {
        "name": "Test Squad",
        "formation": "4-2-3-1",
        "starting_xi": {slot: f"{slot.lower()}-test" for slot in SLOTS_4231},
    }
    (squads_dir / "test-squad.json").write_text(json.dumps(squad), encoding="utf-8")
    return squads_dir


@pytest.fixture
def client(tmp_db, tmp_squads):
    return TestClient(create_app(tmp_db, tmp_squads))


VALID_SQUAD = {
    "name": "Test Squad",
    "formation": "4-2-3-1",
    "starting_xi": {slot: f"{slot.lower()}-test" for slot in SLOTS_4231},
}


def test_create_app_returns_fastapi(tmp_path):
    from fastapi import FastAPI
    squads_dir = tmp_path / "squads"
    squads_dir.mkdir()
    db = tmp_path / "players.json"
    db.write_text('{"schema_version": 1, "cards": []}')
    app = create_app(db, squads_dir)
    assert isinstance(app, FastAPI)


def test_list_cards_returns_envelope(client):
    r = client.get("/api/cards")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "total" in body["data"]
    assert "cards" in body["data"]
    assert body["data"]["total"] == 11


def test_list_cards_search_filter(client):
    r = client.get("/api/cards?search=Player GK")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 1
    assert data["cards"][0]["id"] == "gk-test"


def test_list_cards_pos_filter(client):
    r = client.get("/api/cards?pos=GK")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 1
    assert data["cards"][0]["position"] == "GK"


def test_list_cards_min_ovr_filter(client):
    r = client.get("/api/cards?min_ovr=90")
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 0


def test_list_cards_pagination(client):
    r = client.get("/api/cards?limit=3&offset=0")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["cards"]) == 3
    assert data["total"] == 11


def test_list_cards_bad_sort(client):
    r = client.get("/api/cards?sort=invalid")
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert "sort" in body["error"].lower()


def test_get_card_by_id(client):
    r = client.get("/api/cards/gk-test")
    assert r.status_code == 200
    assert r.json()["data"]["id"] == "gk-test"


def test_get_card_unknown_id(client):
    r = client.get("/api/cards/no-such-card")
    assert r.status_code == 404
    body = r.json()
    assert body["ok"] is False
    assert body["error"] is not None
