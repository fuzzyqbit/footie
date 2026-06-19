"""Bulk card expansion: ingest the live FUT pool from futbin list pages."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from ..db import CardRepository
from ..errors import FC26Error, ParseError
from ..models import Card
from .futbin import LIST_URL_TEMPLATE, ROWS_PER_FULL_PAGE, parse_futbin_page

REQUEST_DELAY_SECONDS = 1.0
ABORT_CHECK_AFTER = 5         # pages before the failure-ratio abort can trigger;
                              # runs with max_pages < 5 never abort, they just
                              # report failed_pages in the result
ABORT_FAILURE_RATIO = 0.5


@dataclass(frozen=True)
class ExpandResult:
    seen: int
    new: int
    merged: int
    failed_pages: tuple[str, ...]   # "url: reason"
    new_ids: tuple[str, ...] = ()   # ids of cards that were newly added


def expand_cards(
    repo: CardRepository,
    *,
    min_ovr: int,
    fetch_html: Callable[[str], str],
    sleep: Callable[[float], None],
    on_progress: Callable[[str], None] = lambda _msg: None,
    max_pages: int | None = None,
) -> ExpandResult:
    seen = 0
    new = 0
    merged = 0
    failed_pages: list[str] = []
    new_ids: list[str] = []

    page = 0
    attempts = 0
    while True:
        page += 1
        if max_pages is not None and page > max_pages:
            break
        url = LIST_URL_TEMPLATE.format(min_ovr=min_ovr, page=page)
        attempts += 1
        try:
            html = fetch_html(url)
            sleep(REQUEST_DELAY_SECONDS)
            cards = parse_futbin_page(html, source_url=url)
        except FC26Error as exc:
            failed_pages.append(f"{url}: {exc}")
            if attempts >= ABORT_CHECK_AFTER and len(failed_pages) / attempts > ABORT_FAILURE_RATIO:
                raise ParseError(
                    f"{len(failed_pages)}/{attempts} list pages failed - futbin layout changed?"
                ) from exc
            continue

        if not cards:
            break   # past the last page
        for card in cards:
            seen += 1
            card, existing = _resolve(repo, card)
            repo.upsert(card)
            if existing is None:
                new += 1
                new_ids.append(card.id)
            else:
                merged += 1
        on_progress(f"page {page}: {len(cards)} cards")
        if len(cards) < ROWS_PER_FULL_PAGE:
            break   # short page = last page

    return ExpandResult(seen, new, merged, tuple(failed_pages), tuple(new_ids))


async def expand_cards_async(
    repo: CardRepository,
    *,
    min_ovr: int,
    fetcher,
    on_progress: Callable[[str], None] = lambda _msg: None,
    max_pages: int | None = None,
) -> ExpandResult:
    """Async sibling of :func:`expand_cards` — byte-identical output.

    Stays SEQUENTIAL: pagination is data-dependent (the loop only knows page
    N+1 exists after parsing N) and ``_resolve`` suffixes id collisions using
    ``find_by_id`` over previously-upserted cards, so the upsert order must be
    preserved exactly. We only route each page fetch through the AsyncFetcher
    for connection reuse; the fetcher's HostRateLimiter supplies the politeness
    delay the sync path got from ``sleep``.
    """
    seen = 0
    new = 0
    merged = 0
    failed_pages: list[str] = []
    new_ids: list[str] = []

    page = 0
    attempts = 0
    while True:
        page += 1
        if max_pages is not None and page > max_pages:
            break
        url = LIST_URL_TEMPLATE.format(min_ovr=min_ovr, page=page)
        attempts += 1
        try:
            html = await fetcher.fetch(url)
            cards = parse_futbin_page(html, source_url=url)
        except FC26Error as exc:
            failed_pages.append(f"{url}: {exc}")
            if attempts >= ABORT_CHECK_AFTER and len(failed_pages) / attempts > ABORT_FAILURE_RATIO:
                raise ParseError(
                    f"{len(failed_pages)}/{attempts} list pages failed - futbin layout changed?"
                ) from exc
            continue

        if not cards:
            break   # past the last page
        for card in cards:
            seen += 1
            card, existing = _resolve(repo, card)
            repo.upsert(card)
            if existing is None:
                new += 1
                new_ids.append(card.id)
            else:
                merged += 1
        on_progress(f"page {page}: {len(cards)} cards")
        if len(cards) < ROWS_PER_FULL_PAGE:
            break   # short page = last page

    return ExpandResult(seen, new, merged, tuple(failed_pages), tuple(new_ids))


def _resolve(repo: CardRepository, card: Card) -> tuple[Card, Card | None]:
    """Resolve id collisions and return (card_to_upsert, existing_card_or_None).

    Two different special cards can share name+version (e.g. two TOTW IFs):
    when the id exists with a DIFFERENT ovr and the card is not a base card,
    suffix the id with the ovr so both survive. Base-card ovr drift (title
    updates) merges normally. The existing-card lookup doubles as the
    new-vs-merged signal so each card costs one repository read, not two.
    """
    existing = repo.find_by_id(card.id)
    if card.version != "base" and existing is not None and existing.ovr != card.ovr:
        suffixed = replace(card, id=f"{card.id}-{card.ovr}")
        return suffixed, repo.find_by_id(suffixed.id)
    return card, existing
