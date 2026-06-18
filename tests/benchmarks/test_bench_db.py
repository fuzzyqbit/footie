"""BENCH-01 — db read/write benchmarks.

These measure the JSON-repository hot paths Phase 2 will optimise (full-file
re-parse on every read; whole-file rewrite on every upsert). Default-gated
benches run over the frozen corpus; one live-gated bench reads the real
~4.4 MB data/players.json for realistic-size numbers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fc26.db import CardRepository

from .corpus import load_corpus_repo

_REAL_DB = Path("data/players.json")


@pytest.mark.benchmark
def test_bench_find_all(benchmark, tmp_repo):
    cards = benchmark(tmp_repo.find_all)
    assert len(cards) == 40


@pytest.mark.benchmark
def test_bench_find_by_id(benchmark, tmp_repo):
    target = tmp_repo.find_all()[0].id
    found = benchmark(lambda: tmp_repo.find_by_id(target))
    assert found is not None and found.id == target


@pytest.mark.benchmark
def test_bench_upsert_one(benchmark, tmp_path):
    # Fresh repo per round so each upsert sees the same starting state.
    seed = load_corpus_repo(tmp_path).find_all()
    card = seed[0]

    def _setup():
        repo = load_corpus_repo(tmp_path)
        return (repo,), {}

    def _upsert(repo):
        repo.upsert(card)

    benchmark.pedantic(_upsert, setup=_setup, rounds=20)


@pytest.mark.benchmark
@pytest.mark.live
def test_bench_find_all_real_db(benchmark):
    if not _REAL_DB.exists():
        pytest.skip("real data/players.json not present")
    repo = CardRepository(_REAL_DB)
    cards = benchmark(repo.find_all)
    assert len(cards) > 2000
