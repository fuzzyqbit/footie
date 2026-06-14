# FC 26 Frontend (`web/`) — Design Spec (Phase 8B)

**Date:** 2026-06-13
**Status:** Approved by user
**Depends on:** Phase 8A (FastAPI server, `fc26 serve` on port 8026)

## Decisions (user-approved)

- Layout: persistent sidebar nav (Cards / Squads / Build / Upgrade)
- Cards page: compact card grid tiles
- Squads/pitch view: vertical pitch (attack top, GK bottom) + side panel
- Slot click: searchable dropdown to swap player; `POST /api/chem` fires on swap; side panel updates live
- Build page: form → editable pitch result → save squad
- Stack: Vite + React 19 + TypeScript + Tailwind CSS v4 + TanStack Query v5 + React Router v7
- State: local `useState` per page; React Query for all server state; no global store
- `fc26 serve` static serving of `web/dist`: deferred to a later phase

## Architecture

```
web/
  src/
    api/            # typed fetch wrappers + React Query hooks
      client.ts     # base fetcher (envelope unwrap, error throw)
      cards.ts      # useCards, useCard
      squads.ts     # useSquads, useSquad, useSaveSquad
      chem.ts       # useChem (mutation)
      build.ts      # useBuild (mutation)
      upgrade.ts    # useUpgrade (mutation)
      meta.ts       # useMeta
    components/
      Sidebar.tsx
      Pitch.tsx
      SlotCard.tsx
      SidePanel.tsx
      PlayerDropdown.tsx
      CardTile.tsx
      SearchFilterBar.tsx
      SkeletonGrid.tsx
      SkeletonPitch.tsx
    pages/
      CardsPage.tsx
      SquadsPage.tsx
      BuildPage.tsx
      UpgradePage.tsx
    App.tsx           # Router shell + Sidebar layout
    main.tsx
  index.html
  vite.config.ts
  tailwind.config.ts
  tsconfig.json
  package.json
```

API base URL: `http://localhost:8026`. All responses follow `{ ok, data, error }` envelope — `client.ts` unwraps `data` or throws on `ok: false`.

## Tailwind Palette

Custom dark football aesthetic:

| Token | Value | Usage |
|---|---|---|
| `pitch` | `#1a3a1a` | Pitch background |
| `navy` | `#0f0f1a` | App background |
| `card` | `#16213e` | Card/tile background |
| `gold` | `#e2b714` | OVR badges, active accents |
| `chem-green` | `#4caf50` | Prices, chem indicators |
| `muted` | `#aaaaaa` | Secondary text |

## Pages

### Cards (`/cards`)

- `SearchFilterBar`: text search + position select + league select + min OVR number input + sort select. All dropdown options populated from `GET /api/meta`.
- `CardTile` grid: 50 cards per page, pagination controls below.
- Click a tile → inline expansion showing all 6 face stats (PAC/SHO/PAS/DRI/DEF/PHY).
- Data: `useCards(params)` → `GET /api/cards` with query params. Re-fetches on any filter change.

### Squads (`/squads`)

- Left column: list of saved squads from `useSquads()` → `GET /api/squads`. Click one to load.
- Right: `Pitch` + `SidePanel`.
- Click slot on pitch → `PlayerDropdown` opens → select player → `useChem` mutation fires with updated squad body → side panel refreshes.
- "Save" button → `useSaveSquad` mutation → `PUT /api/squads/{name}`.
- Squad state (`currentSquad`) lives in `SquadsPage` local state.

### Build (`/build`)

- Form: formation dropdown (options from `useMeta`), budget text input (e.g. `500K`), optional league filter select.
- "Build" button → `useBuild` mutation → `POST /api/build` → result squad loaded into editable `Pitch`.
- Same slot-swap flow as Squads: click slot → dropdown → chem recalc.
- "Save squad" → name input + `useSaveSquad` → `PUT /api/squads/{name}`.
- Built squad state lives in `BuildPage` local state.

### Upgrade (`/upgrade`)

- Squad selector dropdown (from squad list) + budget text input.
- "Find upgrades" → `useUpgrade` mutation → `POST /api/upgrade`.
- Result: list of suggested swaps — slot, old player → new player, cost, chem delta.
- "Accept" button per swap builds a modified squad in local state.
- "Save modified squad" → `useSaveSquad`.

## Components

### `Pitch`

```tsx
<Pitch
  formation="4-2-3-1"
  slots={{ GK: card, RB: card, ... }}
  chemReport={ChemReport | null}
  selectedSlot={string | null}
  onSlotClick={(slot: string) => void}
/>
```

Renders rows of `SlotCard`s using formation slot order from `GET /api/meta`. Stateless — parent owns `slots` and `selectedSlot`.

### `SlotCard`

- Displays: OVR (gold), player name, position label, chem dots (●●● coloured by 0/1/2/3).
- Highlighted border when `selected`.
- Cursor pointer; calls `onSlotClick` on click.

### `SidePanel`

- Shown when a slot is selected.
- Displays: player name, position, OVR, club / nation / league, price, 6 face stats, per-player chem (n/3), team total chem (n/33).
- Clears when no slot selected ("Click a player to see details").

### `PlayerDropdown`

- Triggered when a slot is clicked on the pitch.
- Searchable `<input>` filtering the full card pool (passed as prop — already fetched by page).
- Filtered list shows OVR, name, position, price.
- Selecting fires `onSwap(slot, newCardId)` → parent updates squad state → re-fires `POST /api/chem`.
- Escape or click-away closes without change.
- On swap failure (`POST /api/chem` error): reverts slot to previous card, shows error in `SidePanel`.

### `CardTile`

- Compact: gold OVR badge top-left, player name, position, price.
- Expanded state (click toggle): adds 6 stat bars below.

### `SearchFilterBar`

- Inputs: text search, position `<select>`, league `<select>`, min OVR `<input type="number">`, sort `<select>`.
- All select options from `useMeta()`.
- Debounces text search 300ms; other filters apply immediately.

### `Sidebar`

- Fixed left, full height.
- Logo / title at top.
- Nav links: Cards, Squads, Build, Upgrade.
- Active link: gold left border + lighter background.

### Skeletons

- `SkeletonGrid`: placeholder tiles matching `CardTile` dimensions. Shown while `useCards` loading.
- `SkeletonPitch`: placeholder slot shapes on pitch background. Shown while squad loads.

## Error Handling

| Scenario | Behaviour |
|---|---|
| API error on any query | Inline error message below the triggering element |
| `POST /api/chem` fails after swap | Revert slot to previous card; show error in SidePanel |
| Empty card results | "No cards found" zero-state in grid area |
| No squads saved | "No squads yet" zero-state in squad list |
| Budget parse error from API | Inline error below budget input |

No global toast / notification system — all errors are local to the component that triggered them.

## Testing

Stack: **Vitest + React Testing Library + MSW** (Mock Service Worker for API mocks).

| Test | Coverage |
|---|---|
| `Pitch` unit | Correct slot count and row structure per formation |
| `PlayerDropdown` unit | Filters list by search term; fires `onSwap` on selection |
| `SearchFilterBar` unit | Emits correct query params on filter change |
| `CardsPage` integration | Happy path (grid renders); error state (API error shown inline) |
| `SquadsPage` integration | Squad loads on click; swap triggers chem call; save calls PUT |
| `BuildPage` integration | Form submit calls build; result renders on pitch; save calls PUT |
| `UpgradePage` integration | Upgrade call fires; swap list renders |

All API calls mocked via MSW handlers. Coverage target: ≥80%.

## Non-goals (later phases)

- Drag-drop slot editing
- `fc26 serve` static serving of `web/dist`
- Authentication, HTTPS, multi-user
- Chem style (boost) picker in the UI
- Live price refresh in the UI
- Mobile layout

## Success criteria

- `npm run dev` in `web/` serves on `:5173` against `fc26 serve` on `:8026`.
- Cards page loads and filters the 2,400+ card pool.
- Squads page: load `sample-rivals.json` → pitch shows 11 slots → click slot → dropdown → swap → team chem updates in side panel.
- Build page: form → pitch result → save squad file.
- All tests green, coverage ≥80%.
