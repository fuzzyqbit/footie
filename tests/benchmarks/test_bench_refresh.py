"""BENCH-01 — refresh write-cost benchmark.

The dominant, deterministic cost of `fc26 refresh` is the write amplification:
CardRepository.upsert re-reads + rewrites the entire players.json for *every*
card (O(n^2) over a run). This benches that hotspot directly by bulk-upserting
the whole corpus into an empty repo — exactly the cost Phase 2's batched/atomic
writes will collapse.

The network fetch stages (expand listing pages, enrich per-card pages) are
deliberately excluded: they are I/O-bound, rate-limited by design, and are
Phase 4's concern. They are also not offline-reproducible here (expand needs
listing HTML fixtures; enrich skips already-complete corpus cards). See
README.md for the rationale.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fc26.db import CardRepository

from .corpus import corpus_path


@pytest.mark.benchmark
def test_bench_bulk_upsert(benchmark, tmp_path):
    import json

    cards_payload = json.loads(corpus_path().read_text(encoding="utf-8"))["cards"]
    from fc26.db import card_from_dict

    cards = [card_from_dict(c) for c in cards_payload]

    def _setup():
        db = Path(tmp_path) / "players.json"
        if db.exists():
            db.unlink()
        return (CardRepository(db),), {}

    def _bulk(repo):
        for card in cards:
            repo.upsert(card)

    result = benchmark.pedantic(_bulk, setup=_setup, rounds=5)
    # sanity: final repo holds the whole corpus
    final = CardRepository(Path(tmp_path) / "players.json").find_all()
    assert len(final) == len(cards)
