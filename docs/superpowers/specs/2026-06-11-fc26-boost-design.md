# FC 26 Chem Styles & Boosted Stats (`fc26 boost`) — Design Spec (Phase 7)

**Date:** 2026-06-11
**Status:** Approved by user
**Depends on:** Phases 1–6 (DB, chem engine, builder)

## Decisions (user-approved)

- Chem styles before acquisition planner (option B): `upgrade`/`build` underestimate
  boosted cards until styles exist.
- **Hybrid precision** (option C): sub-stat-exact when a card carries sub-stats
  (fut.gg adds), face-level approximation otherwise; output marks precision.

## Architecture

```
fc26/chem/styles.py     # STYLE_BOOSTS: style -> chem level (1/2/3) -> {sub_stat: +delta}
fc26/builder/boost.py   # boosted-stats engine (pure)
fc26/cli.py             # fc26 boost squads/x.json [--json]
fc26/chem/lineup.py     # slot values accept style objects (backward compatible)
```

### Style table (`styles.py`)

- Encoded at plan time from a current FC26 source (e.g. futbin/gamesradar chem-style
  list), source cited in the module docstring with fetch date. At least two styles
  spot-verified against a second source before pinning.
- Structure: `STYLE_BOOSTS: dict[str, dict[int, dict[str, int]]]` — style slug →
  chem level (1/2/3) → SubStats field name → positive delta. All 29 SubStats field
  names valid (unit-tested against the model).
- GK styles (e.g. Glove) included; GK sub-stats follow the established phase-2 slot
  mapping.

### Boost engine (`boost.py`)

Face-stat constituent subs (EA standard):
PAC ← {acceleration, sprint_speed} · SHO ← {positioning, finishing, shot_power,
long_shots, volleys, penalties} · PAS ← {vision, crossing, fk_accuracy,
short_passing, long_passing, curve} · DRI ← {agility, balance, reactions,
ball_control, dribbling, composure} · DEF ← {interceptions, heading_accuracy,
def_awareness, standing_tackle, sliding_tackle} · PHY ← {jumping, stamina,
strength, aggression}.

- `boosted_stats(card, style, chem_level) -> BoostResult`:
  - chem_level 0 or style None → unboosted, no markers.
  - Card HAS subs: boost each sub exactly (cap 99) → boosted SubStats; face delta =
    mean of that face's constituent deltas applied to the stored face stat (cap 99).
    Precision tier "subs".
  - Card lacks subs: face delta = mean of the style's deltas over the face's
    constituent subs (unboosted subs contribute 0), applied to stored face (cap 99).
    Precision tier "approx".
  - Faces are ALWAYS estimates (EA's true face weights are internal) — every boosted
    face renders with `≈`. Sub-level numbers (when present) are exact.
- Chem level per player comes from the existing `compute_chemistry`.

### Squad file extension (`lineup.py`)

`starting_xi` slot values accept either form:

```json
"ST": "kylian-mbappe--base"
"ST": {"id": "kylian-mbappe--base", "style": "hunter"}
```

- `Lineup.slots` stays `(slot_key, card_id)`; styles land in a parallel
  `Lineup.styles: dict[slot_key, str]` (absent slots = no style).
- Unknown style name → LineupError naming it and listing available styles.
- `chem`, `upgrade`, `build` ignore styles entirely (no behavior change; their
  tests must stay green untouched).

### CLI (`fc26 boost`)

- Table: slot, player, style, chem (0-3), boosted PAC/SHO/PAS/DRI/DEF/PHY rendered
  as `87≈(+5)` style; unstyled/0-chem rows plain.
- Warnings: styled player at 0 chem ("style has no effect"); approx-tier rows get a
  one-line hint ("add via fut.gg for sub-level precision") — once per run, not per row.
- `--json` emits full BoostResults.

## Testing

- Style table: structure test (every style has levels 1/2/3, all sub names valid,
  deltas positive ints), pinned values for ≥3 styles (incl. one GK style) with
  source-verified numbers.
- Boost math hand-checked: exact tier (subs present, incl. cap-99), approx tier,
  chem-0 no-op, unknown style error.
- Lineup: both slot-value forms parse; mixed squads; unknown style error lists
  available styles; old-format squads (all phases' committed files) still load.
- CLI: happy path, `--json`, error paths clean; real-DB CI guard (runs on the
  sample squad with styles added to a copy, no pinned stat numbers).
- Coverage ≥80%; existing 190-test suite stays green.

## Non-goals

- Style suggestion/optimization (acquisition-planner material)
- Style market prices
- Folding boosted stats into `upgrade`/`build` scoring (future enhancement, noted)

## Success criteria

- `fc26 boost` on a styled copy of the sample squad shows believable boosted faces
  with correct chem gating, and exact sub-level boosts for fut.gg-crawled cards
  (verified live with Rodri PTG: shadow at chem 3, sub-exact, cap-99 observed;
  additional cards gain the subs tier as they are added via `fc26 add`).
- Old squad files load unchanged; the full pre-existing suite passes untouched.
