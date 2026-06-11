"""Bulk card expansion: ingest the live FUT pool from futbin list pages."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from ..db import CardRepository
from ..errors import FC26Error, ParseError
from ..models import Card
from .futbin import LIST_URL_TEMPLATE, ROWS_PER_FULL_PAGE, parse_futbin_page

REQUEST_DELAY_SECONDS = 1.0
ABORT_CHECK_AFTER = 5         # pages before the failure-ratio abort can trigger
ABORT_FAILURE_RATIO = 0.5


@dataclass(frozen=True)
class ExpandResult:
    seen: int
    new: int
    merged: int
    failed_pages: tuple[str, ...]   # "url: reason"


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
            card = _disambiguate(repo, card)
            existing = repo.find_by_id(card.id)
            repo.upsert(card)
            if existing is None:
                new += 1
            else:
                merged += 1
        on_progress(f"page {page}: {len(cards)} cards")
        if len(cards) < ROWS_PER_FULL_PAGE:
            break   # short page = last page

    return ExpandResult(seen, new, merged, tuple(failed_pages))


def _disambiguate(repo: CardRepository, card: Card) -> Card:
    """Two different special cards can share name+version (e.g. two TOTW IFs).

    When the id already exists with a DIFFERENT ovr and the card is not a base
    card, suffix the id with the ovr so both cards survive. Base-card ovr
    drift (title updates) merges normally.
    """
    if card.version == "base":
        return card
    existing = repo.find_by_id(card.id)
    if existing is not None and existing.ovr != card.ovr:
        return replace(card, id=f"{card.id}-{card.ovr}")
    return card
