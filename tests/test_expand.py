import pytest

from fc26.db import CardRepository
from fc26.errors import ParseError
from fc26.ingest.expand import ExpandResult, expand_cards
from fc26.models import Card, FaceStats

FACE = FaceStats(pac=90, sho=90, pas=90, dri=90, def_=60, phy=80)


def _card(card_id: str, name: str, version: str, ovr: int) -> Card:
    return Card(id=card_id, player_name=name, version=version, ovr=ovr,
                position="ST", face=FACE, league="L", nation="N", club="C")


def _pages(*pages):
    """Build a fake parse function serving fixed pages of cards by page number."""
    def fake_parse(html, source_url):
        page_num = int(source_url.rsplit("page=", 1)[1])
        if page_num > len(pages):
            return []
        return list(pages[page_num - 1])
    return fake_parse


def test_paginates_until_short_page(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")
    page1 = [_card(f"p{i}--toty", f"P{i}", "TOTY", 90) for i in range(30)]
    page2 = [_card(f"q{i}--tots", f"Q{i}", "TOTS", 88) for i in range(7)]
    monkeypatch.setattr("fc26.ingest.expand.parse_futbin_page", _pages(page1, page2))
    fetched = []
    result = expand_cards(repo, min_ovr=87,
                          fetch_html=lambda url: (fetched.append(url) or url),
                          sleep=lambda s: None)
    assert result.seen == 37
    assert result.new == 37
    assert result.merged == 0
    assert len(fetched) == 2          # stopped after the short page
    assert "player_rating=87-99" in fetched[0]
    assert len(repo.find_all()) == 37


def test_merged_counts_existing_ids(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_card("p0--toty", "P0", "TOTY", 90))
    page1 = [_card("p0--toty", "P0", "TOTY", 90), _card("p1--toty", "P1", "TOTY", 91)]
    monkeypatch.setattr("fc26.ingest.expand.parse_futbin_page", _pages(page1))
    result = expand_cards(repo, min_ovr=87, fetch_html=lambda u: u, sleep=lambda s: None)
    assert result.seen == 2
    assert result.new == 1
    assert result.merged == 1


def test_same_id_different_ovr_gets_suffix(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")
    page1 = [_card("mo-salah--if", "Mo Salah", "IF", 90),
             _card("mo-salah--if", "Mo Salah", "IF", 87)]
    monkeypatch.setattr("fc26.ingest.expand.parse_futbin_page", _pages(page1))
    result = expand_cards(repo, min_ovr=87, fetch_html=lambda u: u, sleep=lambda s: None)
    ids = sorted(c.id for c in repo.find_all())
    assert ids == ["mo-salah--if", "mo-salah--if-87"]
    assert result.new == 2


def test_base_version_ovr_drift_merges_without_suffix(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_card("rodri--base", "Rodri", "base", 89))
    page1 = [_card("rodri--base", "Rodri", "base", 90)]  # title-update drift
    monkeypatch.setattr("fc26.ingest.expand.parse_futbin_page", _pages(page1))
    expand_cards(repo, min_ovr=87, fetch_html=lambda u: u, sleep=lambda s: None)
    cards = repo.find_all()
    assert len(cards) == 1
    assert cards[0].ovr == 90         # merged, incoming wins


def test_max_pages_caps_run(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")
    pages = [[_card(f"x{p}{i}--tots", f"X{p}{i}", "TOTS", 88) for i in range(30)]
             for p in range(5)]
    monkeypatch.setattr("fc26.ingest.expand.parse_futbin_page", _pages(*pages))
    fetched = []
    expand_cards(repo, min_ovr=87, fetch_html=lambda u: (fetched.append(u) or u),
                 sleep=lambda s: None, max_pages=2)
    assert len(fetched) == 2


def test_aborts_when_early_pages_fail(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")

    def boom(html, source_url):
        raise ParseError("no player rows")

    monkeypatch.setattr("fc26.ingest.expand.parse_futbin_page", boom)
    with pytest.raises(ParseError, match="layout changed"):
        expand_cards(repo, min_ovr=87, fetch_html=lambda u: u, sleep=lambda s: None)


def test_sleeps_once_per_fetch(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")
    page1 = [_card(f"p{i}--toty", f"P{i}", "TOTY", 90) for i in range(30)]
    page2 = [_card("z--tots", "Z", "TOTS", 88)]
    monkeypatch.setattr("fc26.ingest.expand.parse_futbin_page", _pages(page1, page2))
    slept = []
    expand_cards(repo, min_ovr=87, fetch_html=lambda u: u,
                 sleep=lambda s: slept.append(s))
    assert len(slept) == 2
