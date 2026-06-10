import pytest

from fc26.db import CardRepository
from fc26.errors import ParseError
from fc26.ingest.discovery import ALL_CLUBS_URL
from fc26.ingest.enrich import EnrichResult, enrich_cards, is_enriched
from fc26.ingest.fcratings import TOP100_URL
from fc26.models import Card, FaceStats

FULL_FACE = FaceStats(pac=90, sho=80, pas=80, dri=80, def_=80, phy=80)


@pytest.fixture()
def repo(tmp_path):
    r = CardRepository(tmp_path / "players.json")
    r.upsert(Card(id="kylian-mbappe--base", player_name="Kylian Mbappé", version="base",
                  ovr=91, position="ST", club="Real Madrid CF"))
    r.upsert(Card(id="karim-adeyemi--base", player_name="Karim Adeyemi", version="base",
                  ovr=82, position="RW", club="Borussia Dortmund"))
    r.upsert(Card(id="rich--tots", player_name="Rich", version="TOTS", ovr=90, position="ST",
                  source_url="https://www.fut.gg/players/1-rich/26-1/"))
    r.upsert(Card(id="done--base", player_name="Done", version="base", ovr=85, position="CB",
                  league="L", nation="N", face=FULL_FACE))
    return r


def _enriched_card(card_id: str, name: str) -> Card:
    return Card(id=card_id, player_name=name, version="base", ovr=91, position="ST",
                club="Real Madrid CF", league="La Liga", nation="France", face=FULL_FACE)


def test_is_enriched():
    assert is_enriched(_enriched_card("a--base", "A"))
    assert not is_enriched(Card(id="b--base", player_name="B", version="base", ovr=80,
                                position="ST", league="L", nation="N"))  # face missing


def test_enrich_happy_path_top100_and_club_routes(repo, monkeypatch):
    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls",
                        lambda html: {"kylian-mbappe": "https://www.fcratings.com/kylian-mbappe-231747"})
    monkeypatch.setattr("fc26.ingest.enrich.parse_all_clubs",
                        lambda html: {"Borussia Dortmund": "https://www.fcratings.com/clubs/borussia-dortmund-22"})
    monkeypatch.setattr("fc26.ingest.enrich.find_player_link",
                        lambda html, name: "https://www.fcratings.com/karim-adeyemi-251852")
    monkeypatch.setattr(
        "fc26.ingest.enrich.parse_player_page",
        lambda html, source_url: _enriched_card(
            "kylian-mbappe--base" if "mbappe" in source_url else "karim-adeyemi--base",
            "Kylian Mbappé" if "mbappe" in source_url else "Karim Adeyemi",
        ),
    )
    fetched, slept = [], []
    result = enrich_cards(
        repo,
        fetch_html=lambda url: (fetched.append(url) or url),
        sleep=lambda s: slept.append(s),
    )
    assert set(result.enriched) == {"kylian-mbappe--base", "karim-adeyemi--base"}
    assert "rich--tots" in result.skipped
    assert "done--base" in result.skipped
    assert result.missed == ()
    assert repo.find_by_id("kylian-mbappe--base").league == "La Liga"
    assert TOP100_URL in fetched
    assert ALL_CLUBS_URL in fetched
    assert len(slept) == len(fetched)  # one polite delay per request


def test_missing_player_recorded_not_fatal(repo, monkeypatch):
    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls",
                        lambda html: {"kylian-mbappe": "https://www.fcratings.com/kylian-mbappe-231747"})
    monkeypatch.setattr("fc26.ingest.enrich.parse_all_clubs", lambda html: {})
    monkeypatch.setattr("fc26.ingest.enrich.parse_player_page",
                        lambda html, source_url: _enriched_card("kylian-mbappe--base", "Kylian Mbappé"))
    result = enrich_cards(repo, fetch_html=lambda u: u, sleep=lambda s: None)
    assert "kylian-mbappe--base" in result.enriched
    assert any(m.startswith("karim-adeyemi--base:") for m in result.missed)


def test_refresh_re_enriches_complete_cards(repo, monkeypatch):
    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls",
                        lambda html: {"done": "https://www.fcratings.com/done-9"})
    monkeypatch.setattr(
        "fc26.ingest.enrich.parse_player_page",
        lambda html, source_url: Card(id="done--base", player_name="Done", version="base",
                                      ovr=86, position="CB", league="L", nation="N", face=FULL_FACE),
    )
    result = enrich_cards(repo, fetch_html=lambda u: u, sleep=lambda s: None,
                          refresh=True, limit=1)
    assert result.enriched == ("done--base",)  # first in id order, limit caps the rest
    assert repo.find_by_id("done--base").ovr == 86


def test_limit_caps_player_fetches(repo, monkeypatch):
    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls",
                        lambda html: {"kylian-mbappe": "u1", "karim-adeyemi": "u2"})
    monkeypatch.setattr("fc26.ingest.enrich.parse_player_page",
                        lambda html, source_url: _enriched_card("karim-adeyemi--base", "Karim Adeyemi"))
    result = enrich_cards(repo, fetch_html=lambda u: u, sleep=lambda s: None, limit=1)
    assert len(result.enriched) == 1


def test_aborts_when_most_pages_fail(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")
    for i in range(12):
        repo.upsert(Card(id=f"p{i}--base", player_name=f"P{i}", version="base",
                         ovr=80, position="ST"))
    monkeypatch.setattr(
        "fc26.ingest.enrich.extract_player_urls",
        lambda html: {f"p{i}": f"https://www.fcratings.com/p{i}-1000{i}" for i in range(12)},
    )
    def boom(html, source_url):
        raise ParseError("missing ovr")
    monkeypatch.setattr("fc26.ingest.enrich.parse_player_page", boom)
    with pytest.raises(ParseError, match="layout changed"):
        enrich_cards(repo, fetch_html=lambda u: u, sleep=lambda s: None)


def test_id_mismatch_surfaces_warning(repo, monkeypatch):
    # page name differs from the DB card name -> upsert lands under a NEW id;
    # the original stays unenriched and the operator must be told
    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls",
                        lambda html: {"kylian-mbappe": "https://www.fcratings.com/vinicius-junior-1"})
    monkeypatch.setattr("fc26.ingest.enrich.parse_all_clubs", lambda html: {})
    monkeypatch.setattr("fc26.ingest.enrich.parse_player_page",
                        lambda html, source_url: _enriched_card("vinicius-junior--base", "Vinícius Júnior"))
    messages = []
    result = enrich_cards(repo, fetch_html=lambda u: u, sleep=lambda s: None,
                          on_progress=messages.append)
    assert "vinicius-junior--base" in result.enriched
    assert any("WARNING" in m and "kylian-mbappe--base" in m for m in messages)


def test_no_club_card_recorded_as_miss(tmp_path, monkeypatch):
    from fc26.db import CardRepository

    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(Card(id="lost--base", player_name="Lost", version="base", ovr=80, position="ST"))
    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls", lambda html: {})
    result = enrich_cards(repo, fetch_html=lambda u: u, sleep=lambda s: None)
    assert any(m.startswith("lost--base: no club") for m in result.missed)


def test_player_not_on_club_page_recorded_as_miss(repo, monkeypatch):
    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls",
                        lambda html: {"kylian-mbappe": "https://www.fcratings.com/kylian-mbappe-231747"})
    monkeypatch.setattr("fc26.ingest.enrich.parse_all_clubs",
                        lambda html: {"Borussia Dortmund": "https://www.fcratings.com/clubs/borussia-dortmund-22"})
    monkeypatch.setattr("fc26.ingest.enrich.find_player_link", lambda html, name: None)
    monkeypatch.setattr("fc26.ingest.enrich.parse_player_page",
                        lambda html, source_url: _enriched_card("kylian-mbappe--base", "Kylian Mbappé"))
    result = enrich_cards(repo, fetch_html=lambda u: u, sleep=lambda s: None)
    assert any(m.startswith("karim-adeyemi--base: not found on club page") for m in result.missed)
