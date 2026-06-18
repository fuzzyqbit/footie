"""BENCH-03 — build/upgrade equivalence over a deterministic matrix.

build_squad + the greedy upgrade engine are deterministic (sorted candidates,
fixed tie-breaks). Phase 3 will optimise compute_chemistry / the search loop;
this goldens the chosen XI + costs over a formation x objective x budget matrix
so any output drift is caught.
"""

from __future__ import annotations

import pytest

from fc26.builder.build import build_squad

from .corpus import golden_check

# corpus fully covers these formations (CF/LWB/RWB excluded — not in source data)
FORMATIONS = ["4-2-3-1", "4-3-3", "4-4-2"]
OBJECTIVES = ["meta", "rating"]
BUDGETS = [1_000_000, 10_000_000, 500_000_000]


@pytest.mark.golden
def test_golden_build_matrix(corpus_cards):
    matrix = {}
    for formation in FORMATIONS:
        for objective in OBJECTIVES:
            for budget in BUDGETS:
                key = f"{formation}|{objective}|{budget}"
                result = build_squad(
                    formation, corpus_cards, budget=budget, objective=objective
                )
                matrix[key] = {
                    "seed_cost": result.seed_cost,
                    "total_cost": result.total_cost,
                    "xi": {slot: card.id for slot, card in result.slot_cards.items()},
                    "swaps": [
                        {"slot": s.slot, "in": s.in_id} for s in result.improve_plan.swaps
                    ],
                }
    golden_check("builder_matrix.json", matrix)
