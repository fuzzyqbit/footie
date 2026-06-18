"""BENCH-01 — builder / chemistry compute benchmarks.

build_squad seeds a legal XI then runs the greedy swap engine (find_upgrades),
which calls compute_chemistry tens-to-hundreds of thousands of times per call —
the CPU hot path Phase 3 will optimise. Benched over the frozen corpus for
formations the corpus fully covers.
"""

from __future__ import annotations

import pytest

from fc26.builder.build import BUILD_MAX_SWAPS, build_squad
from fc26.builder.upgrade import find_upgrades
from fc26.chem.formations import FORMATIONS, slot_position

BUDGET = 500_000_000


@pytest.mark.benchmark
@pytest.mark.parametrize("formation,objective", [
    ("4-2-3-1", "meta"),
    ("4-3-3", "rating"),
])
def test_bench_build_squad(benchmark, corpus_cards, formation, objective):
    result = benchmark(
        lambda: build_squad(formation, corpus_cards, budget=BUDGET, objective=objective)
    )
    assert len(result.slot_cards) == len(FORMATIONS[formation])


@pytest.mark.benchmark
def test_bench_find_upgrades(benchmark, corpus_cards):
    # Seed a legal XI cheaply, then bench the greedy upgrade search directly.
    seed = build_squad("4-2-3-1", corpus_cards, budget=BUDGET, objective="meta")
    lineup, slot_cards = seed.lineup, dict(zip(
        [s for s, _ in seed.lineup.slots],
        [seed.slot_cards[s] for s, _ in seed.lineup.slots],
    ))
    plan = benchmark(lambda: find_upgrades(
        lineup, slot_cards, corpus_cards, budget=BUDGET, max_swaps=BUILD_MAX_SWAPS, objective="meta"
    ))
    assert plan is not None
