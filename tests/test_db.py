import json

import pytest

from fc26.db import CardRepository, card_from_dict, card_to_dict
from fc26.errors import DatabaseError
from fc26.models import Card, FaceStats, SubStats, ValidationError


def _card(card_id="rodri--base", name="Rodri", **overrides) -> Card:
    base = dict(
        id=card_id,
        player_name=name,
        version="base",
        ovr=89,
        position="CDM",
        club="Manchester City F.C.",
    )
    base.update(overrides)
    return Card(**base)


def test_roundtrip_card_through_dict():
    card = _card(
        face=FaceStats(pac=72, sho=78, pas=89, dri=84, def_=87, phy=82),
        subs=SubStats(acceleration=70, sprint_speed=74),
        playstyles_plus=("Intercept",),
        alt_positions=("CM",),
    )
    assert card_from_dict(card_to_dict(card)) == card


def test_find_all_on_missing_file_returns_empty(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    assert repo.find_all() == ()


def test_upsert_then_find_by_id(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    card = _card()
    repo.upsert(card)
    assert repo.find_by_id("rodri--base") == card
    assert repo.find_by_id("nope") is None


def test_upsert_same_id_does_not_duplicate(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_card())
    repo.upsert(_card(ovr=90))
    cards = repo.find_all()
    assert len(cards) == 1
    assert cards[0].ovr == 90


def test_upsert_validates_at_boundary(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    with pytest.raises(ValidationError):
        repo.upsert(_card(ovr=0))
    assert repo.find_all() == ()


def test_search_matches_name_club_version_case_insensitive(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_card())
    repo.upsert(_card(card_id="vini-jr--base", name="Vini Jr.", club="Real Madrid CF", position="LW"))
    assert [c.id for c in repo.search("rodri")] == ["rodri--base"]
    assert [c.id for c in repo.search("real madrid")] == ["vini-jr--base"]
    assert len(repo.search("BASE")) == 2
    assert repo.search("zzz") == ()


def test_corrupt_json_raises_database_error(tmp_path):
    path = tmp_path / "players.json"
    path.write_text("{not json")
    with pytest.raises(DatabaseError, match="players.json"):
        CardRepository(path).find_all()


def test_file_has_schema_version(tmp_path):
    path = tmp_path / "players.json"
    CardRepository(path).upsert(_card())
    data = json.loads(path.read_text())
    assert data["schema_version"] == 1
    assert len(data["cards"]) == 1


def test_malformed_card_record_raises_database_error():
    with pytest.raises(DatabaseError, match="malformed card record"):
        card_from_dict({"id": "x--base", "player_name": "X", "version": "base",
                        "ovr": 80, "position": "ST", "face": {"bogus_stat": 99}})


def test_wrong_schema_version_raises_database_error(tmp_path):
    path = tmp_path / "players.json"
    path.write_text('{"schema_version": 99, "cards": []}')
    with pytest.raises(DatabaseError, match="schema_version"):
        CardRepository(path).find_all()


def test_roundtrip_all_none_substats():
    from fc26.models import SubStats

    card = _card(subs=SubStats())
    assert card_from_dict(card_to_dict(card)) == card
