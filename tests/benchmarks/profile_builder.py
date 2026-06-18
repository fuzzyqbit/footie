"""BENCH-04 — cProfile the build/upgrade compute hot path (sudo-free).

Run from the repo root:

    python tests/benchmarks/profile_builder.py

Profiles build_squad (which runs the greedy find_upgrades engine, the
compute_chemistry hot loop) over the frozen corpus. Prints the top functions by
cumulative time — the attribution Phase 3 uses to target memoization /
algorithmic work. No network, no sudo.
"""

from __future__ import annotations

import cProfile
import pstats
from pathlib import Path

from fc26.builder.build import build_squad
from fc26.db import CardRepository

CORPUS = Path(__file__).parent / "golden" / "corpus.json"
BUDGET = 500_000_000


def _build() -> None:
    pool = CardRepository(CORPUS).find_all()
    for _ in range(5):  # amplify so the profile has signal
        build_squad("4-2-3-1", pool, budget=BUDGET, objective="meta")
        build_squad("4-3-3", pool, budget=BUDGET, objective="rating")


def main() -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    _build()
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    print("=== build/upgrade compute hot path (cumulative time) ===")
    stats.print_stats(30)


if __name__ == "__main__":
    main()
