"""HD backgrounds: one futbin detail fetch per distinct frame, applied to the whole group."""

from __future__ import annotations

import pytest

from fc26.db import CardRepository
from fc26.errors import RateLimitedError
from fc26.ingest.frames import upgrade_card_frames
from fc26.ingest.images import PlayerArt
from fc26.models import Card, FaceStats

_TINY = "https://cdn3.futbin.com/content/fifa27/img/cards/tiny/{}.png?w=64&s=a"
_HD = "https://cdn3.futbin.com/content/fifa27/img/cards/hd/{}.png?w=644&s=b"
_GG = "https://game-assets.fut.gg/cdn-cgi/image/width=512/2027/rarities-level-3-large/{}.abc.png"


def _card(card_id: str, ovr: int, bg: str) -> Card:
    return Card(id=card_id, player_name=card_id, version="base", ovr=ovr, position="ST",
                face=FaceStats(pac=90, sho=90, pas=80, dri=88, def_=40, phy=75),
                bg_url=bg, futbin_url=f"https://www.futbin.com/27/player/1/{card_id}")


def _art(bg: str) -> PlayerArt:
    return PlayerArt(image_url=None, bg_url=bg, club_url=None, league_url=None,
                     nation_url=None, common_name=None)


def test_one_fetch_per_frame_covers_every_card_including_futgg_framed(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")
    for c in (_card("g1", 85, _TINY.format("0_gold")), _card("g2", 90, _TINY.format("0_gold")),
              _card("g3", 82, _GG.format("0")),                 # overwritten by fut.gg earlier
              _card("h1", 88, _TINY.format("72_base_hero"))):
        repo.upsert(c)
    fetched = []
    monkeypatch.setattr("fc26.ingest.frames.parse_player_art",
                        lambda html: _art(_HD.format("72_base_hero" if "h1" in html else "0_gold")))
    result = upgrade_card_frames(repo, fetch_html=lambda u: (fetched.append(u) or u),
                                 sleep=lambda s: None)
    assert len(fetched) == 2                                    # 2 frames, 4 cards
    assert fetched[0].endswith("/g2")                           # highest-rated representative
    assert result.cards == 4 and result.missed == ()
    assert {c.id: c.bg_url for c in repo.find_all()} == {
        "g1": _HD.format("0_gold"), "g2": _HD.format("0_gold"), "g3": _HD.format("0_gold"),
        "h1": _HD.format("72_base_hero"),
    }
    # rerun: nothing to fetch
    again = []
    upgrade_card_frames(repo, fetch_html=lambda u: (again.append(u) or u), sleep=lambda s: None)
    assert again == []


def test_wrong_frame_on_page_is_a_miss_and_rate_limit_stops(tmp_path, monkeypatch):
    repo = CardRepository(tmp_path / "players.json")
    repo.upsert(_card("g1", 85, _TINY.format("0_gold")))
    monkeypatch.setattr("fc26.ingest.frames.parse_player_art", lambda html: _art(_HD.format("3_totw")))
    result = upgrade_card_frames(repo, fetch_html=lambda u: u, sleep=lambda s: None)
    assert result.cards == 0 and result.missed[0].startswith("0_gold:")

    def blocked(url):
        raise RateLimitedError("www.futbin.com blocked us (HTTP 403)", 3000)

    with pytest.raises(RateLimitedError):
        upgrade_card_frames(repo, fetch_html=blocked, sleep=lambda s: None)
