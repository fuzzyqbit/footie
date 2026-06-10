from fc26.ingest.markdown import extract_tables
from fc26.ingest.seed import (
    parse_master_pace_list,
    parse_special_cards,
    parse_top100,
    seed_cards,
)

TOP100_MD = """\
# 08 — FC 26 Top 100 Player Ratings

## Top 100 (by overall)

| Rank | Player | OVR | Pos | Club |
|---:|---|---:|:--:|---|
| 1 | Kylian Mbappé | 91 | ST | Real Madrid CF |
| 2 | Erling Haaland | 91 | ST | Manchester City F.C. |
| 9 | Rodri | 89 | CDM | Manchester City F.C. |
"""

MASTER_MD = """\
# 10 — The Fastest XI (ranked by Pace)

| Pos | Player | OVR | PAC | Club | Source |
|---|---|---:|---:|---|---|
| RB | **Jeremie Frimpong** | 82 | **94** | Liverpool | ✅ crawled |

## Master list — fastest players by Pace

| PAC | Player | Pos | OVR | Club |
|---:|---|:--:|---:|---|
| 96 | Kylian Mbappé | ST | 91 | Real Madrid CF |
| 96 | Karim Adeyemi | RW/RM | 82 | Borussia Dortmund |
"""

SPECIALS_MD = """\
# 11 — Special Cards Tracker

| Player | Card Version | OVR | Pos | PAC | SHO | PAS | DRI | DEF | PHY | AcceleRATE | SM/WF | Key PlayStyles+ |
|---|---|---:|:--:|---:|---:|---:|---:|---:|---:|:--:|:--:|---|
| Cristiano Ronaldo | Team of the Season (TOTS) | 95 | ST | **93** | 96 | 87 | 93 | 45 | 88 | Controlled | 5★/5★ | **Rapid, Quick Step**, Finesse Shot |
| Rodri | Festival of Football: Path to Glory | 96 | CDM/CM | 90 | 88 | 96 | 95 | 94 | 92 | Controlled | 5★/5★ | Intercept, Anticipate |

| Rank | Player | Card | OVR | Pos | PAC | AcceleRATE | Pace PlayStyles+ |
|---:|---|---|---:|:--:|---:|:--:|---|
| 1 | Cristiano Ronaldo | TOTS | 95 | ST | 93 | Controlled | Rapid, Quick Step |
"""


def test_extract_tables_strips_bold_and_skips_separators():
    tables = extract_tables("| A | B |\n|---|---|\n| **x** | y |\n")
    assert tables == [[{"A": "x", "B": "y"}]]


def test_parse_top100_builds_base_cards():
    cards = parse_top100(TOP100_MD)
    assert len(cards) == 3
    mbappe = cards[0]
    assert mbappe.id == "kylian-mbappe--base"
    assert mbappe.ovr == 91
    assert mbappe.position == "ST"
    assert mbappe.club == "Real Madrid CF"
    assert mbappe.version == "base"


def test_parse_master_pace_list_reads_only_master_table():
    cards = parse_master_pace_list(MASTER_MD)
    assert len(cards) == 2  # XI table (with Source column) skipped
    adeyemi = next(c for c in cards if "adeyemi" in c.id)
    assert adeyemi.face.pac == 96
    assert adeyemi.position == "RW"
    assert adeyemi.alt_positions == ("RM",)


def test_parse_special_cards_full_face_stats():
    cards = parse_special_cards(SPECIALS_MD)
    assert len(cards) == 2  # pace-ranking table (with Rank column) skipped
    ronaldo = next(c for c in cards if "ronaldo" in c.id)
    assert ronaldo.id == "cristiano-ronaldo--team-of-the-season-tots"
    assert ronaldo.ovr == 95
    assert ronaldo.face.pac == 93
    assert ronaldo.face.def_ == 45
    assert ronaldo.accelerate == "Controlled"
    assert ronaldo.skill_moves == 5
    assert ronaldo.weak_foot == 5
    assert ronaldo.playstyles_plus == ("Rapid", "Quick Step", "Finesse Shot")
    rodri = next(c for c in cards if "rodri" in c.id)
    assert rodri.position == "CDM"
    assert rodri.alt_positions == ("CM",)


def test_seed_cards_combines_all_sources():
    cards = seed_cards(TOP100_MD, MASTER_MD, SPECIALS_MD)
    ids = [c.id for c in cards]
    assert "kylian-mbappe--base" in ids  # appears once per source; repo merge dedupes
    assert "cristiano-ronaldo--team-of-the-season-tots" in ids
    assert len(cards) == 3 + 2 + 2


def test_rows_with_non_numeric_stats_are_skipped():
    md = (
        "| PAC | Player | Pos | OVR | Club |\n"
        "|---|---|---|---|---|\n"
        "| 96 | Kylian Mbappé | ST | 91 | Real Madrid CF |\n"
        "| — | *not crawled* | LB | — | — |\n"
    )
    cards = parse_master_pace_list(md)
    assert [c.player_name for c in cards] == ["Kylian Mbappé"]


def test_top100_rows_with_non_numeric_ovr_are_skipped():
    md = (
        "| Rank | Player | OVR | Pos | Club |\n"
        "|---|---|---|---|---|\n"
        "| 1 | Kylian Mbappé | 91 | ST | Real Madrid CF |\n"
        "| 2 | Mystery Man | TBD | ST | Nowhere FC |\n"
    )
    cards = parse_top100(md)
    assert [c.player_name for c in cards] == ["Kylian Mbappé"]
