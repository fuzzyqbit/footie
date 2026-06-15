"""One-shot data refresh: bulk-expand the live pool, then enrich it.

Wraps the two scrape stages (expand -> enrich) so both the `fc26 refresh`
command and the server's daily auto-refresh run the exact same pipeline.
Every write goes through CardRepository.upsert, which merges into the
existing db atomically, so a partial or failed scrape never wipes good data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..db import CardRepository
from .enrich import EnrichResult, enrich_cards
from .expand import ExpandResult, expand_cards

DEFAULT_MIN_OVR = 84


@dataclass(frozen=True)
class RefreshResult:
    expand: ExpandResult
    enrich: EnrichResult


def refresh_data(
    repo: CardRepository,
    *,
    min_ovr: int = DEFAULT_MIN_OVR,
    fetch_html: Callable[[str], str],
    sleep: Callable[[float], None],
    on_progress: Callable[[str], None] = lambda _msg: None,
    enrich_limit: int | None = None,
) -> RefreshResult:
    on_progress(f"expand: scraping live pool (min_ovr={min_ovr})")
    expand = expand_cards(
        repo,
        min_ovr=min_ovr,
        fetch_html=fetch_html,
        sleep=sleep,
        on_progress=on_progress,
    )
    on_progress(f"expand done: {expand.new} new, {expand.merged} updated")

    on_progress("enrich: filling league/nation/face stats")
    enrich = enrich_cards(
        repo,
        fetch_html=fetch_html,
        sleep=sleep,
        on_progress=on_progress,
        limit=enrich_limit,
    )
    on_progress(f"enrich done: {len(enrich.enriched)} enriched")

    return RefreshResult(expand=expand, enrich=enrich)
