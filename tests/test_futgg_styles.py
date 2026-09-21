"""fut.gg PlayStyles/sub-stats pass: exact EA-id join, per-page verification, resume."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from fc26.db import CardRepository
from fc26.errors import FetchError, RateLimitedError
from fc26.ingest.futgg import _DIAMOND_PATH, _PENTAGON_PATH, _extract_playstyles
from fc26.ingest.futgg_styles import ea_item_id, futgg_url_for, upgrade_card_styles_async
from fc26.models import Card, FaceStats

_IMG = "https://cdn3.futbin.com/content/fifa27/img/players/{}.png?fm=png&w=51"


def _card(card_id: str, ovr: int, image: str | None) -> Card:
    return Card(
        id=card_id, player_name=card_id, version="base", ovr=ovr, position="ST",
        face=FaceStats(pac=90, sho=90, pas=80, dri=88, def_=40, phy=75),
        image_url=image,
    )


def _page(ea_id: int, overall: int, *, plus=("Trickster",), regular=("Technical",)) -> str:
    badge = '<div title="{}"><svg viewBox="0 0 256 256" height="42" width="42"><path d="{}"></path></svg></div>'
    return (
        f"<script>x={{eaId:{ea_id},evolutionId:null,overall:{overall},"
        f'imagePath:"2027/player-item/27-{ea_id}.abc.webp",'
        "attributeAcceleration:93,attributeSprintSpeed:90,attributeCurve:89,"
        'rarity:{imagePath:"2027/rarities-level-0-large/12.def.png"}}</script>'
        + "".join(badge.format(n, _PENTAGON_PATH) for n in plus)
        + "".join(badge.format(n, _DIAMOND_PATH) for n in regular)
    )


class _Fetcher:
    def __init__(self, pages: dict[str, object]):
        self.pages, self.calls = pages, []

    async def fetch(self, url: str) -> str:
        self.calls.append(url)
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return page


def test_url_join_base_and_special_cards():
    assert futgg_url_for(_card("a", 93, _IMG.format("28130"))) == \
        "https://www.fut.gg/players/28130/27-28130/"
    # special item id = base id + n * 2**24; base id is the low 24 bits
    assert futgg_url_for(_card("b", 90, _IMG.format("p84039159"))) == \
        "https://www.fut.gg/players/153079/27-84039159/"
    assert futgg_url_for(_card("c", 90, _IMG.format("notfound_1"))) is None
    assert futgg_url_for(_card("d", 90, None)) is None


def test_titled_badges_split_plus_from_regular():
    regular, plus = _extract_playstyles(_page(1, 90, plus=("Trickster",), regular=("Technical", "First Touch")))
    assert plus == ("Trickster",)
    assert regular == ("Technical", "First Touch")


def test_updates_verified_cards_and_never_writes_a_mismatch(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    good = _card("good--base", 93, _IMG.format("28130"))
    wrong_ovr = _card("wrong--base", 85, _IMG.format("20801"))
    no_join = _card("nojoin--base", 90, _IMG.format("notfound_1"))
    for c in (good, wrong_ovr, no_join):
        repo.upsert(c)
    fetcher = _Fetcher({
        futgg_url_for(good): _page(28130, 93),
        futgg_url_for(wrong_ovr): _page(20801, 91),      # a different version of the player
    })
    result = asyncio.run(upgrade_card_styles_async(repo, fetcher=fetcher))

    assert result.updated == ("good--base",)
    assert result.skipped == ("nojoin--base",)
    assert len(result.missed) == 1 and "overall 91 != card 85" in result.missed[0]
    saved = repo.find_by_id("good--base")
    assert saved.playstyles_plus == ("Trickster",) and saved.subs.sprint_speed == 90
    assert repo.find_by_id("wrong--base").subs is None
    # HD art comes from the same page, and the card stays joinable afterwards
    assert saved.image_url.endswith("width=256/2027/player-item/27-28130.abc.webp")
    assert saved.bg_url is None                      # backgrounds are futbin's job (frames.py)
    assert futgg_url_for(saved) == futgg_url_for(good)

    # rerun: finished cards are not fetched again
    again = _Fetcher({futgg_url_for(wrong_ovr): _page(20801, 91)})
    asyncio.run(upgrade_card_styles_async(repo, fetcher=again))
    assert again.calls == [futgg_url_for(wrong_ovr)]


def test_rate_limit_keeps_progress_and_stops(tmp_path, monkeypatch):
    monkeypatch.setattr("fc26.ingest.futgg_styles.CHUNK_SIZE", 1)
    repo = CardRepository(tmp_path / "players.json")
    cards = [_card(f"c{i}--base", 90, _IMG.format(str(1000 + i))) for i in range(3)]
    for c in cards:
        repo.upsert(c)
    fetcher = _Fetcher({
        futgg_url_for(cards[0]): _page(1000, 90),
        futgg_url_for(cards[1]): RateLimitedError("www.fut.gg blocked us (HTTP 429)", 600),
    })
    with pytest.raises(RateLimitedError, match="1 updated before the block") as exc:
        asyncio.run(upgrade_card_styles_async(repo, fetcher=fetcher))
    assert exc.value.retry_after == 600
    assert len(fetcher.calls) == 2                       # card 3 never requested
    assert CardRepository(tmp_path / "players.json").find_by_id("c0--base").subs is not None


def test_plain_fetch_error_is_a_miss_not_a_stop(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    card = _card("c--base", 90, _IMG.format("1000"))
    repo.upsert(card)
    fetcher = _Fetcher({
        futgg_url_for(card): FetchError("could not fetch"),
        "https://www.fut.gg/players/1000/": FetchError("could not fetch"),   # hub fallback fails too
    })
    result = asyncio.run(upgrade_card_styles_async(repo, fetcher=fetcher))
    assert result.updated == () and len(result.missed) == 1


def test_404_falls_back_to_player_hub_and_needs_a_unique_overall_match(tmp_path):
    repo = CardRepository(tmp_path / "players.json")
    # futbin named the image after the base id; fut.gg files the card under id + 3 * 2**24
    card = _card("moorhouse--base", 81, _IMG.format("265856"))
    twin = _card("twin--base", 85, _IMG.format("1234"))
    for c in (card, twin):
        repo.upsert(c)
    item = 265856 + 3 * 2**24
    hub = '<a href="/players/265856-anna-moorhouse/27-{}/">x</a><a href="/players/265856-anna-moorhouse/26-265856/">old</a>'
    fetcher = _Fetcher({
        futgg_url_for(card): FetchError("could not fetch: HTTP Error 404"),
        "https://www.fut.gg/players/265856/": hub.format(item),
        f"https://www.fut.gg/players/265856/27-{item}/": _page(item, 81),
        futgg_url_for(twin): FetchError("could not fetch: HTTP Error 404"),
        "https://www.fut.gg/players/1234/": '<a href="/players/1234-t/27-111/"></a><a href="/players/1234-t/27-222/"></a>',
        "https://www.fut.gg/players/1234/27-111/": _page(111, 85),
        "https://www.fut.gg/players/1234/27-222/": _page(222, 85),     # two 85s: ambiguous
    })
    result = asyncio.run(upgrade_card_styles_async(repo, fetcher=fetcher))
    assert result.updated == ("moorhouse--base",)
    assert len(result.missed) == 1 and result.missed[0].startswith("twin--base")
    saved = repo.find_by_id("moorhouse--base")
    assert saved.subs is not None and ea_item_id(saved) == item     # next run joins directly
