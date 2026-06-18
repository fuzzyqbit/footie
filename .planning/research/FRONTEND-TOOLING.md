# Research: Frontend Load + Tooling/Benchmark (footie perf milestone)

**Domain:** Brownfield performance milestone — Vite 6 / React 19 web bundle + Python CLI startup + benchmark harness
**Researched:** 2026-06-17
**Overall confidence:** HIGH (Vite/Rollup/React/TanStack/pytest-benchmark APIs verified against official docs; tied to exact file:line in this repo)
**Constraint reminder:** ZERO behavior change. Same bundle output semantics, same API responses, same CLI text, all tests green. Every recommendation below preserves observable behavior.

---

## Summary

Two independent workstreams, both pure speedups.

**(A) Frontend.** `web/src/App.tsx:3-13` eagerly imports all 12 page components, so the single ~298 KB bundle contains every page plus the dynamic-import graph of the heaviest page (GeneratorPage, which pulls `@imgly/background-removal` WASM+ML). The fix is route-level `React.lazy` + `Suspense` so each page becomes its own chunk and the WASM dep is excluded from the initial download. Two free wins on top: `html-to-image` (`web/package.json:19`) is a **declared-but-unused dependency** (GeneratorPage exports PNG via native `canvas.toDataURL`, `GeneratorPage.tsx:402` — confirmed no `html-to-image` import anywhere in `src/`) and can be removed; and `main.tsx:8`'s bare `new QueryClient()` (staleTime 0) refetches `/api/meta` + `/api/cards` on every navigation, fixable with a sane `defaultOptions`.

**(B) Tooling.** There is no latency/throughput baseline anywhere in the repo (confirmed: no `pytest-benchmark`, no `cProfile`, no `perf_counter` harness; `pyproject.toml:16` dev extras are only `pytest`/`pytest-cov`). This harness is the **safety net for the entire milestone** — without it you cannot prove the cache/async/code-split changes are faster, nor catch regressions. Recommendation: **pytest-benchmark** for committed micro/macro baselines with CI-style regression gates, **cProfile + snakeviz** for one-shot "where does the time go" call-graph analysis, and **py-spy** for sampling the live async refresh/serve process. Separately, `fc26/cli.py:11-36` eagerly imports the whole package graph (httpx, rich, selectolax, every builder/chem/ingest module) so even `fc26 --help` pays full import cost; defer those imports into the command bodies.

The frontend and tooling tracks are fully independent and can be parallel phases. The benchmark harness should land **first** (or alongside the first backend change) because it is the measurement instrument the rest of the milestone depends on.

---

## A. Frontend: code-splitting + lazy deps

### A1. Route-level code-splitting with React.lazy + Suspense (the main win)

**Problem (verified):** `web/src/App.tsx:3-13` does 11 static page imports + the `<Routes>` block at lines 20-33. Every page — including `GeneratorPage` (24 KB source, `GeneratorPage.tsx`) — is in the entry chunk. The lone existing dynamic import (`GeneratorPage.tsx:272`, `@imgly/background-removal`) does NOT help the initial load today, because GeneratorPage is itself statically imported into the eager App, so Rollup still creates the page's chunk eagerly-reachable. Splitting the page is what makes that inner dynamic import pay off.

**Fix — convert static page imports to `lazy()` at module top level** (React 19 verified pattern, react.dev/reference/react/lazy):

```tsx
// web/src/App.tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import Sidebar from './components/Sidebar'

// Declare lazy components at MODULE TOP LEVEL (never inside the component —
// react.dev warns that lazy() inside a component resets state every render).
const CardsPage      = lazy(() => import('./pages/CardsPage'))
const SquadsPage     = lazy(() => import('./pages/SquadsPage'))
const BuildPage      = lazy(() => import('./pages/BuildPage'))
const UpgradePage    = lazy(() => import('./pages/UpgradePage'))
const UpdatesPage    = lazy(() => import('./pages/UpdatesPage'))
const ValuePage      = lazy(() => import('./pages/ValuePage'))
const WatchlistPage  = lazy(() => import('./pages/WatchlistPage'))
const ComparePage    = lazy(() => import('./pages/ComparePage'))
const ObjectivesPage = lazy(() => import('./pages/ObjectivesPage'))
const SbcsPage       = lazy(() => import('./pages/SbcsPage'))
const GeneratorPage  = lazy(() => import('./pages/GeneratorPage'))

export default function App() {
  return (
    <div className="flex h-screen bg-navy text-fg overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <Suspense fallback={<SkeletonGrid />}>  {/* reuse existing components/SkeletonGrid */}
          <Routes>
            <Route path="/" element={<Navigate to="/cards" replace />} />
            <Route path="/cards" element={<CardsPage />} />
            {/* …unchanged… */}
            <Route path="/create" element={<GeneratorPage />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}
```

**Notes for this repo:**
- Page components must be **default exports** for `lazy(() => import(...))` to work. Verify each `pages/*.tsx` default-exports (App.tsx currently imports them as defaults, so they already do). Confidence: HIGH.
- Wrap `<Routes>` in a single `<Suspense>` (shown) — simplest and matches the declarative `Routes/Route` API this app uses (react-router-dom v7, `package.json:22`). A per-route `<Suspense>` is also valid but unnecessary here. Confidence: HIGH.
- There is already a `components/SkeletonGrid.tsx` and `components/SkeletonPitch.tsx` — reuse one as the fallback so the loading state matches existing UX. Behavior-preserving.
- **Test impact:** vitest page tests (`pages/*.test.tsx`) render pages directly and are unaffected. Playwright e2e (`e2e/app.spec.ts`, 7 specs visiting every page) will now trigger chunk loads; assertions are data-resilient (per QUALITY.md) so they should stay green, but the loading fallback briefly appears — confirm e2e waits on content, not on absence of a spinner. Flag for the implementer.

**Why React.lazy over React Router's `lazy` route property:** this app uses the declarative `<BrowserRouter>` + `<Routes>`/`<Route>` API (`main.tsx:13`, `App.tsx`), not the data-router (`createBrowserRouter`). React Router's route-`lazy` is a data-router feature; `React.lazy` is the correct, minimal-diff tool for the component API already in use. (Verified: react-router v7 lazy-route pattern requires the object/data router.) Confidence: HIGH.

### A2. Lazy-load the WASM dep — already half-done, finish it

**Status:** `@imgly/background-removal` (`package.json:17`) is **already** dynamically imported (`GeneratorPage.tsx:272`: `const { removeBackground } = await import('@imgly/background-removal')`) and the comment at lines 267-270 confirms intent: "the model only downloads when someone actually uploads a photo." This is correct.

**The only missing piece** is A1: because GeneratorPage is eagerly imported into App today, its module graph (including the `import()` call site and `@imgly`'s static sub-deps) is reachable from the entry. Once GeneratorPage is `lazy()`-loaded (A1), the `@imgly` chunk is only fetched when (a) the user navigates to `/create` AND (b) actually uploads a photo. No further code change to GeneratorPage is needed. Confidence: HIGH.

**Do NOT** add `@imgly/background-removal` to `optimizeDeps` or any manualChunks rule that would force it eager — leave it behind the existing `await import()`.

### A3. Remove the dead `html-to-image` dependency (free win)

**Finding (verified):** `grep -rn "html-to-image" src/` → no matches. The PNG export is hand-rolled with `canvas.getContext('2d')` + `canvas.toDataURL('image/png')` (`GeneratorPage.tsx:308-403`). `html-to-image@^1.11.13` (`package.json:19`) is never imported.

**Action:** remove it from `package.json` dependencies. If it's genuinely unimported, tree-shaking likely already excludes it from the bundle, so the runtime win may be ~0 KB — but it removes a supply-chain surface and ~install weight, and prevents accidental future inclusion. **Behavior-preserving** (nothing imports it). Confidence: HIGH that it's unused; MEDIUM that removal changes bundle bytes (depends on whether anything pulled it transitively — verify with a before/after `vite build` size diff).

### A4. `manualChunks` for vendor/stable-cache splitting (verified Vite 6 + Rollup)

**Vite version note (IMPORTANT):** this project pins `vite: ^6.0.0` (`package.json:38`). Vite 6 uses **Rollup** under the hood, so the config key is `build.rollupOptions.output.manualChunks` (Rollup's option). The newest Vite docs now describe a Rolldown-based `build.rolldownOptions.output.codeSplitting` — **that is for Vite 7+/rolldown-vite and does NOT apply at v6.** Stay on `rollupOptions`. Confidence: HIGH (verified: v6.vite.dev/guide/build points to `build.rollupOptions.output.manualChunks` → Rollup docs; rollupjs.org/configuration-options/#output-manualchunks documents both forms).

**Recommended config** (`web/vite.config.ts`, add to the existing `defineConfig`):

```ts
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Keep React + the router on their own stable cache line. These
          // change rarely, so a hashed vendor chunk stays cached across
          // app deploys.
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'query-vendor': ['@tanstack/react-query'],
        },
      },
    },
  },
  test: { /* …unchanged… */ },
})
```

**Why object form, not a function:** the object form (`name -> [modules]`) is simpler and lower-risk here. Rollup's docs warn the function form's per-`id` logic can accidentally co-locate or split modules and **"can change the behaviour of the application if side effects are triggered before the corresponding modules are actually used"** (rollupjs.org). With only 2-3 stable vendor groups, the object form is sufficient and safe. Confidence: HIGH.

**Caveats / do-NOT list:**
- **Do not** route-split via manualChunks — A1's `React.lazy` already gives one chunk per page automatically; adding a function-form `manualChunks` that also touches pages risks double-classification. Let `React.lazy` own page splitting; let `manualChunks` own only `node_modules` vendors.
- **Do not** put `@imgly/background-removal` in any manualChunks group (keep it behind the dynamic import, A2).
- **Do not** use the old `splitVendorChunkPlugin` — deprecated/removed; `manualChunks` is the supported path.
- After changing chunking, run `npm run build` and eyeball the chunk list — you want: a small entry, `react-vendor`/`query-vendor`, one chunk per page, and a separate `@imgly` chunk reachable only from the generator page.

### A5. Avoid over-fetching the full pool (`useAllCards` / `?limit=5000`)

**Finding:** `web/src/api/cards.ts:49-55` `useAllCards()` fetches `/api/cards?limit=5000` (the whole ~2,434-card pool, ~4.4 MB JSON serialized) and is used by `BuildPage.tsx:18`, `SquadsPage.tsx:19`, `GeneratorPage.tsx:198`. It already sets `staleTime: 5 * 60 * 1000` (line 53), so within a 5-min window navigating between those three pages reuses the cache — good. The remaining cost is the first load on each of those pages.

**Recommendations (pick per behavior-equivalence tolerance):**
- **Keep behavior identical, improve caching only:** ensure the global `defaultOptions` (A6) gives this query a `gcTime` long enough that it isn't garbage-collected between visits, and keep its explicit 5-min `staleTime`. Lowest risk, zero behavior change. Confidence: HIGH.
- **Reduce payload (needs care):** GeneratorPage only needs names + a few face stats for the dropdown; BuildPage/SquadsPage need the buildable pool. A trimmed projection (fewer fields) or a smaller `min_ovr` floor would cut bytes — but this **changes what the client receives** and could alter dropdown contents, so it risks behavior change and must be validated against e2e. Treat as a stretch/optional item, not core. Confidence: MEDIUM that a safe projection exists; flag for phase-specific design.
- The backend cache work (CONCERNS.md 3.1/3.3) will make `/api/cards?limit=5000` itself far cheaper server-side, which is the bigger lever — this frontend item is secondary.

### A6. React Query cache tuning (verified TanStack Query v5)

**Problem (verified):** `web/src/main.tsx:8` is a bare `new QueryClient()`. TanStack Query v5 defaults (tanstack.com/query/v5 important-defaults): `staleTime: 0` (every query is immediately stale), `gcTime: 5 min`, and `refetchOnMount` / `refetchOnWindowFocus` / `refetchOnReconnect` all effectively `true` (refetch when stale). Net effect for this app: navigating between pages and re-focusing the tab re-fires `/api/meta` (static between refreshes) and `/api/cards` queries. CONCERNS.md 2.3 flags this exactly, and notes the per-query 5-min override on `useAllCards` makes caching inconsistent.

**Fix — set sensible global defaults, then drop the now-redundant per-query override:**

```tsx
// web/src/main.tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,   // 5 min: data is "fresh"; no refetch on nav within window
      gcTime: 30 * 60 * 1000,     // 30 min: keep inactive caches around between visits
      refetchOnWindowFocus: false, // this is a local single-user tool; tab-focus refetch is noise
      retry: 1,                    // local API; long retry chains just delay error surfacing
    },
  },
})
```

**Rationale:**
- `staleTime: 5min` matches the existing intent in `useAllCards` and the reality that `/api/meta` and the card pool only change on the server's scheduled auto-refresh (default interval is hours — `serve --refresh-interval-hours`, `cli.py:703`). So 5 min is conservative and safe.
- With a global 5-min `staleTime`, the explicit `staleTime: 5 * 60 * 1000` in `cards.ts:53` becomes redundant — remove it for consistency (CONCERNS.md 2.3's "inconsistent caching" point), or leave it; either is correct.
- `refetchOnWindowFocus: false` is the single biggest UX/network win for a local single-user app and is the community-standard tuning. Confidence: HIGH.

**Behavior-equivalence note:** this changes *when* the client refetches, not *what* the API returns. Data is identical; it's just fetched less often. For a perf milestone with a "no behavior change" rule, "fewer redundant refetches" is the intended kind of change. But confirm no test asserts a specific refetch-on-focus behavior (unlikely — MSW mocks responses, doesn't assert call counts on focus). Flag for the implementer. Confidence: HIGH.

---

## B. Python benchmark + profiling harness (THE SAFETY NET)

This is the load-bearing deliverable: it's how the milestone proves the cache/async/split changes are faster and guards every later phase against regressions. Land it early.

### B1. Tool choice (verified)

| Tool | Role in this milestone | Why | Confidence |
|------|------------------------|-----|------------|
| **pytest-benchmark** | Committed baselines + regression gate | Integrates with the existing pytest suite, auto-calibrates iterations, saves JSON baselines, and **fails on regression** via `--benchmark-compare-fail` (e.g. `mean:10%`). This is the durable safety net. | HIGH |
| **cProfile** (+ snakeviz/gprof2dot for viz) | One-shot "where does the time go" call-graph | Stdlib, deterministic, function-level totals — perfect for confirming the JSON re-parse / chem-recompute hot paths before/after a change. Per-call overhead makes it bad for *timing*, great for *attribution*. | HIGH |
| **py-spy** | Sample the live `fc26 serve` / refresh process | Sampling profiler, **attaches to a running PID without code changes or restart**, low overhead, flame graphs. Ideal for the async scraper and the running API where you can't easily wrap a function. | HIGH |

**Decision:** adopt **pytest-benchmark as the primary harness** (committed, automated, regression-guarding), use **cProfile** ad-hoc during optimization to find hot lines, and keep **py-spy** in the toolbox for the live async refresh path. `timeit` is too low-level/manual for a multi-target harness — skip it. (Verified comparison: pythonspeed.com "beyond cProfile", pytest-benchmark.readthedocs.io usage.) Confidence: HIGH.

PEP 690 / PEP 810 "lazy imports" are **not** available here — the project targets Python 3.12 (`pyproject.toml:5`), PEP 810 lands in 3.15. The CLI fix (B4) is manual deferred imports, not a language feature.

### B2. Where it lives + how to wire it

- Add dev deps to `pyproject.toml:16`:
  ```toml
  dev = ["pytest>=8", "pytest-cov>=5", "pytest-benchmark>=4", "py-spy"]
  ```
  (snakeviz optional, dev-only.)
- New test dir/module, e.g. `tests/benchmarks/` or `tests/test_perf_bench.py`, with benchmark tests marked so the default `pytest` run can skip them and the suite stays fast (mirror the existing `live` marker pattern in `pyproject.toml:29` / `conftest.py`):
  ```toml
  markers = [
    "live: hits the real network (opt-in via --run-live)",
    "benchmark: perf baseline timing (opt-in via --run-bench)",
  ]
  ```
  Gate them in `conftest.py` the same way live tests are gated (`tests/conftest.py:4-19`), so `pytest` stays offline+fast and `pytest -m benchmark` (or `--run-bench`) runs baselines.
- Use a **fixed, committed corpus** so timings are comparable run-to-run: the real `data/players.json` (~2,434 cards) is the natural fixture for read/parse benchmarks; for upsert/refresh, build a `tmp_path` DB seeded from it (matches the existing integration-test style: `CardRepository(tmp_path/"players.json")`, QUALITY.md).

### B3. What to measure (first baselines — tie to CONCERNS.md hot paths)

These are the proof points for the milestone. Each maps to a CONCERNS.md bottleneck so "faster" is measurable:

| Benchmark | Target code | Guards (CONCERNS.md) |
|-----------|-------------|----------------------|
| `CardRepository.find_all()` full load+parse of real DB | `fc26/db.py:48-66` | 1.x / 3.1 — root-cause re-parse; in-memory cache must beat this |
| `CardRepository.upsert()` single card into a populated DB | `db.py:85` (find_all + full re-serialize) | 1.1 — O(n²) rewrite; batch/atomic write must beat this |
| Full `refresh_data` with **mocked HTTP + stubbed sleep** (offline) | `fc26/ingest/refresh.py` | 1.1/1.2/1.5 — proves async + batch-write win *without* network variance |
| `compute_chemistry(lineup, slot_cards)` single call | `fc26/chem/engine.py:87-160` | 3.5/3.6 — memoization/canonical caching must beat this |
| `find_upgrades(...)` one `/api/upgrade`-shaped call | `fc26/builder/upgrade.py:87-169` | 3.5 — hundreds of thousands of chem recomputes |
| `build_squad(...)` one `/api/build`-shaped call | `fc26/builder/build.py` | 3.5 |
| `/api/cards?limit=5000` via `TestClient` (filter + serialize path) | `fc26/api/app.py` cards handler | 3.1/3.2 — cache + off-event-loop win |
| `/api/meta` via `TestClient` | `app.py:327-342` | 3.3 — static-dropdown recompute; memoize/cache win |

**Critical discipline:** capture baselines **before** any optimization lands (`pytest -m benchmark --benchmark-autosave`), commit the JSON, then after each optimization run `--benchmark-compare=<baseline> --benchmark-compare-fail=mean:5%` (or looser) so a regression fails the run. Verified flags (pytest-benchmark.readthedocs.io/usage): `--benchmark-save NAME`, `--benchmark-autosave`, `--benchmark-compare`, `--benchmark-compare-fail mean:10%` / `min:5%`. Confidence: HIGH.

**Behavior-equivalence guard:** the existing ~346 pytest tests + vitest + e2e remain the *correctness* gate (must stay green); pytest-benchmark is the *speed* gate. Both run; neither is sacrificed. Where feasible, assert the benchmarked function's return value equals the pre-optimization value inside the benchmark test (pytest-benchmark returns the function result) so a benchmark also pins output.

### B4. CLI fast-start via deferred imports

**Problem (verified):** `fc26/cli.py:11-36` imports — at module load — `httpx`, `typer`, `rich.console`, `rich.table`, and **every** builder/chem/ingest/db module (`advise`, `boost`, `build`, `market`, `plan`, `upgrade`, `chem.engine`, `chem.lineup`, `db`, `ingest.enrich/expand/fcratings/futgg/images/objectives/refresh/sbc/seed/web`, `models`). These transitively pull `selectolax` (HTML parser) etc. So `fc26 --help` or `fc26 search foo` loads the entire scraping+builder graph it never uses (CONCERNS.md 4.1). `Console(width=200)` also constructs at import (`cli.py:39`, CONCERNS.md 4.2).

**Fix — move heavy imports into the command bodies that use them (deferred/lazy imports):**

```python
# fc26/cli.py — keep only what every invocation needs at module top:
import typer
app = typer.Typer(help="FC 26 (PS5) FUT player database", no_args_is_help=True)

@app.command()
def search(text: str, db: Path = DB_OPTION, json: bool = JSON_FLAG) -> None:
    """Find cards by name, club, or version (case-insensitive)."""
    from .db import CardRepository          # deferred: only when `search` runs
    from .errors import FC26Error
    ...
```

- Defer the expensive/rarely-used imports into the few commands that need them: ingest modules into `add/sync/enrich/expand/images/refresh/refresh-objectives/refresh-sbcs`; builder/chem into `build/upgrade/plan/chem/advise/boost`; `httpx` into the scraper commands; `uvicorn`/`create_app` are *already* deferred inside `serve` (`cli.py:715-716`) — good, follow that exact pattern everywhere.
- Make `console` lazy too: replace the module-level `Console(width=200)` (`cli.py:39`) with a small accessor (e.g. a `_console()` that constructs on first use, or a module-level lazy singleton) so `--help` doesn't build rich machinery. Lower priority than the package-graph imports.
- Keep `DB_OPTION`/`JSON_FLAG`/`DEFAULT_DB` and `Path`/`typer` at top level (typer needs option defaults at decoration time).

**Behavior-equivalence:** deferred imports change *when* a module loads, not *what* the command does — identical output, identical errors (same `FC26Error` handling). The only observable change is faster `--help`/simple-command startup. Verified approach: standard typer/click lazy-import idiom (function-body imports); 50-80% startup reductions reported (hugovk.dev, byteiota). Confidence: HIGH for correctness; MEDIUM on the exact speedup magnitude for this graph (measure it — add a benchmark/`python -X importtime -m fc26.cli --help` before/after).

**Measure the CLI win:** `python -X importtime -m fc26 --help 2>&1 | sort -k2 -rn | head` before/after shows which imports dominate and confirms the deferral worked. (Optional: a pytest-benchmark test that imports `fc26.cli` in a subprocess and times `--help`.)

---

## Confidence levels

| Claim | Confidence | Source |
|-------|------------|--------|
| `App.tsx` eagerly imports all 12 pages; no React.lazy/Suspense | HIGH | Read `web/src/App.tsx:3-13,20-33` |
| `@imgly/background-removal` already dynamically imported at `GeneratorPage.tsx:272` | HIGH | Read + grep (only `import()` in src) |
| `html-to-image` is declared but unused in `src/` (export uses native canvas) | HIGH | grep `src/` (no matches) + `GeneratorPage.tsx:402` |
| React 19 `lazy`+`Suspense` top-level pattern; never declare lazy inside a component | HIGH | react.dev/reference/react/lazy |
| Vite 6 uses `build.rollupOptions.output.manualChunks` (NOT rolldownOptions) | HIGH | v6.vite.dev/guide/build + rollupjs.org |
| Object-form manualChunks safer than function form; side-effect-order caveat | HIGH | rollupjs.org/configuration-options/#output-manualchunks |
| TanStack Query v5 defaults: staleTime 0, gcTime 5min, refetch-on-mount/focus on | HIGH | tanstack.com/query/v5 important-defaults |
| `main.tsx:8` bare QueryClient causes refetch-on-nav; defaultOptions fix | HIGH | Read `main.tsx:8` + CONCERNS.md 2.3 |
| `useAllCards` fetches `?limit=5000`, 5-min staleTime, used by 3 pages | HIGH | Read `cards.ts:49-55` + grep |
| No benchmark/profiling harness exists | HIGH | QUALITY.md:38-42 + `pyproject.toml:16` |
| pytest-benchmark save/compare/compare-fail flags | HIGH | pytest-benchmark.readthedocs.io/usage |
| cProfile=attribution, py-spy=live sampling, pytest-benchmark=regression gate | HIGH | pythonspeed.com, infoworld, oneuptime |
| `cli.py:11-36` eagerly imports whole package graph; `serve` already defers uvicorn | HIGH | Read `cli.py:11-36,715-716` |
| Deferred function-body imports cut CLI startup (PEP 810 N/A on py3.12) | HIGH (approach) / MEDIUM (magnitude) | hugovk.dev, byteiota; pyproject.toml:5 |
| Exact bundle-byte savings from each change | MEDIUM | requires before/after `vite build` measurement |
| Safe trimmed-payload projection for `useAllCards` without behavior change | MEDIUM | needs phase-specific design + e2e validation |

### Open questions / flag for phase design
- **e2e fallback timing:** confirm Playwright specs wait on page content (not on spinner absence) after route-splitting introduces a Suspense fallback. Low risk, but verify.
- **`useAllCards` payload reduction** is the one frontend item that could touch behavior — keep it optional/stretch and gate on e2e; the backend cache work is the bigger lever for that endpoint.
- **Benchmark thresholds:** start with a loose `--benchmark-compare-fail=mean:10%` to avoid flaky CI on a dev laptop; tighten once baselines are stable. Run benchmarks on a quiet machine / pin iterations.

## Sources
- [react.dev — lazy](https://react.dev/reference/react/lazy)
- [Vite 6 — Building for Production](https://v6.vite.dev/guide/build)
- [Rollup — output.manualChunks](https://rollupjs.org/configuration-options/#output-manualchunks)
- [Lazy-Loading Routes with Vite and React Router v7](https://schof.co/lazy-loading-routes-with-vite-and-react-router-v7/)
- [TanStack Query v5 — Important Defaults](https://tanstack.com/query/v5/docs/framework/react/guides/important-defaults)
- [pytest-benchmark — Usage](https://pytest-benchmark.readthedocs.io/en/latest/usage.html)
- [Beyond cProfile — choosing the right tool (pythonspeed)](https://pythonspeed.com/articles/beyond-cprofile/)
- [Profile Python with cProfile and py-spy (oneuptime)](https://oneuptime.com/blog/post/2025-01-06-profile-python-cprofile-pyspy/view)
- [9 fine libraries for profiling Python (InfoWorld)](https://www.infoworld.com/article/2261513/9-fine-libraries-for-profiling-python-code.html)
- [Three times faster with lazy imports (hugovk)](https://hugovk.dev/blog/2025/lazy-imports/)
- [Python Lazy Imports / PEP 810 (byteiota)](https://byteiota.com/python-lazy-imports-speed-up-startup-with-pep-810/)
