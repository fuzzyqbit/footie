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


@pytest.mark.benchmark
def test_bench_bulk_upsert_batched(benchmark, tmp_path):
    """The real refresh write pattern: all upserts inside one batch() → a single
    flush instead of one whole-file rewrite per card. This is the DATA-03 win."""
    import json

    from fc26.db import card_from_dict

    cards = [card_from_dict(c) for c in
             json.loads(corpus_path().read_text(encoding="utf-8"))["cards"]]

    def _setup():
        db = Path(tmp_path) / "players.json"
        if db.exists():
            db.unlink()
        CardRepository._reset_cache()
        return (CardRepository(db),), {}

    def _bulk(repo):
        with repo.batch():
            for card in cards:
                repo.upsert(card)

    benchmark.pedantic(_bulk, setup=_setup, rounds=5)
    final = CardRepository(Path(tmp_path) / "players.json").find_all()
    assert len(final) == len(cards)


# Simulated-latency fetch: every fetch costs a fixed delay, no network. The two
# upsert benches above measure write cost and CANNOT show the async fetch win
# (they have no latency); this one does — it proves enrich_cards_async overlaps
# fetches instead of serialising the sleeps.
_SIM_N = 24          # number of cards (= player-page fetches)
_SIM_LAT = 0.005     # simulated per-fetch latency in seconds


class _LatencyFetcher:
    """Async fetcher stub: each fetch sleeps a fixed latency, returns dummy HTML."""

    async def fetch(self, url: str) -> str:
        import asyncio
        await asyncio.sleep(_SIM_LAT)
        return "x"


@pytest.mark.benchmark
def test_bench_async_enrich_beats_sequential(benchmark, tmp_path, monkeypatch):
    """Async enrich wall-clock must be far below the sequential sum-of-sleeps.

    Sequential cost would be (N+1)*LAT (top-100 page + N player pages, one at a
    time). The async path resolves URLs serially (1 top-100 fetch) then gathers
    the N player-page fetches concurrently, so its wall-clock is a small number
    of latency rounds regardless of N. We assert it beats 0.4x the sequential
    baseline — wide headroom, so this fails only if concurrency regresses to
    serial, not on scheduling jitter.
    """
    import asyncio

    from fc26.ingest.enrich import enrich_cards_async
    from fc26.models import Card, FaceStats

    face = FaceStats(pac=90, sho=80, pas=80, dri=80, def_=80, phy=80)

    db = Path(tmp_path) / "players.json"
    CardRepository._reset_cache()
    repo = CardRepository(db)
    with repo.batch():
        for i in range(_SIM_N):
            repo.upsert(Card(id=f"p{i:03d}--base", player_name=f"P{i}", version="base",
                             ovr=88, position="ST", club="C"))

    monkeypatch.setattr("fc26.ingest.enrich.extract_player_urls",
                        lambda html: {f"p{i}": f"u{i}" for i in range(_SIM_N)})

    def parse(html, source_url):
        i = int(source_url[1:])
        return Card(id=f"p{i:03d}--base", player_name=f"P{i}", version="base", ovr=88,
                    position="ST", club="C", league="La Liga", nation="France", face=face)

    monkeypatch.setattr("fc26.ingest.enrich.parse_player_page", parse)

    fetcher = _LatencyFetcher()

    def _run():
        # refresh=True so every benchmark round re-fetches all N (idempotent cost).
        # batch() collapses the N upserts to a single flush so the measurement
        # reflects fetch concurrency, not write amplification.
        with repo.batch():
            return asyncio.run(enrich_cards_async(repo, fetcher=fetcher, refresh=True))

    result = benchmark.pedantic(_run, rounds=5, iterations=1)
    assert len(result.enriched) == _SIM_N

    sequential_baseline = (_SIM_N + 1) * _SIM_LAT     # analytic, no timed pass
    assert benchmark.stats.stats.mean < 0.4 * sequential_baseline
