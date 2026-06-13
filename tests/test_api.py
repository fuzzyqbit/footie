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


def test_list_cards_version_filter(client):
    r = client.get("/api/cards?version=base")
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 11
    r2 = client.get("/api/cards?version=tots")
    assert r2.status_code == 200
    assert r2.json()["data"]["total"] == 0


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


def test_list_cards_invalid_min_ovr_returns_envelope(client):
    r = client.get("/api/cards?min_ovr=abc")
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False
    assert body["error"] is not None
    assert "data" in body


def test_list_cards_negative_limit_rejected(client):
    r = client.get("/api/cards?limit=-1")
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_list_squads(client):
    r = client.get("/api/squads")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    squads = body["data"]
    assert len(squads) == 1
    assert squads[0]["name"] == "test-squad"


def test_get_squad_by_name(client):
    r = client.get("/api/squads/test-squad")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["formation"] == "4-2-3-1"


def test_get_squad_not_found(client):
    r = client.get("/api/squads/no-such-squad")
    assert r.status_code == 404
    assert r.json()["ok"] is False


def test_get_squad_path_traversal(client):
    r = client.get("/api/squads/dotdot..evil")
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_put_squad_valid(client):
    new_squad = {
        "name": "New Squad",
        "formation": "4-2-3-1",
        "starting_xi": {slot: f"{slot.lower()}-test" for slot in SLOTS_4231},
    }
    r = client.put("/api/squads/new-squad", json=new_squad)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["name"] == "new-squad"


def test_put_squad_invalid_formation(client):
    bad = {"formation": "bad", "starting_xi": {}}
    r = client.put("/api/squads/my-squad", json=bad)
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert "unknown formation" in body["error"]


def test_put_squad_path_traversal_rejected(client):
    r = client.put("/api/squads/dotdot..evil", json=VALID_SQUAD)
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_post_chem_valid_squad(client):
    r = client.post("/api/chem", json=VALID_SQUAD)
    assert r.status_code == 200
    data = r.json()["data"]
    # All same club+nation+league -> 33/33
    assert data["team_total"] == 33
    assert len(data["players"]) == 11


def test_post_chem_invalid_squad(client):
    r = client.post("/api/chem", json={"formation": "bad", "starting_xi": {}})
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_post_chem_missing_card(client):
    bad_squad = {
        "formation": "4-2-3-1",
        "starting_xi": {slot: "no-such-card" for slot in SLOTS_4231},
    }
    r = client.post("/api/chem", json=bad_squad)
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_post_boost_valid_squad(client):
    r = client.post("/api/boost", json=VALID_SQUAD)
    assert r.status_code == 200
    data = r.json()["data"]
    assert "players" in data
    assert "team_chem" in data
    assert len(data["players"]) == 11
    assert data["team_chem"] == 33


def test_post_boost_invalid_squad(client):
    r = client.post("/api/boost", json={"formation": "bad", "starting_xi": {}})
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_post_upgrade_valid(client):
    body = {"squad": VALID_SQUAD, "budget": "50K", "swaps": 2}
    r = client.post("/api/upgrade", json=body)
    assert r.status_code == 200
    data = r.json()["data"]
    assert "swaps" in data
    assert "spent" in data
    assert "budget" in data


def test_post_upgrade_bad_budget(client):
    body = {"squad": VALID_SQUAD, "budget": "not-a-budget", "swaps": 1}
    r = client.post("/api/upgrade", json=body)
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_post_upgrade_invalid_squad(client):
    body = {"squad": {"formation": "bad", "starting_xi": {}}, "budget": "50K"}
    r = client.post("/api/upgrade", json=body)
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_post_build_valid(client):
    body = {"formation": "4-2-3-1", "budget": "200K"}
    r = client.post("/api/build", json=body)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["formation"] == "4-2-3-1"
    assert "seed_cost" in data
    assert "total_cost" in data
    assert "team_chem" in data
    assert "xi" in data
    assert "squad" in data
    assert len(data["xi"]) == 11


def test_post_build_unknown_formation(client):
    body = {"formation": "9-1", "budget": "100K"}
    r = client.post("/api/build", json=body)
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_post_build_bad_budget(client):
    body = {"formation": "4-2-3-1", "budget": "nope"}
    r = client.post("/api/build", json=body)
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_get_meta(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "formations" in data
    assert "4-2-3-1" in data["formations"]
    assert "styles" in data
    assert "hunter" in data["styles"]
    assert "leagues" in data
    assert "Premier League" in data["leagues"]
    assert "versions" in data
    assert "base" in data["versions"]


def test_serve_command_exists():
    from fc26.cli import app as typer_app
    command_names = [cmd.name for cmd in typer_app.registered_commands]
    assert "serve" in command_names
