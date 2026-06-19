"""Bulk enrichment: fill league/nation/face stats from fcratings player pages."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from ..db import CardRepository
from ..errors import FC26Error, ParseError
from ..models import Card, FACE_STAT_NAMES, slugify
from .discovery import ALL_CLUBS_URL, find_player_link, parse_all_clubs
from .fcratings import TOP100_URL, extract_player_urls
from .fcratings_player import parse_player_page

REQUEST_DELAY_SECONDS = 1.0
ABORT_CHECK_AFTER = 10        # attempts before the failure-ratio abort can trigger
ABORT_FAILURE_RATIO = 0.5


@dataclass(frozen=True)
class EnrichResult:
    enriched: tuple[str, ...]
    skipped: tuple[str, ...]
    missed: tuple[str, ...]   # "card-id: reason"


def is_enriched(card: Card) -> bool:
    if card.league is None or card.nation is None:
        return False
    return all(getattr(card.face, name) is not None for name in FACE_STAT_NAMES)


def _is_futgg(card: Card) -> bool:
    return bool(card.source_url and "fut.gg" in card.source_url)


def enrich_cards(
    repo: CardRepository,
    *,
    fetch_html: Callable[[str], str],
    sleep: Callable[[float], None],
    on_progress: Callable[[str], None] = lambda _msg: None,
    refresh: bool = False,
    limit: int | None = None,
) -> EnrichResult:
    enriched: list[str] = []
    skipped: list[str] = []
    missed: list[str] = []

    url_map = extract_player_urls(fetch_html(TOP100_URL))
    sleep(REQUEST_DELAY_SECONDS)
    club_urls: dict[str, str] | None = None   # fetched lazily, once
    club_pages: dict[str, str] = {}           # club URL -> fetched html

    attempts = 0
    failures = 0
    for card in repo.find_all():
        if _is_futgg(card):
            skipped.append(card.id)
            continue
        if card.version != "base":
            # fcratings only carries base cards; special versions are
            # enriched via `fc26 add <fut.gg URL>`
            skipped.append(card.id)
            continue
        if not refresh and is_enriched(card):
            skipped.append(card.id)
            continue
        if limit is not None and attempts >= limit:
            skipped.append(card.id)
            continue

        player_url = url_map.get(slugify(card.player_name))
        if player_url is None:
            player_url, club_urls = _discover_via_club(
                card, club_urls, club_pages, fetch_html, sleep, missed
            )
            if player_url is None:
                continue   # miss already recorded

        attempts += 1
        try:
            html = fetch_html(player_url)
            sleep(REQUEST_DELAY_SECONDS)
            fresh = parse_player_page(html, source_url=player_url)
            merged = repo.upsert(fresh)
            if merged.id != card.id:
                on_progress(
                    f"WARNING: page id {merged.id!r} != card id {card.id!r} "
                    f"- original card left unenriched"
                )
            enriched.append(merged.id)
            on_progress(f"enriched {merged.id} ({merged.nation}, {merged.league})")
        except FC26Error as exc:
            failures += 1
            missed.append(f"{card.id}: {exc}")
        # only parse/fetch attempts count toward the abort ratio;
        # URL-discovery misses (no club / not on page) do not
        if attempts >= ABORT_CHECK_AFTER and failures / attempts > ABORT_FAILURE_RATIO:
            raise ParseError(
                f"{failures}/{attempts} player pages failed - fcratings layout changed?"
            )
    return EnrichResult(tuple(enriched), tuple(skipped), tuple(missed))


async def enrich_cards_async(
    repo: CardRepository,
    *,
    fetcher,
    on_progress: Callable[[str], None] = lambda _msg: None,
    refresh: bool = False,
    limit: int | None = None,
) -> EnrichResult:
    """Async sibling of :func:`enrich_cards` — byte-identical output.

    Concurrency is added to fetching only: player URLs (including lazy club
    discovery) are resolved SERIALLY in ``find_all()`` order (so the shared
    club caches are never mutated concurrently), the player-page fetches run
    concurrently with per-card error isolation (``gather`` preserves card
    order), and every ``repo.upsert`` + ``on_progress`` runs SERIALLY in card
    order on this consuming coroutine — exactly one writer. The fetcher's
    HostRateLimiter supplies the politeness delay the sync path got from
    ``sleep``, so there is no separate sleep call.
    """
    enriched: list[str] = []
    skipped: list[str] = []
    missed: list[str] = []

    url_map = extract_player_urls(await fetcher.fetch(TOP100_URL))
    club_urls: dict[str, str] | None = None   # fetched lazily, once (serial)
    club_pages: dict[str, str] = {}           # club URL -> fetched html

    # --- serial pre-pass: skip rules + URL resolution in card order ---
    todo: list[tuple[Card, str]] = []
    resolved = 0   # mirrors the sync `attempts` at the limit-check moment
    for card in repo.find_all():
        if _is_futgg(card):
            skipped.append(card.id)
            continue
        if card.version != "base":
            skipped.append(card.id)
            continue
        if not refresh and is_enriched(card):
            skipped.append(card.id)
            continue
        if limit is not None and resolved >= limit:
            skipped.append(card.id)
            continue

        player_url = url_map.get(slugify(card.player_name))
        if player_url is None:
            player_url, club_urls = await _discover_via_club_async(
                card, club_urls, club_pages, fetcher, missed
            )
            if player_url is None:
                continue   # miss already recorded

        resolved += 1
        todo.append((card, player_url))

    # --- concurrent fetch + parse, error-isolated (gather preserves order) ---
    async def _work(card: Card, url: str):
        try:
            html = await fetcher.fetch(url)
            return card, parse_player_page(html, source_url=url), None
        except FC26Error as exc:
            return card, None, exc

    results = await asyncio.gather(*(_work(card, url) for card, url in todo))

    # --- serial upsert in card order (single writer); on_progress here only ---
    attempts = 0
    failures = 0
    for card, fresh, exc in results:
        attempts += 1
        if exc is not None:
            failures += 1
            missed.append(f"{card.id}: {exc}")
        else:
            merged = repo.upsert(fresh)
            if merged.id != card.id:
                on_progress(
                    f"WARNING: page id {merged.id!r} != card id {card.id!r} "
                    f"- original card left unenriched"
                )
            enriched.append(merged.id)
            on_progress(f"enriched {merged.id} ({merged.nation}, {merged.league})")
        if attempts >= ABORT_CHECK_AFTER and failures / attempts > ABORT_FAILURE_RATIO:
            raise ParseError(
                f"{failures}/{attempts} player pages failed - fcratings layout changed?"
            )
    return EnrichResult(tuple(enriched), tuple(skipped), tuple(missed))


async def _discover_via_club_async(
    card: Card,
    club_urls: dict[str, str] | None,
    club_pages: dict[str, str],
    fetcher,
    missed: list[str],
) -> tuple[str | None, dict[str, str] | None]:
    """Serial club discovery for the async path (mirrors _discover_via_club)."""
    if not card.club:
        missed.append(f"{card.id}: no club on card and not on top-100 page")
        return None, club_urls
    if club_urls is None:
        club_urls = parse_all_clubs(await fetcher.fetch(ALL_CLUBS_URL))
    club_url = club_urls.get(card.club) or club_urls.get(slugify(card.club))
    if club_url is None:
        missed.append(f"{card.id}: club {card.club!r} not found on fcratings")
        return None, club_urls
    if club_url not in club_pages:
        club_pages[club_url] = await fetcher.fetch(club_url)
    player_url = find_player_link(club_pages[club_url], card.player_name)
    if player_url is None:
        missed.append(f"{card.id}: not found on club page {club_url}")
        return None, club_urls
    return player_url, club_urls


def _discover_via_club(
    card: Card,
    club_urls: dict[str, str] | None,
    club_pages: dict[str, str],
    fetch_html: Callable[[str], str],
    sleep: Callable[[float], None],
    missed: list[str],
) -> tuple[str | None, dict[str, str] | None]:
    if not card.club:
        missed.append(f"{card.id}: no club on card and not on top-100 page")
        return None, club_urls
    if club_urls is None:
        club_urls = parse_all_clubs(fetch_html(ALL_CLUBS_URL))
        sleep(REQUEST_DELAY_SECONDS)
    club_url = club_urls.get(card.club) or club_urls.get(slugify(card.club))
    if club_url is None:
        missed.append(f"{card.id}: club {card.club!r} not found on fcratings")
        return None, club_urls
    if club_url not in club_pages:
        club_pages[club_url] = fetch_html(club_url)
        sleep(REQUEST_DELAY_SECONDS)
    player_url = find_player_link(club_pages[club_url], card.player_name)
    if player_url is None:
        missed.append(f"{card.id}: not found on club page {club_url}")
        return None, club_urls
    return player_url, club_urls
