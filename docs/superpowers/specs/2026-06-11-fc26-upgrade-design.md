# FC 26 Squad Upgrader (`fc26 upgrade`) — Design Spec (Phase 5)

**Date:** 2026-06-11
**Status:** Approved by user
**Project:** footie — FC 26 Playbook (PS5)
**Depends on:** Phases 1–4 (player DB 2,434 cards with live prices, enrichment, expansion, chemistry engine + squad files)

## Context & decisions

User decisions from brainstorming:

- **Upgrader before auto-builder** (option B): improve an existing squad file with
  budgeted swap suggestions. The full-XI `fc26 build` optimizer is the next phase
  and will reuse this phase's scoring and candidate machinery.
- **Meta score, not raw OVR** (option B): per-position weighted face stats — the
  playbook's pace-meta philosophy (docs/02, docs/09) encoded as a visible,
  tunable weight table.
- **Net budget semantics** (option B): a swap costs
  `incoming.price − 95% × outgoing resale` (EA's 5% transfer tax); selling the
  replaced card funds the upgrade.

## Architecture

```
fc26/builder/
  __init__.py
  meta.py       # per-position face-stat weights + meta_score(card, slot_position)
  market.py     # budget parsing, net swap cost (5% sell tax), resale rules
  upgrade.py    # find_upgrades(...) -> UpgradePlan (pure, injectable-free)
fc26/cli.py     # new: fc26 upgrade <squad-file> --budget B [--swaps N] [--write OUT] [--json]
```

All computation is pure (mirrors `chem/engine.py`): `find_upgrades` takes the
lineup, resolved slot cards, the full card pool, and a budget — no I/O.

## Algorithm — greedy iterative swap search

1. Score the current squad: `squad_score = Σ meta_score(card, slot_position) +
   CHEM_WEIGHT × team_chem` (chem from the existing pure engine).
2. Per slot, build the candidate pool: every DB card playable in the slot
   position (primary or alt), not the same real player as any XI member, with a
   known price.
3. For each candidate compute the full effect of the swap: re-run
   `compute_chemistry` on the swapped XI (pure + fast), Δmeta, Δchem,
   Δsquad_score, and net cost.
4. Apply the best affordable swap (highest Δscore; tie-break higher
   Δscore-per-coin), deduct the budget, and repeat until the `--swaps` cap
   (default 3), the budget is exhausted, or no positive-Δscore swap remains.

Greedy is not globally optimal — documented trade-off. It is transparent (every
suggestion independently justified), and fast: ~2,400 cards × 11 slots ×
O(11) chem recompute per round is trivial.

Scale check: a full round evaluates ≲ 2,400 candidates; each evaluation re-runs
the pure chem engine on 11 cards. Three rounds complete in well under a second.

## Meta weights (`meta.py`)

One visible table, position → weights over the six face stats, each row summing
to 1.0 (unit-tested). Draft values (tunable constants):

| Pos | PAC | SHO | PAS | DRI | DEF | PHY |
|---|---|---|---|---|---|---|
| ST | .30 | .35 | .05 | .20 | .00 | .10 |
| RW / LW / RM / LM | .35 | .20 | .15 | .25 | .00 | .05 |
| CAM / CF | .15 | .25 | .25 | .25 | .00 | .10 |
| CM | .15 | .15 | .25 | .20 | .15 | .10 |
| CDM | .10 | .05 | .20 | .15 | .30 | .20 |
| RB / LB / RWB / LWB | .30 | .05 | .10 | .15 | .25 | .15 |
| CB | .25 | .03 | .07 | .05 | .35 | .25 |
| GK | .25 | .20 | .05 | .30 | .05 | .15 |

The GK row reads as DIV/HAN/KIC/REF/SPD/POS — the DB stores GK stats in the six
face slots under that mapping (established in phase 2).

- `meta_score(card, position)` = weighted sum on the 0–99 scale. Cards missing
  any face stat score None and are excluded from candidacy with a warning
  (currently ~0 such cards — everything is enriched).
- `CHEM_WEIGHT = 3.0` (visible constant): full 33 team chem ≈ one elite player's
  worth of meta. The report always shows Δmeta and Δchem separately so the
  composite never hides a chemistry sacrifice.

## Market rules (`market.py`)

- `parse_budget("100K" / "1.2M" / "50000")` — same semantics as futbin's
  `parse_price` (shared/re-exported, not duplicated).
- `net_cost(incoming, outgoing_resale) = incoming.price − int(0.95 ×
  outgoing_resale)`. Resale = the outgoing card's DB price; **price None →
  resale 0, flagged** in the swap row ("resale unknown — treated as 0").
  Negative net cost is allowed — a better-AND-cheaper swap is shown only when
  Δscore > 0.
- Incoming candidates require a known price (None → unbuyable → excluded;
  extinct/SBC items aren't on the market anyway).

## Hard constraints (enforced in `upgrade.py`)

1. **One real player per XI** (FUT rule): a candidate is excluded when its
   slugified player name matches — or contains/is contained by — any current XI
   member's name slug. This containment heuristic also bridges the known
   dual-id wart (futbin "Cristiano Ronaldo dos Santos Aveiro" vs fut.gg
   "Cristiano Ronaldo"). Implementation refinement: token-boundary prefix
   extension only (bare substring over-blocked 44 real pairs, e.g.
   Rodri/Rodrigo De Paul). KNOWN residual over-block: mononym Icon/Hero cards
   ("Cole" = Ashley Cole blocks "Cole Palmer"; "Gabriel" blocks
   "Gabriel Martinelli") — ~10 mononyms affected; name-only matching cannot
   resolve these. Proper fix is EA-player-id dedup (ids exist in futbin/fut.gg
   URLs), deferred to a later phase.
2. **In-position only**: the candidate's position or alt_positions must include
   the slot position (out-of-position = 0 chem; never suggested).
3. The budget is never exceeded (running total of net costs).
4. Each slot is swapped at most once per run.

## CLI surface

```
fc26 upgrade squads/my-team.json --budget 100K               # top 3 swaps
fc26 upgrade squads/my-team.json --budget 100K --swaps 5
fc26 upgrade squads/my-team.json --budget 100K --write squads/upgraded.json
fc26 upgrade ... --json
```

- Output: one row per swap — slot, OUT (name, version, resale), IN (name,
  version, price), net cost, Δmeta, Δchem — then totals: spend, remaining
  budget, squad score before → after, team chem before → after.
- `--write` saves the upgraded lineup as a NEW squad file (never overwrites the
  input).
- Squad-file problems reuse the `LineupError` clean-exit paths. No positive
  swap within budget → friendly "no upgrades found within budget", exit 0.
- Warnings carried into output: resale-unknown, dedup-heuristic fired,
  candidates skipped for missing face stats.

## Testing

- Pure-unit tests with small synthetic pools, hand-computed picks: budget
  exclusion, net-cost math (5% tax, rounding), dedup blocks the same player
  (incl. a containment-variant name), chem-aware choice (composite picks a
  chem-preserving candidate over a higher-meta chem-wrecker), greedy ordering,
  `--swaps` cap, no-upgrade case, negative-net-cost swap.
- `meta.py` sanity: every weight row sums to 1.0; every VALID_POSITION covered;
  meta_score hand-checked for one card per archetype.
- CLI tests via CliRunner (tmp DB), including `--write` output validity (the
  written file loads via `load_lineup` and resolves).
- One CI integration guard against the real DB + `squads/sample-rivals.json`:
  asserts a clean run and that every suggested swap reports positive Δscore
  (no pinned names/prices — the market drifts).

## Non-goals (later phases)

- Full-XI auto-builder (`fc26 build`)
- Chemistry styles & boosted stats
- Live price refresh during a run (uses DB prices; `fc26 expand` refreshes)
- Transfer-market tactics (bid sniping, price history)
- Bench/sub management

## Success criteria

- `fc26 upgrade squads/sample-rivals.json --budget 200K` produces sensible
  suggestions whose Δchem is reproducible by running `fc26 chem` on the
  `--write` output.
- Every hard constraint unit-proven; weight rows sum-tested.
- Coverage stays ≥80%.
