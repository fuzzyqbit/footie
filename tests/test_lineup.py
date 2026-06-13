import json

import pytest

from fc26.chem.formations import FORMATIONS, slot_position
from fc26.chem.lineup import Lineup, LineupError, load_lineup, resolve_cards
from fc26.db import CardRepository
from fc26.models import Card, VALID_POSITIONS


def test_all_formations_have_eleven_valid_slots():
    assert len(FORMATIONS) == 12
    for name, slots in FORMATIONS.items():
        assert len(slots) == 11, name
        assert slots[0] == "GK", name
        assert len(set(slots)) == 11, name           # unique slot keys
        for slot in slots:
            assert slot_position(slot) in VALID_POSITIONS, (name, slot)


def test_slot_position_strips_numeric_suffix():
    assert slot_position("CB1") == "CB"
    assert slot_position("ST2") == "ST"
    assert slot_position("GK") == "GK"
    assert slot_position("CDM1") == "CDM"


def _write_squad(path, formation="4-2-3-1", overrides=None, manager=None, drop=None):
    xi = {
        "GK": "gk--base", "RB": "rb--base", "CB1": "cb1--base", "CB2": "cb2--base",
        "LB": "lb--base", "CDM1": "cdm1--base", "CDM2": "cdm2--base", "CAM": "cam--base",
        "RW": "rw--base", "LW": "lw--base", "ST": "st--base",
    }
    xi.update(overrides or {})
    for key in drop or []:
        del xi[key]
    payload = {"name": "Test", "formation": formation, "starting_xi": xi}
    if manager:
        payload["manager"] = manager
    path.write_text(json.dumps(payload))
    return path


def test_load_lineup_happy_path(tmp_path):
    squad = _write_squad(tmp_path / "s.json", manager={"league": "Premier League"})
    lineup = load_lineup(squad)
    assert lineup.formation == "4-2-3-1"
    assert len(lineup.slots) == 11
    assert lineup.slots[0] == ("GK", "gk--base")
    assert lineup.manager.league == "Premier League"
    assert lineup.manager.nation is None


def test_load_lineup_unknown_formation_lists_available(tmp_path):
    squad = _write_squad(tmp_path / "s.json", formation="9-9-9")
    with pytest.raises(LineupError) as exc:
        load_lineup(squad)
    assert "9-9-9" in str(exc.value)
    assert "4-2-3-1" in str(exc.value)   # available list shown


def test_load_lineup_reports_all_slot_errors_at_once(tmp_path):
    squad = _write_squad(tmp_path / "s.json", drop=["ST"], overrides={"BOGUS": "x--base"})
    with pytest.raises(LineupError) as exc:
        load_lineup(squad)
    message = str(exc.value)
    assert "ST" in message       # missing slot named
    assert "BOGUS" in message    # extra slot named


def test_load_lineup_duplicate_card(tmp_path):
    squad = _write_squad(tmp_path / "s.json", overrides={"LW": "st--base"})
    with pytest.raises(LineupError, match="st--base"):
        load_lineup(squad)


def test_load_lineup_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(LineupError, match="bad.json"):
        load_lineup(bad)


def test_resolve_cards_reports_all_missing_ids(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(Card(id="gk--base", player_name="G", version="base", ovr=85, position="GK"))
    squad = _write_squad(tmp_path / "s.json")
    lineup = load_lineup(squad)
    with pytest.raises(LineupError) as exc:
        resolve_cards(lineup, repo)
    message = str(exc.value)
    assert "rb--base" in message and "st--base" in message   # all missing, not just first
    assert "gk--base" not in message


def test_lineup_slot_accepts_style_object(tmp_path):
    squad = _write_squad(tmp_path / "s.json",
                         overrides={"ST": {"id": "st--base", "style": "hunter"}})
    lineup = load_lineup(squad)
    assert dict(lineup.slots)["ST"] == "st--base"
    assert lineup.styles == {"ST": "hunter"}


def test_lineup_unknown_style_lists_available(tmp_path):
    squad = _write_squad(tmp_path / "s.json",
                         overrides={"ST": {"id": "st--base", "style": "zoomzoom"}})
    with pytest.raises(LineupError) as exc:
        load_lineup(squad)
    assert "zoomzoom" in str(exc.value)
    assert "hunter" in str(exc.value)


def test_lineup_plain_string_slots_have_no_styles(tmp_path):
    lineup = load_lineup(_write_squad(tmp_path / "s.json"))
    assert lineup.styles == {}


from fc26.chem.lineup import lineup_from_dict


def test_lineup_from_dict_valid():
    data = {
        "name": "My Squad",
        "formation": "4-2-3-1",
        "starting_xi": {
            "GK": "gk-1", "RB": "rb-1", "CB1": "cb1-1", "CB2": "cb2-1",
            "LB": "lb-1", "CDM1": "cdm1-1", "CDM2": "cdm2-1", "CAM": "cam-1",
            "RW": "rw-1", "LW": "lw-1", "ST": "st-1",
        },
    }
    lineup = lineup_from_dict(data)
    assert lineup.name == "My Squad"
    assert lineup.formation == "4-2-3-1"
    assert len(lineup.slots) == 11


def test_lineup_from_dict_invalid_formation():
    data = {"formation": "bad", "starting_xi": {}}
    with pytest.raises(LineupError, match="unknown formation"):
        lineup_from_dict(data)


def test_lineup_from_dict_missing_slots():
    data = {
        "formation": "4-2-3-1",
        "starting_xi": {"GK": "gk-1"},
    }
    with pytest.raises(LineupError, match="missing slots"):
        lineup_from_dict(data)
