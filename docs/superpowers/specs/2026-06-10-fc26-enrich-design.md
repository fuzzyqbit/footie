# FC 26 Card Enrichment (`fc26 enrich`) — Design Spec (Phase 2)

**Date:** 2026-06-10
**Status:** Approved by user
**Project:** footie — FC 26 Playbook (PS5)
**Depends on:** Phase 1 (`docs/superpowers/specs/2026-06-10-fc26-player-db-design.md`)

## Context

Phase 1 seeded `data/players.json` with 131 cards, but the seed sources carried no
league or nation (0/131) and full face stats for only 37 cards. The chemistry
engine (phase 3) needs club + league + nation for every fielded player, and the
squad builder (phase 4) wants face stats everywhere.

The user chose **bulk crawl enrichment** (option B) over lazy fut.gg adds or
static maps.

Feasibility was verified live during brainstorming:

- The fcratings **top-100 list rows** already contain each player's nation
  (flag `title`) and a per-player page URL (e.g.
  `https://www.fcratings.com/kylian-mbappe-231747`) — the phase-1 parser simply
  ignores them.
- **Player pages** are server-rendered and carry league, nation, club, and full
  face stats (verified on the Mbappé page).
- **Club pages** (e.g. `clubs/borussia-dortmund-22`) are server-rendered, list
  full squads with player-page links (Adeyemi confirmed) and the club's league.
- **`lists/all-clubs`** provides a club-name → club-URL map.
- The site's WordPress search does NOT return player links (dead end, confirmed).

## Scope

One new CLI command, `fc26 enrich`, bulk-enriching all non-fut.gg cards with
**league, nation, club, and the six face stats** (plus skill moves / weak foot
where cleanly present) from fcratings player pages.

### Flow

1. Fetch the top-100 list page. Harvest per-row player-page URL + nation →
   URL map covering 100 players.
2. For DB cards not covered by step 1 (~31 pace-list extras): fetch
   `lists/all-clubs` once → club-name → URL map; fetch the card's club page;
   find the player's link by slug match. (~25 club pages.)
3. Fetch each player page (~131 total) → parse league/nation/club/face/SM/WF.
4. Upsert through the existing merge rules. Cards whose `source_url` is fut.gg
   are skipped before any fetch (already rich; merge would protect them anyway).

### Behavior

- **Politeness:** 1 request/second between fetches (sleep injectable so tests
  never really sleep), existing User-Agent.
- **Idempotent + resumable:** cards already enriched (league AND nation AND all
  six face stats present) are skipped on re-run; `--refresh` forces re-fetch.
  Each card is upserted as fetched, so an interrupted run loses nothing.
- **Run time:** ≈ 3–4 minutes for a full first run.

## New files

```
fc26/ingest/fcratings_player.py   # player-page parser
fc26/ingest/enrich.py             # discovery + orchestration
# plus: extend fc26/ingest/fcratings.py (row extras) and fc26/cli.py (command)
```

No schema change — the Card model already carries every target field.

## Parsers & fixtures

Three parse surfaces, each tested against a saved-HTML fixture (offline,
deterministic — same pattern as phase 1):

1. **Top-100 row extras** — extend the existing module with
   `extract_player_urls(html) -> dict[name, url]` and capture nation per row.
   The existing `parse_top100_page` Card contract keeps its shape (now with
   nation filled). The existing fixture already contains the needed markup.
2. **`parse_player_page(html, source_url) -> Card`** — pinned-value test
   against a fetched Mbappé fixture (OVR 91, ST, PAC 96, France,
   league-as-displayed, Real Madrid CF). **League names are stored verbatim as
   fcratings displays them** — the chemistry engine matches on equality, so
   verbatim-consistent beats pretty. Required fields: name, ovr, position,
   league, nation, club, all six face stats; missing required → `ParseError`
   naming the field and URL. SM/WF optional.
3. **Discovery** — `parse_all_clubs(html) -> dict[club_name, url]` and
   `find_player_link(club_html, player_name) -> url | None` (slug-prefix match
   via the existing `slugify`). Club-page fixture: Dortmund (pins the Adeyemi
   link and the league).

Merge nuance: enriched cards are built as `version="base"` with the same id, so
the repository upsert merges them; incoming fcratings data is primary and fills
league/nation/face on the seeded cards.

## Errors & edge cases

- **Slug-match collisions** (two squad players matching the card name): take an
  exact full-slug-prefix match; if still ambiguous, skip + warn — never guess.
- **Transferred players** (card club ≠ current fcratings club page): player link
  not found → miss, warned, not fatal. `fc26 add <fut.gg URL>` remains the
  manual fallback.
- **OVR drift:** player pages show current (post-title-update) ratings; the
  merge lets incoming values win, so the DB drifts toward live ratings. This is
  intended: fcratings is the live truth for base cards.
- **Per-fetch failures:** timeout/HTTP error after 1 retry → skip card, record
  in the miss list, continue the batch.
- **Parse failures:** ParseError on one page → same skip+warn path. If more
  than 50% of the first 10 attempted pages fail, abort the whole run with a
  clear "fcratings layout changed?" error rather than hammering a broken site.
- **Validation:** every enriched card passes `validate_card` at upsert; a
  failure is skip+warn. Atomic writes (phase 1) keep the DB uncorrupted.
- **Exit code:** 0 with warnings when ≥1 card was enriched; 1 when zero.

## CLI surface

```
fc26 enrich                  # bulk: fill league/nation/face for all non-fut.gg cards
fc26 enrich --refresh        # re-fetch even already-enriched cards
fc26 enrich --limit 5        # cap fetches (testing / partial runs)
```

Output: one progress line per player
(`enriched kylian-mbappe--base (France, La Liga)`), then a summary
(`enriched N, skipped S, missed M`) with the misses named.

## Non-goals (later specs)

- The chemistry engine itself (next spec — consumes this data)
- Sub-stats / PlayStyles from fcratings player pages (fut.gg stays the rich
  source; YAGNI until the squad builder needs them)
- Price data, special-card discovery, scheduled auto-sync

## Success criteria

- After `fc26 enrich`: ≥120/131 cards have league + nation + all six face
  stats; misses are individually named in the output.
- Test suite stays ≥80% coverage; all parsers tested offline via fixtures.
- Re-run is fast (skips enriched cards) and byte-stable on an unchanged site.
