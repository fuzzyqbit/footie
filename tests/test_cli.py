import json

import pytest
from typer.testing import CliRunner

from fc26.cli import app
from fc26.db import CardRepository
from fc26.models import Card, FaceStats

runner = CliRunner()


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "players.json"
    repo = CardRepository(path)
    repo.upsert(Card(
        id="rodri--base", player_name="Rodri", version="base", ovr=89,
        position="CDM", club="Manchester City F.C.",
        face=FaceStats(pac=72, sho=78, pas=89, dri=84, def_=87, phy=82),
    ))
    repo.upsert(Card(
        id="kylian-mbappe--base", player_name="Kylian Mbappé", version="base",
        ovr=91, position="ST", club="Real Madrid CF", face=FaceStats(pac=96),
    ))
    return path


def test_search_finds_by_name(db_path):
    result = runner.invoke(app, ["search", "rodri", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "Rodri" in result.output
    assert "Mbapp" not in result.output


def test_search_json_output(db_path):
    result = runner.invoke(app, ["search", "rodri", "--db", str(db_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["id"] == "rodri--base"


def test_search_no_match_exits_nonzero(db_path):
    result = runner.invoke(app, ["search", "zzz", "--db", str(db_path)])
    assert result.exit_code == 1
    assert "no cards" in result.output.lower()


def test_show_by_id_and_by_name(db_path):
    by_id = runner.invoke(app, ["show", "rodri--base", "--db", str(db_path)])
    by_name = runner.invoke(app, ["show", "Rodri", "--db", str(db_path)])
    assert by_id.exit_code == 0 and by_name.exit_code == 0
    assert "CDM" in by_id.output


def test_show_unknown_exits_nonzero(db_path):
    result = runner.invoke(app, ["show", "nobody", "--db", str(db_path)])
    assert result.exit_code == 1


def test_list_filters_by_position_and_sorts_by_pace(db_path):
    result = runner.invoke(app, ["list", "--pos", "ST", "--sort", "pac", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "Mbapp" in result.output
    assert "Rodri" not in result.output


def test_list_json(db_path):
    result = runner.invoke(app, ["list", "--sort", "ovr", "--db", str(db_path), "--json"])
    data = json.loads(result.output)
    assert [c["id"] for c in data] == ["kylian-mbappe--base", "rodri--base"]


def test_seed_reads_docs_and_writes_db(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "08-player-ratings-top100.md").write_text(
        "| Rank | Player | OVR | Pos | Club |\n|---|---|---|---|---|\n"
        "| 1 | Kylian Mbappé | 91 | ST | Real Madrid CF |\n"
    )
    (docs / "10-fastest-xi.md").write_text(
        "| PAC | Player | Pos | OVR | Club |\n|---|---|---|---|---|\n"
        "| 96 | Kylian Mbappé | ST | 91 | Real Madrid CF |\n"
    )
    (docs / "11-special-cards.md").write_text(
        "| Player | Card Version | OVR | Pos | PAC | SHO | PAS | DRI | DEF | PHY | AcceleRATE | SM/WF | Key PlayStyles+ |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| Rodri | Path to Glory | 96 | CDM/CM | 90 | 88 | 96 | 95 | 94 | 92 | Controlled | 5★/5★ | Intercept |\n"
    )
    db = tmp_path / "players.json"
    result = runner.invoke(app, ["seed", "--docs-dir", str(docs), "--db", str(db)])
    assert result.exit_code == 0, result.output
    repo = CardRepository(db)
    mbappe = repo.find_by_id("kylian-mbappe--base")
    assert mbappe is not None
    assert mbappe.face.pac == 96  # enriched by the pace list merge
    assert repo.find_by_id("rodri--path-to-glory") is not None


def test_seed_is_idempotent(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "08-player-ratings-top100.md").write_text(
        "| Rank | Player | OVR | Pos | Club |\n|---|---|---|---|---|\n"
        "| 1 | Kylian Mbappé | 91 | ST | Real Madrid CF |\n"
    )
    (docs / "10-fastest-xi.md").write_text("")
    (docs / "11-special-cards.md").write_text("")
    db = tmp_path / "players.json"
    runner.invoke(app, ["seed", "--docs-dir", str(docs), "--db", str(db)])
    first = db.read_text()
    runner.invoke(app, ["seed", "--docs-dir", str(docs), "--db", str(db)])
    assert db.read_text() == first


def test_add_calls_futgg_fetch(db_path, monkeypatch):
    fetched_urls = []

    def fake_fetch(url):
        fetched_urls.append(url)
        return Card(id="x--tots", player_name="X", version="TOTS", ovr=90, position="ST")

    monkeypatch.setattr("fc26.cli.fetch_futgg_card", fake_fetch)
    result = runner.invoke(app, ["add", "https://www.fut.gg/players/1-x/26-1/", "--db", str(db_path)])
    assert result.exit_code == 0
    assert fetched_urls == ["https://www.fut.gg/players/1-x/26-1/"]
    assert CardRepository(db_path).find_by_id("x--tots") is not None


def test_sync_calls_fcratings_fetch(db_path, monkeypatch):
    def fake_fetch():
        return [Card(id="y--base", player_name="Y", version="base", ovr=85, position="CB")]

    monkeypatch.setattr("fc26.cli.fetch_top100", fake_fetch)
    result = runner.invoke(app, ["sync", "--db", str(db_path)])
    assert result.exit_code == 0
    assert CardRepository(db_path).find_by_id("y--base") is not None


def test_fetch_error_is_clean_not_traceback(db_path, monkeypatch):
    from fc26.errors import FetchError

    def fake_fetch(url):
        raise FetchError("could not fetch http://x: boom")

    monkeypatch.setattr("fc26.cli.fetch_futgg_card", fake_fetch)
    result = runner.invoke(app, ["add", "http://x", "--db", str(db_path)])
    assert result.exit_code == 1
    assert "could not fetch" in result.output


@pytest.fixture()
def corrupt_db(tmp_path):
    path = tmp_path / "players.json"
    path.write_text("{not json")
    return path


def test_search_corrupt_db_exits_clean(corrupt_db):
    result = runner.invoke(app, ["search", "rodri", "--db", str(corrupt_db)])
    assert result.exit_code == 1
    assert "cannot read" in result.output
    assert "Traceback" not in result.output


def test_show_corrupt_db_exits_clean(corrupt_db):
    result = runner.invoke(app, ["show", "rodri--base", "--db", str(corrupt_db)])
    assert result.exit_code == 1
    assert "cannot read" in result.output
    assert "Traceback" not in result.output


def test_list_corrupt_db_exits_clean(corrupt_db):
    result = runner.invoke(app, ["list", "--db", str(corrupt_db)])
    assert result.exit_code == 1
    assert "cannot read" in result.output
    assert "Traceback" not in result.output


def test_add_invalid_card_exits_clean(db_path, monkeypatch):
    def fake_fetch(url):
        return Card(id="bad--tots", player_name="Bad", version="TOTS", ovr=200, position="ST")

    monkeypatch.setattr("fc26.cli.fetch_futgg_card", fake_fetch)
    result = runner.invoke(app, ["add", "http://x", "--db", str(db_path)])
    assert result.exit_code == 1
    assert "out of range" in result.output
    assert "Traceback" not in result.output


def test_enrich_command_reports_summary(db_path, monkeypatch):
    from fc26.ingest.enrich import EnrichResult

    def fake_enrich(repo, **kwargs):
        kwargs["on_progress"]("enriched x--base (France, La Liga)")
        return EnrichResult(("x--base",), ("y--base",), ("z--base: not found",))

    monkeypatch.setattr("fc26.cli.enrich_cards", fake_enrich)
    result = runner.invoke(app, ["enrich", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "enriched x--base (France, La Liga)" in result.output
    assert "enriched 1, skipped 1, missed 1" in result.output
    assert "z--base" in result.output


def test_enrich_command_exit_1_only_when_truly_nothing_happened(db_path, monkeypatch):
    from fc26.ingest.enrich import EnrichResult

    monkeypatch.setattr("fc26.cli.enrich_cards",
                        lambda repo, **kw: EnrichResult((), (), ()))
    result = runner.invoke(app, ["enrich", "--db", str(db_path)])
    assert result.exit_code == 1


def test_enrich_command_exit_0_when_only_misses(db_path, monkeypatch):
    from fc26.ingest.enrich import EnrichResult

    monkeypatch.setattr("fc26.cli.enrich_cards",
                        lambda repo, **kw: EnrichResult((), (), ("a--base: gone",)))
    result = runner.invoke(app, ["enrich", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "a--base" in result.output


def test_enrich_command_exit_0_when_all_skipped(db_path, monkeypatch):
    from fc26.ingest.enrich import EnrichResult

    monkeypatch.setattr("fc26.cli.enrich_cards",
                        lambda repo, **kw: EnrichResult((), ("a--base", "b--base"), ()))
    result = runner.invoke(app, ["enrich", "--db", str(db_path)])
    assert result.exit_code == 0


def test_enrich_command_clean_error_on_abort(db_path, monkeypatch):
    from fc26.errors import ParseError

    def boom(repo, **kwargs):
        raise ParseError("11/12 player pages failed - fcratings layout changed?")

    monkeypatch.setattr("fc26.cli.enrich_cards", boom)
    result = runner.invoke(app, ["enrich", "--db", str(db_path)])
    assert result.exit_code == 1
    assert "layout changed" in result.output
    assert "Traceback" not in result.output


def test_expand_command_reports_summary(db_path, monkeypatch):
    from fc26.ingest.expand import ExpandResult

    def fake_expand(repo, **kwargs):
        kwargs["on_progress"]("page 1: 30 cards")
        return ExpandResult(37, 35, 2, ())

    monkeypatch.setattr("fc26.cli.expand_cards", fake_expand)
    result = runner.invoke(app, ["expand", "--min-ovr", "87", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "page 1: 30 cards" in result.output
    assert "seen 37, new 35, merged 2, failed pages 0" in result.output


def test_expand_requires_min_ovr(db_path):
    result = runner.invoke(app, ["expand", "--db", str(db_path)])
    assert result.exit_code != 0


def test_expand_exit_1_when_nothing_ingested(db_path, monkeypatch):
    from fc26.ingest.expand import ExpandResult

    monkeypatch.setattr("fc26.cli.expand_cards",
                        lambda repo, **kw: ExpandResult(0, 0, 0, ("url: boom",)))
    result = runner.invoke(app, ["expand", "--min-ovr", "87", "--db", str(db_path)])
    assert result.exit_code == 1


def test_expand_clean_error_on_abort(db_path, monkeypatch):
    from fc26.errors import ParseError

    def boom(repo, **kwargs):
        raise ParseError("3/5 list pages failed - futbin layout changed?")

    monkeypatch.setattr("fc26.cli.expand_cards", boom)
    result = runner.invoke(app, ["expand", "--min-ovr", "87", "--db", str(db_path)])
    assert result.exit_code == 1
    assert "layout changed" in result.output
    assert "Traceback" not in result.output


@pytest.fixture()
def chem_db(tmp_path):
    path = tmp_path / "players.json"
    repo = CardRepository(path)
    positions = {"GK": "GK", "RB": "RB", "CB1": "CB", "CB2": "CB", "LB": "LB",
                 "CDM1": "CDM", "CDM2": "CDM", "CAM": "CAM", "RW": "RW", "LW": "LW", "ST": "ST"}
    for slot, pos in positions.items():
        repo.upsert(Card(
            id=f"{slot.lower()}--base", player_name=f"P{slot}", version="base",
            ovr=88, position=pos, club=f"Club {slot}", nation=f"Nation {slot}",
            league="Premier League",
        ))
    return path


@pytest.fixture()
def squad_file(tmp_path):
    squad = {
        "name": "CLI Test", "formation": "4-2-3-1",
        "starting_xi": {slot: f"{slot.lower()}--base" for slot in
                        ("GK", "RB", "CB1", "CB2", "LB", "CDM1", "CDM2", "CAM", "RW", "LW", "ST")},
    }
    path = tmp_path / "squad.json"
    path.write_text(json.dumps(squad))
    return path


def test_chem_command_reports_table_and_total(chem_db, squad_file):
    result = runner.invoke(app, ["chem", str(squad_file), "--db", str(chem_db)])
    assert result.exit_code == 0, result.output
    assert "33/33" in result.output          # 11 same-league players -> full chem
    assert "Premier League" in result.output


def test_chem_command_json(chem_db, squad_file):
    result = runner.invoke(app, ["chem", str(squad_file), "--db", str(chem_db), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["team_total"] == 33
    assert len(data["players"]) == 11


def test_chem_command_lineup_error_is_clean(chem_db, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"formation": "9-9-9", "starting_xi": {}}')
    result = runner.invoke(app, ["chem", str(bad), "--db", str(chem_db)])
    assert result.exit_code == 1
    assert "unknown formation" in result.output
    assert "Traceback" not in result.output


def test_chem_command_missing_card_is_clean(chem_db, squad_file):
    squad = json.loads(squad_file.read_text())
    squad["starting_xi"]["ST"] = "nobody--base"
    squad_file.write_text(json.dumps(squad))
    result = runner.invoke(app, ["chem", str(squad_file), "--db", str(chem_db)])
    assert result.exit_code == 1
    assert "nobody--base" in result.output


@pytest.fixture()
def upgrade_db(tmp_path):
    path = tmp_path / "players.json"
    repo = CardRepository(path)
    positions = {"GK": "GK", "RB": "RB", "CB1": "CB", "CB2": "CB", "LB": "LB",
                 "CDM1": "CDM", "CDM2": "CDM", "CAM": "CAM", "RW": "RW", "LW": "LW", "ST": "ST"}
    for slot, pos in positions.items():
        repo.upsert(Card(
            id=f"{slot.lower()}--base", player_name=f"P{slot}", version="base",
            ovr=80, position=pos, club=f"C{slot}", nation=f"N{slot}",
            league="Premier League", price=10_000,
            face=FaceStats(pac=70, sho=70, pas=70, dri=70, def_=70, phy=70),
        ))
    repo.upsert(Card(
        id="upgrade--tots", player_name="Upgrade", version="TOTS", ovr=92,
        position="ST", club="CX", nation="NX", league="Premier League", price=50_000,
        face=FaceStats(pac=92, sho=92, pas=92, dri=92, def_=92, phy=92),
    ))
    return path


def test_upgrade_command_suggests_and_reports(upgrade_db, squad_file):
    result = runner.invoke(app, ["upgrade", str(squad_file), "--budget", "100K",
                                 "--db", str(upgrade_db)])
    assert result.exit_code == 0, result.output
    assert "Upgrade" in result.output
    assert "spent" in result.output


def test_upgrade_command_json(upgrade_db, squad_file):
    result = runner.invoke(app, ["upgrade", str(squad_file), "--budget", "100K",
                                 "--db", str(upgrade_db), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["swaps"][0]["in_id"] == "upgrade--tots"
    assert data["spent"] <= data["budget"]


def test_upgrade_command_write_produces_loadable_squad(upgrade_db, squad_file, tmp_path):
    out = tmp_path / "upgraded.json"
    result = runner.invoke(app, ["upgrade", str(squad_file), "--budget", "100K",
                                 "--db", str(upgrade_db), "--write", str(out)])
    assert result.exit_code == 0, result.output
    saved = json.loads(out.read_text())
    assert saved["starting_xi"]["ST"] == "upgrade--tots"
    chem = runner.invoke(app, ["chem", str(out), "--db", str(upgrade_db)])
    assert chem.exit_code == 0, chem.output


def test_upgrade_write_refuses_overwriting_input(upgrade_db, squad_file):
    result = runner.invoke(app, ["upgrade", str(squad_file), "--budget", "100K",
                                 "--db", str(upgrade_db), "--write", str(squad_file)])
    assert result.exit_code == 1
    assert "NEW file" in result.output


def test_upgrade_no_upgrades_found_is_friendly(upgrade_db, squad_file):
    result = runner.invoke(app, ["upgrade", str(squad_file), "--budget", "1",
                                 "--db", str(upgrade_db)])
    assert result.exit_code == 0
    assert "no upgrades found" in result.output.lower()


def test_upgrade_bad_budget_clean_error(upgrade_db, squad_file):
    result = runner.invoke(app, ["upgrade", str(squad_file), "--budget", "lots",
                                 "--db", str(upgrade_db)])
    assert result.exit_code == 1
    assert "cannot parse budget" in result.output
    assert "Traceback" not in result.output


def test_upgrade_against_real_db_ci_guard():
    from pathlib import Path

    sample = Path("squads/sample-rivals.json")
    db = Path("data/players.json")
    if not sample.exists() or not db.exists():
        pytest.skip("sample squad or real DB not present")
    result = runner.invoke(app, ["upgrade", str(sample), "--budget", "200K",
                                 "--db", str(db), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["spent"] <= data["budget"]
    for swap in data["swaps"]:
        assert swap["score_delta"] > 0


def test_committed_sample_squad_hand_check_holds():
    # squads/sample-rivals.json documents a hand-computed 33/33; guard it
    # against silent DB drift (any of its 11 cards changing under enrichment).
    from pathlib import Path

    sample = Path("squads/sample-rivals.json")
    db = Path("data/players.json")
    if not sample.exists() or not db.exists():
        pytest.skip("sample squad or real DB not present")
    result = runner.invoke(app, ["chem", str(sample), "--db", str(db)])
    assert result.exit_code == 0, result.output
    assert "33/33" in result.output


def test_build_command_happy_path(upgrade_db, tmp_path):
    out = tmp_path / "built.json"
    result = runner.invoke(app, ["build", "--formation", "4-2-3-1", "--budget", "200K",
                                 "--db", str(upgrade_db), "--write", str(out)])
    assert result.exit_code == 0, result.output
    assert "total cost" in result.output
    saved = json.loads(out.read_text())
    assert len(saved["starting_xi"]) == 11
    chem = runner.invoke(app, ["chem", str(out), "--db", str(upgrade_db)])
    assert chem.exit_code == 0, chem.output


def test_build_command_json(upgrade_db):
    result = runner.invoke(app, ["build", "--formation", "4-2-3-1", "--budget", "200K",
                                 "--db", str(upgrade_db), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_cost"] <= 200_000
    assert len(data["xi"]) == 11


def test_build_command_infeasible_budget_clean(upgrade_db):
    result = runner.invoke(app, ["build", "--formation", "4-2-3-1", "--budget", "1000",
                                 "--db", str(upgrade_db)])
    assert result.exit_code == 1
    assert "budget too small" in result.output
    assert "Traceback" not in result.output


def test_build_command_real_db_ci_guard():
    from pathlib import Path

    db = Path("data/players.json")
    if not db.exists():
        pytest.skip("real DB not present")
    result = runner.invoke(app, ["build", "--formation", "4-2-3-1", "--budget", "300K",
                                 "--db", str(db), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["total_cost"] <= 300_000
    assert len(data["xi"]) == 11
    names = [p["player_name"] for p in data["xi"]]
    assert len(set(names)) == 11
