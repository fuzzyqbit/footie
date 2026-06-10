"""Bulk enrichment: fill league/nation/face stats from fcratings player pages."""

from __future__ import annotations

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
