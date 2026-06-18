"""One-shot data refresh: bulk-expand the live pool, then enrich it.

Wraps the two scrape stages (expand -> enrich) so both the `fc26 refresh`
command and the server's daily auto-refresh run the exact same pipeline.
Every write goes through CardRepository.upsert, which merges into the
existing db atomically, so a partial or failed scrape never wipes good data.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..db import CardRepository, card_to_dict
from .enrich import EnrichResult, enrich_cards
from .expand import ExpandResult, expand_cards

MANIFEST_CARD_CAP = 200   # keep last_refresh.json small

DEFAULT_MIN_OVR = 84
DEFAULT_INTERVAL_HOURS = 72.0   # every 3 days — gentle on the source sites


def jittered_sleep(seconds: float) -> None:
    """Sleep `seconds` plus 0-100% random extra, so request timing isn't a
    fixed metronome that looks like a bot to rate-limiters."""
    time.sleep(seconds + random.uniform(0, seconds))


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
    manifest_path: Path | None = None,
) -> RefreshResult:
    # One batched write for the whole refresh: the ~2,400 upserts inside
    # expand_cards/enrich_cards (same repo) defer to a single flush at exit,
    # turning the per-card whole-file rewrite (O(n^2)) into one write. The
    # batch flushes even on exception, so a partial scrape still persists.
    with repo.batch():
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

    if manifest_path is not None:
        new_cards = []
        for card_id in expand.new_ids[:MANIFEST_CARD_CAP]:
            card = repo.find_by_id(card_id)
            if card is not None:
                new_cards.append(card_to_dict(card))
        payload = {
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "new_count": expand.new,
            "updated_count": expand.merged,
            "new_cards": new_cards,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return RefreshResult(expand=expand, enrich=enrich)
