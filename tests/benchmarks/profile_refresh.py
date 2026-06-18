"""BENCH-04 — cProfile the refresh write hot path (sudo-free).

Run from the repo root:

    python tests/benchmarks/profile_refresh.py

Profiles bulk-upserting the frozen corpus into an empty repo — the O(n^2)
whole-file-rewrite-per-card cost that dominates `fc26 refresh`. Prints the top
functions by cumulative time. No network, no sudo.

For a live, sampling profile of a real refresh, see the py-spy section in
README.md (macOS requires sudo + a SIP-exempt interpreter).
"""

from __future__ import annotations

import cProfile
import json
import pstats
import tempfile
from pathlib import Path

from fc26.db import CardRepository, card_from_dict

CORPUS = Path(__file__).parent / "golden" / "corpus.json"


def _bulk_upsert() -> None:
    cards = [card_from_dict(c) for c in json.loads(
        CORPUS.read_text(encoding="utf-8"))["cards"]]
    with tempfile.TemporaryDirectory() as d:
        repo = CardRepository(Path(d) / "players.json")
        for _ in range(5):  # amplify so the profile has signal
            for card in cards:
                repo.upsert(card)


def main() -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    _bulk_upsert()
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    print("=== refresh write hot path (cumulative time) ===")
    stats.print_stats(30)


if __name__ == "__main__":
    main()
