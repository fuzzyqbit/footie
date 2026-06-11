# ⚽ FC 26 Playbook (PS5)

A practical, opinionated guide to dominating **EA Sports FC 26** on PlayStation 5 —
strategies, formations & lineups, tactics (FC IQ + Player Roles), and player
acquisition plans for both **Ultimate Team (FUT)** and **Career Mode**.

> **Patch note:** EA tunes gameplay throughout the year via Title Updates. Anything
> here about the "meta" (best formations, OP PlayStyles, must-buy players) is a
> snapshot and will drift. The *principles* — spacing, role chemistry, defensive
> shape, value in the market — outlast any single patch. Re-check ratings and
> prices in-game before spending coins.

## How to use this playbook

1. **Lock your settings first.** Controller, camera, and gameplay config matter
   more than any tactic. → [`docs/01-gameplay-settings.md`](docs/01-gameplay-settings.md)
2. **Pick an identity.** Decide *how* you want to play (possession, counter,
   wing-overload, gegenpress) before you pick a formation.
   → [`docs/02-tactics-fc-iq.md`](docs/02-tactics-fc-iq.md)
3. **Choose a formation + lineup** that expresses that identity.
   → [`docs/03-formations-lineups.md`](docs/03-formations-lineups.md)
4. **Assign Player Roles** so every position has a job.
   → [`docs/04-player-roles.md`](docs/04-player-roles.md)
5. **Build the squad.** Hunt PlayStyles+ and chemistry, not just overalls.
   → [`docs/05-player-acquisitions.md`](docs/05-player-acquisitions.md)
6. **Drill the mechanics** that win games at the margins.
   → [`docs/06-skill-and-mechanics.md`](docs/06-skill-and-mechanics.md)
7. **Apply it per mode** (FUT / Career / Clubs / Rush).
   → [`docs/07-game-modes.md`](docs/07-game-modes.md)
8. **Reference the ratings.** FC 26 Top 100 + best-per-position, crawled from
   fcratings.com. → [`docs/08-player-ratings-top100.md`](docs/08-player-ratings-top100.md)
9. **Chase pace.** Fastest players (crawled PAC) + the fast special-card/AcceleRATE
   meta. → [`docs/09-fastest-players-and-pace-meta.md`](docs/09-fastest-players-and-pace-meta.md)
10. **The Fastest XI.** Fastest player per position ranked by PAC, plus a master
    fast-player list. → [`docs/10-fastest-xi.md`](docs/10-fastest-xi.md)
11. **Special cards.** Per-card stats crawled from fut.gg player pages (paste a card
    URL to add). → [`docs/11-special-cards.md`](docs/11-special-cards.md)

## The `fc26` program

The playbook now has a companion CLI: a player-card database seeded from the
crawled docs, with live ingest from fut.gg and fcratings.

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/fc26 seed                          # one-time: docs → data/players.json
.venv/bin/fc26 add <fut.gg card URL>         # add a special card
.venv/bin/fc26 sync                          # refresh fcratings top-100
.venv/bin/fc26 enrich                        # backfill league/nation/face stats
.venv/bin/fc26 expand --min-ovr 87           # bulk-ingest live FUT cards + prices (futbin)
.venv/bin/fc26 search "rodri"
.venv/bin/fc26 list --pos ST --sort pac
.venv/bin/fc26 show kylian-mbappe--base
.venv/bin/fc26 chem squads/sample-rivals.json # chemistry for a lineup file
.venv/bin/fc26 upgrade squads/sample-rivals.json --budget 200K # budgeted swap suggestions
```

Design: [`docs/superpowers/specs/2026-06-10-fc26-player-db-design.md`](docs/superpowers/specs/2026-06-10-fc26-player-db-design.md).
Coming next: full-XI auto-builder, acquisition planner.

## Quick-start TL;DR

- **Most forgiving meta formation:** `4-2-3-1` — defensive solidity from the double
  pivot plus a creative 10. Great for learning FC IQ.
- **Highest skill ceiling:** `4-3-3 (False 9)` or `4-2-2-2` for wing/half-space play.
- **Best "I just want to win" defensive shape:** drop into a `4-4-2` block out of
  possession, regardless of your on-paper formation.
- **Two non-negotiable PlayStyles+ to chase:** an attacker with **Finesse Shot+**
  and a passer with **Incisive Pass+**.
- **Defending priority:** master **secondary-press contain (L2/LT jockey) + manual
  player switching**. Spamming tackle (○/B) loses games at high levels.

See [`docs/`](docs/) for the full breakdown.
