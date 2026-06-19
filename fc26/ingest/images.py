"""HD card-art enrichment: pull full-size player render + frame from futbin detail pages.

The player-list crawl (futbin.py) only sees tiny w~64 thumbnails. Each card's
futbin detail page renders the same layers at HD (player render ~w=485, card
frame ~w=644). This module fetches those pages and upgrades the stored URLs.
All URLs are futbin's signed CDN links — stored, not downloaded (hotlinked).
"""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from typing import Callable

from selectolax.parser import HTMLParser

from ..db import CardRepository
from ..errors import FC26Error, ParseError
from ..models import Card

REQUEST_DELAY_SECONDS = 1.0
ABORT_CHECK_AFTER = 10        # attempts before the failure-ratio abort can trigger
ABORT_FAILURE_RATIO = 0.5
HD_MIN_WIDTH = 200            # below this a stored image_url is a list thumbnail, not HD

_WIDTH_RE = re.compile(r"[?&]w=(\d+)")


@dataclass(frozen=True)
class ImagesResult:
    upgraded: tuple[str, ...]
    skipped: tuple[str, ...]
    missed: tuple[str, ...]   # "card-id: reason"


def _width(url: str) -> int:
    m = _WIDTH_RE.search(url)
    return int(m.group(1)) if m else 0


def _largest(tree: HTMLParser, marker: str) -> str | None:
    """Largest-width <img> src containing marker; None if none match.

    Detail pages list the main card plus smaller related-card thumbnails, so the
    main render is reliably the widest of each layer.
    """
    best: str | None = None
    best_w = -1
    for img in tree.css("img"):
        src = img.attributes.get("src") or ""
        if marker in src and _width(src) > best_w:
            best, best_w = src, _width(src)
    return best


def _logo(tree: HTMLParser, alt: str) -> str | None:
    """First <img alt=alt> src, preferring a /dark/ variant when both exist.

    Crest/league/flag logos on a detail page all carry the same CDN id across
    widths; the dark variant matches the card overlay. Nation has no dark/light
    split, so the first match is returned for it.
    """
    fallback: str | None = None
    for img in tree.css("img"):
        if (img.attributes.get("alt") or "") != alt:
            continue
        src = img.attributes.get("src") or ""
        if not src:
            continue
        if "/dark/" in src:
            return src
        if fallback is None:
            fallback = src
    return fallback


def _common_name(tree: HTMLParser) -> str | None:
    """Short/known name carried as the alt text on the main player render.

    The page H1/og:title give the player's FULL legal name; only the
    /img/players/ render's alt holds the common name (e.g. "Balde" for
    "Alejandro Balde Martínez"). All renders share the same alt, so the
    largest-width one (the main card) is authoritative.
    """
    best: str | None = None
    best_w = -1
    for img in tree.css("img"):
        src = img.attributes.get("src") or ""
        if "/img/players/" in src and _width(src) > best_w:
            alt = (img.attributes.get("alt") or "").strip()
            best, best_w = (alt or None), _width(src)
    return best


@dataclass(frozen=True)
class PlayerArt:
    image_url: str | None
    bg_url: str | None
    club_url: str | None
    league_url: str | None
    nation_url: str | None
    common_name: str | None


def parse_player_art(html: str) -> PlayerArt:
    """All card-art fields for the main card on a futbin player detail page."""
    tree = HTMLParser(html)
    return PlayerArt(
        image_url=_largest(tree, "/img/players/"),
        bg_url=_largest(tree, "/img/cards/"),
        club_url=_logo(tree, "Club"),
        league_url=_logo(tree, "League"),
        nation_url=_logo(tree, "Nation"),
        common_name=_common_name(tree),
    )


def parse_player_images(html: str) -> tuple[str | None, str | None]:
    """(image_url, bg_url) for the main card on a futbin player detail page."""
    art = parse_player_art(html)
    return art.image_url, art.bg_url


# Each playstyle on a detail page is an anchor like:
#   <a ... class="playStyle-table-icon ... active psplus"><img ...>
#     <div class="slim-font ...">Power Shot</div></a>
# class "active" => the card HAS it; "psplus" => it's a PlayStyle+ (else regular).
# A detail page also lists RELATED cards' playstyle tables; each card's table is
# its own <div class="player-abilities-wrapper">, the first of which is the main
# card. We scope to that first wrapper so related cards never leak in.
_PLAYSTYLE_RE = re.compile(
    r'<a [^>]*class="([^"]*playStyle-table-icon[^"]*)"[^>]*>'
    r'.*?<div class="slim-font[^"]*">([^<]+)</div>',
    re.DOTALL,
)


def parse_player_playstyles(html: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(playstyles, playstyles_plus) for the main card on a detail page.

    Only "active" anchors count (inactive ones are styles the card lacks);
    "psplus" anchors are PlayStyle+. Scoped to the first
    player-abilities-wrapper (the main card) so related-card tables are ignored;
    falls back to the whole document if that wrapper is absent.
    """
    tree = HTMLParser(html)
    # The first player-abilities-wrapper is sometimes an empty placeholder, so
    # use the first wrapper that actually contains playstyle anchors as the main
    # card; fall back to the whole document if no wrapper has any.
    fragment = html
    for wrapper in tree.css("div.player-abilities-wrapper"):
        if wrapper.css_first("a.playStyle-table-icon") is not None:
            fragment = wrapper.html
            break
    playstyles: list[str] = []
    playstyles_plus: list[str] = []
    for css_class, name in _PLAYSTYLE_RE.findall(fragment or ""):
        if "active" not in css_class:
            continue
        label = name.strip()
        if "psplus" in css_class:
            playstyles_plus.append(label)
        else:
            playstyles.append(label)
    return tuple(playstyles), tuple(playstyles_plus)


def _has_hd_art(card: Card) -> bool:
    return card.image_url is not None and _width(card.image_url) >= HD_MIN_WIDTH


def upgrade_card_images(
    repo: CardRepository,
    *,
    fetch_html: Callable[[str], str],
    sleep: Callable[[float], None],
    on_progress: Callable[[str], None] = lambda _msg: None,
    refresh: bool = False,
    limit: int | None = None,
    workers: int = 1,
) -> ImagesResult:
    """Fetch each card's futbin detail page and upgrade image_url/bg_url to HD.

    Resumable: cards that already carry HD art are skipped unless refresh=True,
    so an interrupted run continues where it stopped.

    With workers > 1, detail pages are fetched concurrently in a thread pool but
    every repo.upsert runs on this (the consuming) thread, so there is exactly
    one writer to the JSON file — concurrent writers would clobber each other
    since each upsert rewrites the whole file. The per-fetch delay still runs in
    each worker thread, keeping the aggregate request rate polite.
    """
    skipped: list[str] = []
    todo: list[Card] = []
    for card in repo.find_all():
        if not card.futbin_url:
            skipped.append(card.id)
        elif not refresh and _has_hd_art(card):
            skipped.append(card.id)
        elif limit is not None and len(todo) >= limit:
            skipped.append(card.id)
        else:
            todo.append(card)

    upgraded: list[str] = []
    missed: list[str] = []
    attempts = 0
    failures = 0

    def _apply(card: Card, art: PlayerArt) -> None:
        if art.image_url is None and art.bg_url is None:
            missed.append(f"{card.id}: no card art on {card.futbin_url}")
        else:
            repo.upsert(replace(
                card,
                image_url=art.image_url or card.image_url,
                bg_url=art.bg_url or card.bg_url,
                club_url=art.club_url or card.club_url,
                league_url=art.league_url or card.league_url,
                nation_url=art.nation_url or card.nation_url,
                common_name=art.common_name or card.common_name,
            ))
            upgraded.append(card.id)
            on_progress(f"hd art {card.id}")

    def _aborting() -> bool:
        return attempts >= ABORT_CHECK_AFTER and failures / attempts > ABORT_FAILURE_RATIO

    if workers <= 1:
        for card in todo:
            attempts += 1
            try:
                html = fetch_html(card.futbin_url)
                sleep(REQUEST_DELAY_SECONDS)
                _apply(card, parse_player_art(html))
            except FC26Error as exc:
                failures += 1
                missed.append(f"{card.id}: {exc}")
            if _aborting():
                raise ParseError(
                    f"{failures}/{attempts} detail pages failed - futbin layout changed?"
                )
        return ImagesResult(tuple(upgraded), tuple(skipped), tuple(missed))

    def _fetch(card: Card) -> PlayerArt:
        html = fetch_html(card.futbin_url)
        sleep(REQUEST_DELAY_SECONDS)
        return parse_player_art(html)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch, card): card for card in todo}
        for future in as_completed(futures):
            card = futures[future]
            attempts += 1
            try:
                _apply(card, future.result())
            except FC26Error as exc:
                failures += 1
                missed.append(f"{card.id}: {exc}")
            if _aborting():
                for pending in futures:
                    pending.cancel()
                raise ParseError(
                    f"{failures}/{attempts} detail pages failed - futbin layout changed?"
                )

    return ImagesResult(tuple(upgraded), tuple(skipped), tuple(missed))


async def upgrade_card_images_async(
    repo: CardRepository,
    *,
    fetcher,
    on_progress: Callable[[str], None] = lambda _msg: None,
    refresh: bool = False,
    limit: int | None = None,
) -> ImagesResult:
    """Async sibling of :func:`upgrade_card_images` — byte-identical output.

    Detail pages are fetched concurrently (``gather`` preserves card order) but
    every ``repo.upsert`` runs SERIALLY on this consuming coroutine, in card
    order — exactly one writer. The output matches the deterministic
    ``workers=1`` order, NOT the sync ``workers>1`` ``as_completed`` order.
    """
    skipped: list[str] = []
    todo: list[Card] = []
    for card in repo.find_all():
        if not card.futbin_url:
            skipped.append(card.id)
        elif not refresh and _has_hd_art(card):
            skipped.append(card.id)
        elif limit is not None and len(todo) >= limit:
            skipped.append(card.id)
        else:
            todo.append(card)

    upgraded: list[str] = []
    missed: list[str] = []
    attempts = 0
    failures = 0

    def _apply(card: Card, art: PlayerArt) -> None:
        if art.image_url is None and art.bg_url is None:
            missed.append(f"{card.id}: no card art on {card.futbin_url}")
        else:
            repo.upsert(replace(
                card,
                image_url=art.image_url or card.image_url,
                bg_url=art.bg_url or card.bg_url,
                club_url=art.club_url or card.club_url,
                league_url=art.league_url or card.league_url,
                nation_url=art.nation_url or card.nation_url,
                common_name=art.common_name or card.common_name,
            ))
            upgraded.append(card.id)
            on_progress(f"hd art {card.id}")

    async def _fetch_async(card: Card):
        try:
            html = await fetcher.fetch(card.futbin_url)
            return card, parse_player_art(html), None
        except FC26Error as exc:
            return card, None, exc

    results = await asyncio.gather(*(_fetch_async(card) for card in todo))
    for card, art, exc in results:
        attempts += 1
        if exc is not None:
            failures += 1
            missed.append(f"{card.id}: {exc}")
        else:
            _apply(card, art)
        if attempts >= ABORT_CHECK_AFTER and failures / attempts > ABORT_FAILURE_RATIO:
            raise ParseError(
                f"{failures}/{attempts} detail pages failed - futbin layout changed?"
            )

    return ImagesResult(tuple(upgraded), tuple(skipped), tuple(missed))
