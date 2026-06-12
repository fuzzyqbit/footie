# FC 26 Auto-Builder (`fc26 build`) — Design Spec (Phase 6)

**Date:** 2026-06-11
**Status:** Approved by user
**Project:** footie — FC 26 Playbook (PS5)
**Depends on:** Phases 1–5 (DB with prices, chem engine, builder package: meta/market/upgrade)

## Decisions (user-approved)

Seed-and-improve strategy with `--league` theming (option A): reuse the tested
greedy swap engine rather than building new search machinery.

## Scope & flow

```
fc26/builder/build.py    # seed_xi() + build_squad() (pure)
fc26/cli.py              # fc26 build --formation 4-2-3-1 --budget 500K
                         #   [--league "Premier League"] [--write squads/built.json] [--json]
```

1. **Pool**: all DB cards with a known price AND complete face stats. `--league`
   filters the pool via `canonical_league` (alias-aware, so "Premier League"
   matches "English Premier League" cards).
2. **Seed**: walk the formation's slots in order; for each, pick the **cheapest**
   pool card that is in-position (primary or alt) and does not name-match any
   already-seeded player (`_same_player` from `upgrade.py` — token-boundary
   rule, inherits the documented mononym limitation). If the seed's gross cost
   exceeds the budget → clean error: "budget too small to field a legal XI in
   <formation> (cheapest legal XI costs N)".
3. **Improve**: run the existing `find_upgrades` on the seeded lineup with
   `max_swaps=11` and remaining budget = budget − seed gross cost. The seeds
   are owned cards, so the upgrade engine's sell-at-95% net economics apply
   exactly as in `fc26 upgrade`.
4. **Output**: final XI table (slot, player, version, price, meta), chem
   summary (reusing ChemReport totals), total cost = seed spend + swap net
   spend, remaining budget. `--write` saves a squad file in the standard
   format (same shape `fc26 chem`/`fc26 upgrade` consume); name defaults to
   "Built <formation> (<budget>)".

## Errors

- Unknown formation → error listing available formations (reuses the chem
  phase's message style).
- Unknown/empty league filter (no pool cards match) → error naming the filter.
- Infeasible budget → the seed-cost error above.
- All errors are FC26Error → clean `error:` exit 1.

## Testing

- Synthetic-pool unit tests, hand-checked: seed picks cheapest legal card per
  slot; dedup blocks duplicate real players across slots (and allows distinct
  players); position/alt eligibility; infeasible-budget error message carries
  the cheapest-XI cost; league filter excludes non-matching cards (alias-aware
  test with "English Premier League" vs "Premier League"); improve phase
  upgrades a seeded slot when budget allows (hand-derived pick).
- CLI tests via CliRunner: happy path, `--json`, `--write` round-trips through
  `load_lineup` + `fc26 chem`, error paths clean.
- Real-DB CI guard: `fc26 build --formation 4-2-3-1 --budget 300K` runs clean,
  XI is legal (11 slots resolved, no duplicate real players), total cost ≤
  budget. No pinned names/prices.
- Coverage stays ≥80%.

## Non-goals

- Chemistry styles / boosted stats
- Multi-formation comparison ("which formation gives the best 500K team")
- Bench building
- EA-player-id dedup (mononym limitation inherited and documented)

## Success criteria

- `fc26 build --formation 4-2-3-1 --budget 500K --league "Premier League"`
  produces a legal, budget-respecting XI whose chem is reproducible via
  `fc26 chem` on the `--write` output.
- Infeasible budgets fail with the cheapest-XI cost named.
