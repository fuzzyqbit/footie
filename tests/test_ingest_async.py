"""Byte-identical sync-vs-async equivalence gate for the ingest rewrite.

For each stage (enrich, expand, images, refresh) we run the sync function and
its async sibling over the SAME stubbed fixtures into two tmp repos, then assert
three things are identical: the result tuple, the players.json BYTES, and the
on_progress sequence. This is the zero-behavior-change contract for Phase 4.

No pytest-asyncio: async siblings are driven via asyncio.run() in sync tests.
"""

from __future__ import annotations

import asyncio

import pytest

from fc26.db import CardRepository
from fc26.errors import ParseError
from fc26.ingest.discovery import ALL_CLUBS_URL
from fc26.ingest.enrich import enrich_cards, enrich_cards_async
from fc26.ingest.expand import expand_cards, expand_cards_async
from fc26.ingest.fcratings import TOP100_URL
from fc26.ingest.futbin import LIST_URL_TEMPLATE
from fc26.ingest.images import PlayerArt, upgrade_card_images, upgrade_card_images_async
from fc26.ingest.refresh import refresh_data, refresh_data_async
from fc26.models import Card, FaceStats
from tests.benchmarks.corpus import (
    async_fetcher_class,
    offline_fetch,
    offline_fetch_async,
)

FULL_FACE = FaceStats(pac=90, sho=80, pas=80, dri=80, def_=80, phy=80)


def _seed(repo: CardRepository, cards) -> None:
    for card in cards:
        repo.upsert(card)


def _two_repos(tmp_path, cards_factory):
    repo_sync = CardRepository(tmp_path / "sync.json")
    repo_async = CardRepository(tmp_path / "async.json")
    _seed(repo_sync, cards_factory())
    _seed(repo_async, cards_factory())
    return repo_sync, repo_async


def _assert_equivalent(tmp_path, sync_res, async_res, sync_log, async_log):
    assert async_res == sync_res
    assert (tmp_path / "async.json").read_bytes() == (tmp_path / "sync.json").read_bytes()
    assert async_log == sync_log


# --------------------------------------------------------------------------- #
# enrich                                                                       #
# --------------------------------------------------------------------------- #

def _enrich_seed():
    return [
        Card(id="kylian-mbappe--base", player_name="Kylian Mbappé", version="base",
             ovr=91, position="ST", club="Real Madrid CF"),
        Card(id="karim-adeyemi--base", player_name="Karim Adeyemi", version="base",
             ovr=82, position="RW", club="Borussia Dortmund"),
        Card(id="rich--tots", player_name="Rich", version="TOTS", ovr=90, position="ST",
             source_url="https://www.fut.gg/players/1-rich/26-1/"),
        Card(id="done--base", player_name="Done", version="base", ovr=85, position="CB",
             league="L", nation="N", face=FULL_FACE),
    ]


def _enriched(card_id, name):
    return Card(id=card_id, player_name=name, version="base", ovr=91, position="ST",
                club="Real Madrid CF", league="La Liga", nation="France", face=FULL_FACE)


def _patch_enrich(monkeypatch):
    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls",
                        lambda html: {"kylian-mbappe": "https://www.fcratings.com/kylian-mbappe-231747"})
    monkeypatch.setattr("fc26.ingest.enrich.parse_all_clubs",
                        lambda html: {"Borussia Dortmund": "https://www.fcratings.com/clubs/borussia-dortmund-22"})
    monkeypatch.setattr("fc26.ingest.enrich.find_player_link",
                        lambda html, name: "https://www.fcratings.com/karim-adeyemi-251852")


_ENRICH_MAPPING = {
    TOP100_URL: "top",
    ALL_CLUBS_URL: "clubs",
    "https://www.fcratings.com/kylian-mbappe-231747": "page",
    "https://www.fcratings.com/clubs/borussia-dortmund-22": "club",
    "https://www.fcratings.com/karim-adeyemi-251852": "page",
}


def test_enrich_equivalence(tmp_path, monkeypatch):
    _patch_enrich(monkeypatch)
    monkeypatch.setattr(
        "fc26.ingest.enrich.parse_player_page",
        lambda html, source_url: _enriched(
            "kylian-mbappe--base" if "mbappe" in source_url else "karim-adeyemi--base",
            "Kylian Mbappé" if "mbappe" in source_url else "Karim Adeyemi",
        ),
    )
    repo_sync, repo_async = _two_repos(tmp_path, _enrich_seed)
    sync_log: list[str] = []
    sync_res = enrich_cards(repo_sync, fetch_html=offline_fetch(_ENRICH_MAPPING),
                            sleep=lambda _s: None, on_progress=sync_log.append)
    async_log: list[str] = []
    async_res = asyncio.run(enrich_cards_async(
        repo_async, fetcher=offline_fetch_async(_ENRICH_MAPPING), on_progress=async_log.append))

    assert sync_res.enriched == ("karim-adeyemi--base", "kylian-mbappe--base")
    _assert_equivalent(tmp_path, sync_res, async_res, sync_log, async_log)


def test_enrich_error_isolation_equivalence(tmp_path, monkeypatch):
    _patch_enrich(monkeypatch)

    def parse(html, source_url):
        if "mbappe" in source_url:
            return _enriched("kylian-mbappe--base", "Kylian Mbappé")
        raise ParseError("missing ovr")

    monkeypatch.setattr("fc26.ingest.enrich.parse_player_page", parse)
    repo_sync, repo_async = _two_repos(tmp_path, _enrich_seed)
    sync_log: list[str] = []
    sync_res = enrich_cards(repo_sync, fetch_html=offline_fetch(_ENRICH_MAPPING),
                            sleep=lambda _s: None, on_progress=sync_log.append)
    async_log: list[str] = []
    async_res = asyncio.run(enrich_cards_async(
        repo_async, fetcher=offline_fetch_async(_ENRICH_MAPPING), on_progress=async_log.append))

    # one card enriched, the other isolated as a miss — same in both paths
    assert sync_res.enriched == ("kylian-mbappe--base",)
    assert any(m.startswith("karim-adeyemi--base:") for m in sync_res.missed)
    _assert_equivalent(tmp_path, sync_res, async_res, sync_log, async_log)


# --------------------------------------------------------------------------- #
# expand                                                                       #
# --------------------------------------------------------------------------- #

_EXPAND_FACE = FaceStats(pac=90, sho=90, pas=90, dri=90, def_=60, phy=80)


def _ecard(card_id, name, version, ovr):
    return Card(id=card_id, player_name=name, version=version, ovr=ovr,
                position="ST", face=_EXPAND_FACE, league="L", nation="N", club="C")


def _pages(*pages):
    def fake_parse(html, source_url):
        page_num = int(source_url.rsplit("page=", 1)[1])
        if page_num > len(pages):
            return []
        return list(pages[page_num - 1])
    return fake_parse


def test_expand_equivalence_with_id_collision(tmp_path, monkeypatch):
    # two specials sharing id at different ovr -> _resolve suffixes the 2nd;
    # the suffix decision depends on upsert ORDER, so this is the risk-#2 guard.
    page1 = [_ecard("mo-salah--if", "Mo Salah", "IF", 90),
             _ecard("mo-salah--if", "Mo Salah", "IF", 87)]
    monkeypatch.setattr("fc26.ingest.expand.parse_futbin_page", _pages(page1))
    mapping = {
        LIST_URL_TEMPLATE.format(min_ovr=87, page=1): "p1",
        LIST_URL_TEMPLATE.format(min_ovr=87, page=2): "p2",
    }
    repo_sync = CardRepository(tmp_path / "sync.json")
    repo_async = CardRepository(tmp_path / "async.json")
    sync_log: list[str] = []
    sync_res = expand_cards(repo_sync, min_ovr=87, fetch_html=offline_fetch(mapping),
                            sleep=lambda _s: None, on_progress=sync_log.append)
    async_log: list[str] = []
    async_res = asyncio.run(expand_cards_async(
        repo_async, min_ovr=87, fetcher=offline_fetch_async(mapping), on_progress=async_log.append))

    assert sorted(c.id for c in repo_sync.find_all()) == ["mo-salah--if", "mo-salah--if-87"]
    _assert_equivalent(tmp_path, sync_res, async_res, sync_log, async_log)


# --------------------------------------------------------------------------- #
# images                                                                       #
# --------------------------------------------------------------------------- #

def _img_seed():
    return [Card(id=f"c{i}--toty", player_name=f"C{i}", version="TOTY", ovr=90,
                 position="ST", futbin_url=f"https://www.futbin.com/26/player/{i}/c")
            for i in range(3)]


def test_images_equivalence(tmp_path, monkeypatch):
    art = PlayerArt(image_url="https://cdn.futbin.com/img/players/p.png?w=485",
                    bg_url="https://cdn.futbin.com/img/cards/c.png?w=644",
                    club_url="club", league_url="league", nation_url="nation",
                    common_name="Common")
    monkeypatch.setattr("fc26.ingest.images.parse_player_art", lambda html: art)
    mapping = {f"https://www.futbin.com/26/player/{i}/c": "html" for i in range(3)}
    repo_sync, repo_async = _two_repos(tmp_path, _img_seed)
    sync_log: list[str] = []
    sync_res = upgrade_card_images(repo_sync, fetch_html=offline_fetch(mapping),
                                   sleep=lambda _s: None, on_progress=sync_log.append)
    async_log: list[str] = []
    async_res = asyncio.run(upgrade_card_images_async(
        repo_async, fetcher=offline_fetch_async(mapping), on_progress=async_log.append))

    assert sync_res.upgraded == ("c0--toty", "c1--toty", "c2--toty")
    _assert_equivalent(tmp_path, sync_res, async_res, sync_log, async_log)


# --------------------------------------------------------------------------- #
# refresh (full pipeline: expand -> enrich, single batched writer)            #
# --------------------------------------------------------------------------- #

def test_refresh_equivalence(tmp_path, monkeypatch):
    # expand yields two un-enriched base cards; enrich then fills them.
    page1 = [
        Card(id="a--base", player_name="A", version="base", ovr=88, position="ST", club="C"),
        Card(id="b--base", player_name="B", version="base", ovr=88, position="ST", club="C"),
    ]
    monkeypatch.setattr("fc26.ingest.expand.parse_futbin_page", _pages(page1))
    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls",
                        lambda html: {"a": "ua", "b": "ub"})

    def parse_player(html, source_url):
        cid = "a--base" if source_url == "ua" else "b--base"
        name = "A" if source_url == "ua" else "B"
        return Card(id=cid, player_name=name, version="base", ovr=88, position="ST",
                    club="C", league="La Liga", nation="France", face=FULL_FACE)

    monkeypatch.setattr("fc26.ingest.enrich.parse_player_page", parse_player)

    mapping = {
        LIST_URL_TEMPLATE.format(min_ovr=87, page=1): "p1",
        LIST_URL_TEMPLATE.format(min_ovr=87, page=2): "p2",
        TOP100_URL: "top",
        "ua": "pa",
        "ub": "pb",
    }
    repo_sync = CardRepository(tmp_path / "sync.json")
    repo_async = CardRepository(tmp_path / "async.json")
    sync_log: list[str] = []
    sync_res = refresh_data(repo_sync, min_ovr=87, fetch_html=offline_fetch(mapping),
                            sleep=lambda _s: None, on_progress=sync_log.append,
                            manifest_path=None)

    monkeypatch.setattr("fc26.ingest.refresh.AsyncFetcher", async_fetcher_class(mapping))
    async_log: list[str] = []
    async_res = asyncio.run(refresh_data_async(
        repo_async, min_ovr=87, on_progress=async_log.append, manifest_path=None))

    assert sync_res.expand.new == 2
    assert sync_res.enrich.enriched == ("a--base", "b--base")
    _assert_equivalent(tmp_path, sync_res, async_res, sync_log, async_log)
