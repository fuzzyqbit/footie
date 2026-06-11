# FC 26 Chemistry Engine (`fc26 chem`) — Design Spec (Phase 4)

**Date:** 2026-06-11
**Status:** Design approved by user in brainstorming (2026-06-10); spec pending review
**Project:** footie — FC 26 Playbook (PS5)
**Depends on:** Phases 1–3 (player DB, enrichment, expansion — DB now holds 2,434 cards incl. specials and Icons/Heroes)

## Context & decisions

User decisions from brainstorming: lineup defined in a **JSON squad file** (option A — the
file becomes the shared artifact for the squad-builder phase); **chemistry points only**
(option A — chem styles and boosted stats deferred to the squad-builder phase).

### Verified FC26 chemistry rules

Source: fifauteam.com/fc-26-chemistry (fetched 2026-06-10), cross-checked against
TheGamer/teamgullit search results. Encoded as constants, cited in `rules.py`:

- Per-player chemistry: 0–3 points. Out-of-position players get **zero chemistry and
  contribute nothing** to any threshold.
- Thresholds (players needed → points contributed to each in-position sharer):
  - Club: 2→1, 4→2, 7→3
  - Nation: 2→1, 5→2, 8→3
  - League: 3→1, 5→2, 8→3
- Player chem = club points + nation points + league points (+ manager bonus), capped at 3.
- Counts include the player themself.
- **Icons:** always 3 chem when in their preferred position; count **2× toward their
  nation** and **1× toward every league**.
- **Heroes:** always 3 chem in position; count **1× toward nation, 2× toward their league**.
- **Manager:** optional; players sharing the manager's nation OR league get +1 (a single
  +1 — no double-stacking), still capped at 3 total.
- Substitutes get no chemistry (only the starting XI is modeled).

## Architecture

```
fc26/chem/
  __init__.py
  rules.py        # thresholds + icon/hero/manager constants (source-cited)
  aliases.py      # league/nation/club canonicalization across the 3 vocabularies
  formations.py   # formation name → ordered slot definitions
  lineup.py       # Lineup frozen model + JSON load/validate
  engine.py       # compute_chemistry(lineup, cards) -> ChemReport (pure)
squads/           # user lineup files (committed; sample file is a living fixture)
fc26/cli.py       # new: fc26 chem <squad-file> [--json]
```

`compute_chemistry` is pure: takes a Lineup and resolved Cards, no I/O — same
testability pattern as the enrich/expand orchestrators.

### Icon/Hero detection (data-driven heuristic, documented)

- Icon: `card.league == "Icons"` (futbin pseudo-league, 330 cards) OR the version
  contains the word "Icon" (case-insensitive).
- Hero: version contains "Hero" (e.g. futbin "Base Heroes").
- Neither flag exists on the schema — detection lives in `rules.py` helpers
  (`is_icon(card)`, `is_hero(card)`) so a future schema field can replace the
  heuristic without touching the engine.

## Canonicalization (`aliases.py`)

All equality comparisons go through `canonical_league / canonical_nation /
canonical_club` = slugify + explicit alias dict. The DB currently mixes three
vocabularies (fcratings, fut.gg, futbin). Divergences enumerated by the phase-3
final review against the real 2,434-card DB:

**League alias pairs (futbin ↔ fcratings):**
Premier League ↔ English Premier League · Bundesliga ↔ German Bundesliga ·
Ligue 1 McDonald's ↔ French Ligue 1 · Serie A TIM ↔ Italian Serie A ·
LALIGA EA SPORTS ↔ Spanish La Liga · MLS ↔ USA Major League Soccer ·
ROSHN Saudi League ↔ Saudi Pro League · Liga Portugal ↔ Portuguese Primeira Liga
(plus any single-source synonyms found at implementation time — the alias table is
generated against the live DB and tested against it).

**Pseudo-leagues:** "Icons" and "Men's National" are not chem leagues — Icons get the
icon rule; "Men's National" cards (national-team items) count toward nation and club
normally, league contribution none. Women's leagues stay distinct (they are real
chem leagues in FUT).

**Nations:** mostly identical across sources; two real divergences found against the
live DB (2026-06-11) and aliased: Holland ↔ Netherlands, Czech Republic ↔ Czechia.

**Club alias pairs:** Arsenal ↔ Arsenal F.C. · Real Madrid ↔ Real Madrid CF ·
Manchester City ↔ Manchester City F.C. · Juventus ↔ Juventus FC ·
Aston Villa ↔ Aston Villa F.C. · Everton ↔ Everton F.C. · Celtic ↔ Celtic F.C. ·
Al Nassr ↔ Al-Nassr FC · Athletic Club ↔ Athletic club. Canonicalization strips
F.C./FC/CF suffixes and case.

Unknown strings pass through slugified — never crash. The chem report flags cards
with null league/nation rather than silently treating them as no-match.

## Lineup file (`squads/*.json`)

```json
{
  "name": "My Rivals Team",
  "formation": "4-2-3-1",
  "manager": {"league": "Premier League", "nation": "Spain"},
  "starting_xi": {
    "GK": "thibaut-courtois--base",
    "RB": "achraf-hakimi--base",
    "CB1": "virgil-van-dijk--base",
    "CB2": "william-saliba--base",
    "LB": "theo-hernandez--base",
    "CDM1": "rodri--festival-of-football-path-to-glory",
    "CDM2": "declan-rice--base",
    "CAM": "jude-bellingham--base",
    "RW": "lamine-yamal--base",
    "LW": "vini-jr--base",
    "ST": "kylian-mbappe--base"
  }
}
```

- Slot keys come from the formation definition. `formations.py` defines 12 standard
  formations (from docs/03): 4-2-3-1, 4-3-3, 4-4-2, 4-2-2-2, 4-1-2-1-2, 3-5-2,
  5-2-1-2, 5-3-2, 4-5-1, 4-3-2-1, 3-4-3, 4-1-4-1. Numbered suffixes (CB1/CB2)
  disambiguate duplicate positions; a slot's chem position = the suffix-stripped key.
- In-position = slot position ∈ {card.position} ∪ card.alt_positions.
- `manager` optional; either key optional within it.
- Validation lists ALL errors at once (house style): unknown formation (with the
  available list), missing/extra slots, card id not in DB, duplicate card across
  slots, malformed JSON — clean `error:` exit 1.

## Output (`fc26 chem squads/my-team.json [--json]`)

- Per-player table: slot, player, version, in-position ✓/✗, chem 0–3.
- Team total N/33.
- Threshold breakdown grouped by club/league/nation with counts and **near-miss
  hints** ("Premier League: 4 players → tier 1; +1 player → tier 2").
- Warnings for cards with unknown league/nation ("run `fc26 add <fut.gg URL>`").
- `--json` emits the full ChemReport machine-readably.

## Testing

- Engine pure-unit tests against hand-computed squads: full-chem core squad, split
  squad, out-of-position cases (0 chem + 0 contribution), icon weighting (2× nation,
  1× every league), hero weighting, manager bonus + cap at 3, unknown-league card
  flagged.
- Alias tests pinned to REAL strings from the live DB (both vocabularies per pair).
- Lineup validation tests for every error case; formation definitions sanity-tested
  (each formation has exactly 11 slots, all positions valid).
- CLI tests via CliRunner with a tmp DB.
- A sample squad file committed in `squads/` built from real card ids — living
  fixture + user's starter template.
- Coverage stays ≥80%.

## Known wart (inherited, handled at report level)

The same real-world card can exist under two ids across vocabularies (futbin
full-name `cristiano-ronaldo-dos-santos-aveiro--tots` vs fut.gg
`cristiano-ronaldo--team-of-the-season-tots`). Chem computes whatever ids the lineup
references — dedup is a squad-builder-phase concern. The spec notes it so nobody
mistakes it for a chem bug.

## Non-goals (later phases)

- Chemistry styles & boosted stats (squad builder)
- Auto-XI optimization, acquisition suggestions
- Bench/sub chem (subs get none — only XI modeled)
- Evolutions special-casing
- Cross-vocabulary card dedup

## Success criteria

- `fc26 chem` on the committed sample squad reports chem matching a hand calculation
  documented in the test file.
- Out-of-position, icon, hero, manager, and cap rules each unit-proven.
- Alias table resolves every league/club pair listed above (tested against the live
  DB strings).
- Unknown-league cards produce a visible warning, never a silent zero.
