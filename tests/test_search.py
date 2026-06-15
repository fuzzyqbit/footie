import json

from fc26.db import CardRepository
from fc26.known_names import fold


def _db(tmp_path, names):
    cards = []
    for i, name in enumerate(names):
        cards.append({
            "id": f"p{i}--base", "player_name": name, "version": "base",
            "ovr": 90, "position": "ST", "alt_positions": [],
            "face": {"pac": 90, "sho": 90, "pas": 90, "dri": 90, "def_": 50, "phy": 80},
            "subs": None, "playstyles": [], "playstyles_plus": [],
            "accelerate": None, "skill_moves": None, "weak_foot": None,
            "club": None, "nation": "Brazil", "league": None, "price": 1000,
        })
    path = tmp_path / "players.json"
    path.write_text(json.dumps({"schema_version": 1, "cards": cards}), encoding="utf-8")
    return CardRepository(path)


def test_fold_strips_accents():
    assert fold("Vinícius") == "vinicius"
    assert fold("Kaká") == "kaka"


def test_search_is_accent_insensitive(tmp_path):
    repo = _db(tmp_path, ["Vinícius José de Oliveira Júnior", "Harry Kane"])
    hits = {c.player_name for c in repo.search("vinicius")}
    assert hits == {"Vinícius José de Oliveira Júnior"}


def test_search_matches_known_nicknames(tmp_path):
    repo = _db(tmp_path, [
        "Ronaldo Luís Nazário de Lima",
        "Ronaldo de Assis Moreira",
        "Harry Kane",
    ])
    assert {c.player_name for c in repo.search("R9")} == {"Ronaldo Luís Nazário de Lima"}
    assert {c.player_name for c in repo.search("ronaldinho")} == {"Ronaldo de Assis Moreira"}
