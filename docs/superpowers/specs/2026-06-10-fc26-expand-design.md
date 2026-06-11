# FC 26 Bulk Card Expansion (`fc26 expand`) — Design Spec (Phase 3)

**Date:** 2026-06-10
**Status:** Approved by user (direction approved in discussion; spec pending review)
**Project:** footie — FC 26 Playbook (PS5)
**Depends on:** Phase 1 (player DB), Phase 2 (enrichment)

## Context

The DB holds 131 cards: fcratings base cards (top-100 + pace-list extras) plus two
hand-added specials. The user wants the full live card pool from a rating floor up
("87 and up"): FUT special cards (TOTW/TOTS/TOTY/promos/Icons/Heroes) accumulate all
year and number in the thousands — ~2,360 cards at 87+ as of 2026-06-10.

Source feasibility (verified live during brainstorming):

- **futbin.com player list is server-rendered and crawlable** (earlier "403" finding
  from the docs/09 era is stale). `https://www.futbin.com/players?player_rating={min}-99&page={n}`
  returns 30 players/page; 87+ = 79 pages.
- **Each row carries a full card payload:** name, OVR, card version (TOTY, TOTS,
  Icon, Hero, IF, …), position + alt positions ("ST ++ CAM, RW"), nation, league,
  club (as `title` attributes on row icons), the six face stats, skill moves, weak
  foot, height, AcceleRATE, and the **live market price** (e.g. "3.02M").
- Per-card deep data (29 sub-stats, PlayStyles/PlayStyles+) is NOT in rows — that
  remains the fut.gg per-card path (`fc26 add`).
- fut.gg/futwiz list pages and easysbc remain JS-shells or behind anti-bot; futbin
  list is the one workable bulk source.

FUT includes women players (e.g. Alessia Russo) — they are real FUT cards and are
ingested like any other.

## Scope

One new CLI command:

```
fc26 expand --min-ovr 87              # crawl futbin list, upsert all cards >= 87
fc26 expand --min-ovr 90 --max-pages 5  # cap pages (testing / partial runs)
```

### Flow

1. Fetch `https://www.futbin.com/players?player_rating={min}-99&page={n}` for
   n = 1, 2, … until a page yields fewer than 30 rows (last page) or `--max-pages`.
2. Parse each row → `Card`: id = `make_card_id(name, version)`, version verbatim
   from the row badge ("TOTY", "TOTS", "Icon", "IF", "base" when the badge is the
   plain gold/rare kind), ovr, position + alt_positions, face stats, skill_moves,
   weak_foot, height_cm, accelerate, club/league/nation (verbatim futbin strings),
   price (parsed from "3.02M"/"750K"/"12,500" forms → integer coins),
   source_url = the list page URL, crawled_at = today.
3. Upsert through existing merge rules. fut.gg-sourced cards stay protected
   (futbin is not fut.gg, so a fut.gg card's fields win unless null).
4. Politeness: 1 request/second (existing pattern), honest User-Agent,
   `--max-pages` cap available.

### Behavior

- **Idempotent:** re-running upserts the same ids; price/crawled_at update (prices
  move daily — that is desired), everything else stable unless futbin data changed.
- **Failure handling:** page fetch/parse failure after 1 retry → record, continue;
  >50% of first 5 pages failing → abort with "futbin layout changed?" (mirrors the
  enrich abort guard).
- **Row sanity floor:** a parsed page yielding 0 cards while claiming to be a list
  page → ParseError (layout drift detection).
- **Versions normalization:** futbin badge text stored verbatim as `version`
  except the plain base-card badges (gold/rare/common markers) which map to
  `"base"` so ids collide correctly with the existing fcratings base cards and
  merge enrichment into them.

## Data model

No schema change. `price` (already on Card, unused until now) gets populated.
Base-card rows merge into existing enriched cards by id; special versions create
new cards (`ousmane-dembele--toty`).

## New files

```
fc26/ingest/futbin.py     # list-page row parser + pagination iterator (pure)
fc26/ingest/expand.py     # orchestrator (injectable fetch/sleep, like enrich)
# plus: `expand` command in fc26/cli.py
```

Fixture: one saved futbin list page (page 1 of 87+) with pinned-value tests
(Dembélé TOTY: 97 OVR, ST + CAM/RW, face 97/94/90/95/60/77, SM/WF 5/5, 178cm,
Explosive, France, "Ligue 1 McDonald's", "Paris SG", price > 0).

## Errors & edge cases

- Price forms: "3.02M" → 3_020_000; "750K" → 750_000; "12,500" → 12500; "0" or
  missing (extinct/SBC cards) → None. Malformed → None, never crash.
- Duplicate ids across pages (same card listed twice, e.g. sort jitter between
  page fetches): upsert dedupes naturally; last write wins.
- Same player+version at two OVRs (e.g. two different TOTW cards, "IF" appearing
  twice): id collision would merge them wrongly. Mitigation: when a page-1..N run
  sees an id twice with a DIFFERENT ovr, suffix the later id with its ovr
  (`mo-salah--if-90`). Documented, tested.
- Women/men name collisions (e.g. two "Alessia Russo"-like same-name players):
  same id-collision policy applies (version+ovr disambiguation).
- League/nation/club strings are futbin-verbatim — the chemistry phase's alias
  table (next spec) normalizes across fcratings/fut.gg/futbin vocabularies.

## CLI surface

```
fc26 expand --min-ovr 87 [--max-pages N]
```

- Progress: one line per page ("page 3/79: 30 cards"), summary at end
  ("expanded: 2356 cards seen, 2201 new, 155 merged, 0 failed pages").
- `--min-ovr` required (no default — the user chooses depth consciously).
- Exit 1 only when zero cards were ingested.

## Non-goals

- Sub-stats / PlayStyles bulk crawl (fut.gg add stays the deep-data path)
- Price history/tracking over time (acquisition-planner phase decides)
- Auto-refresh scheduling
- The chemistry engine (next spec, unchanged design — computes over the larger pool)

## Success criteria

- `fc26 expand --min-ovr 87` ingests ≥2,000 cards in one run with 0 failed pages;
  re-run is clean (no duplicate-id explosions; only price/crawled_at churn).
- Dembélé TOTY pinned test passes offline against the committed fixture.
- Existing 131-card data survives: enriched base cards keep their data (merge
  fills, never wipes), the two fut.gg specials untouched.
- Suite stays ≥80% coverage.
