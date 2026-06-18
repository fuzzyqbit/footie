# Phase 1: Benchmark & Equivalence Harness - Research

**Researched:** 2026-06-18
**Domain:** Python performance benchmarking (pytest-benchmark) + golden-output/equivalence testing + profiling entrypoints (cProfile / py-spy), brownfield, over a single-process FastAPI + Typer + JSON-file app
**Confidence:** HIGH

## Summary

Phase 1 builds the measurement instrument and the golden-output safety net that gate every later optimization phase. It is purely additive: no `fc26/` runtime code changes, no behavior change, no on-disk format change. Two deliverables: (1) a **pytest-benchmark** suite that captures committed wall-clock baselines for the hot paths (refresh, `/api/cards|build|upgrade|meta`, db read/write) behind a new `benchmark` marker that mirrors the existing `live` marker so the default `pytest` run stays fast and offline; (2) a **golden-output/equivalence** check that captures today's outputs (refresh-produced `players.json` bytes + result tuples + progress sequence; a build/upgrade matrix over formations × objectives × budgets; key API JSON; CLI text) and re-asserts structural/byte equality after any optimization. Profiling entrypoints (cProfile wrapper + documented py-spy usage) round out BENCH-04.

The repo is unusually well-shaped for this work. Side effects are **injected, not patched** (`fetch_html`/`sleep`/`on_progress` are parameters), so an offline, deterministic refresh is already how the existing tests run (`tests/test_refresh.py:22-25`, `tests/test_expand.py:48`). HTML fixtures already exist in `tests/fixtures/`. `CardRepository(tmp_path/"players.json")` is the established integration-test idiom (`tests/test_db.py:34`). A real-DB live fixture pattern (`_REAL_DB`, gated by `@pytest.mark.live`) already exists (`tests/test_api.py:540-550`). The harness should reuse every one of these patterns rather than invent new ones.

The single most important design constraint, surfaced across all four research files: **the golden fixtures must be decoupled from the live `data/players.json`**, which changes on every `fc26 refresh`. Equivalence checks assert "output is unchanged across an optimization," not "output matches the current scrape." A small, committed, deterministic card corpus (a frozen sample carved from the real DB, ~30-60 cards) is the right fixture for golden + most benchmarks; the real 4.4 MB / 2,434-card DB is the right fixture only for the read/parse benchmarks where realistic size is the point — and those should be gated/skipped when the file is absent (mirroring `_REAL_DB`).

**Primary recommendation:** Add `pytest-benchmark>=5` and `py-spy` to `pyproject.toml [dev]`; register a `benchmark` marker and a `--run-bench` option in `conftest.py` mirroring `live`/`--run-live`; put all new code under `tests/benchmarks/` (benchmark tests, golden capture/assert helpers, a committed `golden/` fixtures dir, a committed `.benchmarks/` baseline store, and a `README.md` documenting cProfile/py-spy entrypoints). Capture baselines + golden on `ro` HEAD first, commit them, then gate every later phase with `--benchmark-compare-fail=mean:10%` and the golden assertions.

## User Constraints

> No CONTEXT.md exists for this phase (no `/gsd:discuss-phase` was run). Constraints below are extracted from PROJECT.md, REQUIREMENTS.md, ROADMAP.md success criteria, and the orchestrator's task brief, and carry the same authority.

### Locked Decisions (from PROJECT.md / REQUIREMENTS.md / task brief)
- **Zero behavior change.** Outputs byte-identical: same `data/players.json` format, same API responses, same CLI text. The harness adds measurement only. [CITED: PROJECT.md:52, REQUIREMENTS.md:55-59]
- **All existing tests stay green** — pytest offline, vitest, Playwright e2e — unedited where they encode the behavior contract. [CITED: REQUIREMENTS.md:55]
- **Default `pytest` run must stay fast and offline.** Slow benchmarks gated behind a marker, mirroring the existing `live` marker in `conftest.py`. [CITED: task brief CONSTRAINTS; conftest.py:13-19]
- **No new infrastructure** — no Redis/Memcached/RabbitMQ. New *dev* dependencies (`pytest-benchmark`, `py-spy`) are fine; add to `pyproject.toml [dev]` / optional extras. [CITED: PROJECT.md:55, task brief]
- **No on-disk format change.** Keep dad's JSON format. [CITED: PROJECT.md:53]
- **Golden capture must be deterministic:** refresh uses injected `fetch_html` (mocked HTTP) + stubbed `sleep` (offline + reproducible); build/upgrade golden = a matrix over formations × objectives × budgets; API golden via `TestClient`; CLI golden via captured stdout. [CITED: task brief CONSTRAINTS]
- **Branching:** `main` is dad's authoritative branch; all work lands on `ro`. (Per repo MEMORY.md, merging to `main` is now permitted via commit → push `ro` → merge `main`, but that is a separate, explicitly-instructed action — Phase 1 work commits to `ro`/feature branch.) [CITED: ./CLAUDE.md; MEMORY.md]

### Claude's Discretion
- Exact directory layout under `tests/` (recommended: `tests/benchmarks/`).
- The opt-in mechanism: a `--run-bench` flag and/or `-m benchmark` selection (recommended: both, mirroring `live`).
- The size/composition of the committed deterministic corpus, and whether golden uses a frozen corpus vs. the real DB per benchmark.
- The exact regression threshold to start with (recommended: `mean:10%`, loosen/tighten after baselines stabilize).
- Whether to add `pytest-codspeed` or stay with `pytest-benchmark` (recommended: `pytest-benchmark` — committed local baselines, no SaaS, no CI required).

### Deferred Ideas (OUT OF SCOPE for Phase 1)
- Any actual optimization (cache, batched writes, async, code-split, lazy imports) — those are Phases 2-5. Phase 1 only measures and pins.
- CI wiring (`.github/workflows` is absent; no CI exists per QUALITY.md:33). Phase 1 produces a *locally runnable* gate; automating it in CI is not required and not in scope.
- Frontend bundle-size benchmarking (Phase 5 concern; uses `vite build` size diff, not pytest-benchmark).
- The gated algorithmic-chemistry equivalence sweep / `hypothesis` property tests — those belong to the deferred v2 CHEM work, not Phase 1's structural golden check.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BENCH-01 | Reusable benchmark harness measures refresh, `/api/cards`, `/api/build`, `/api/upgrade`, `/api/meta`, and db read/write, with committed baselines | pytest-benchmark 5.2.3 verified (Python 3.14 supported); `benchmark` fixture + `--benchmark-autosave`/`--benchmark-storage` for committed baselines (§Standard Stack, §Code Examples); target functions + call shapes identified at file:line (§Benchmark Target Map) |
| BENCH-02 | Regression gate flags when a benchmarked path slows past threshold (e.g. mean +10%) | `--benchmark-compare` + `--benchmark-compare-fail mean:10%` verified syntax (§Code Examples); start loose to absorb laptop variance (§Common Pitfalls) |
| BENCH-03 | Golden-output/equivalence check captures current outputs and asserts unchanged after each optimization | Concrete capture+assert design for refresh bytes/tuples/progress, build/upgrade matrix via `asdict`, API JSON via `TestClient`, CLI text via captured stdout (§Architecture Patterns, §Golden Capture Design); determinism via injected `fetch_html`/`sleep` + id-sort already in `_save` (db.py:99) |
| BENCH-04 | Profiling entrypoints (cProfile / py-spy) documented for refresh + build/upgrade hot paths | cProfile stdlib wrapper script + py-spy 0.4.2 usage (macOS needs sudo; Homebrew python avoids SIP); docs land in `tests/benchmarks/README.md` (§Profiling Entrypoints) |

## Architectural Responsibility Map

The harness is a **test-tier** instrument that observes the existing tiers without changing them.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Benchmark timing of db read/write | Test (pytest-benchmark) | Data layer (`fc26/db.py`) | The `benchmark` fixture wraps `CardRepository` calls; no db.py change. |
| Benchmark timing of API endpoints | Test (pytest-benchmark + Starlette `TestClient`) | API (`fc26/api/app.py`) | `TestClient` exercises the real handler stack in-process; no app.py change. |
| Benchmark timing of refresh | Test (pytest-benchmark) | Ingest (`fc26/ingest/refresh.py`) | Injected `fetch_html`/`sleep` make it offline+deterministic; no refresh.py change. |
| Benchmark timing of build/upgrade | Test (pytest-benchmark) | Builder (`fc26/builder/*`) | Calls `build_squad`/`find_upgrades` directly over a fixed pool. |
| Golden capture/assert of outputs | Test (golden fixtures + helpers) | All tiers (db/api/cli/ingest) | Pure observation: serialize current outputs, diff after each change. |
| Profiling (cProfile/py-spy) | Test/Dev tooling (scripts + docs) | Ingest + Builder hot paths | Wrapper scripts + documented PID-attach; not part of the test run. |
| Regression gating | Test (CI-style local gate) | — | `--benchmark-compare-fail` against committed baselines. |

**Key tier note:** nothing in Phase 1 touches a `fc26/` runtime tier. Every capability lives in `tests/benchmarks/` and `pyproject.toml`/`conftest.py`. This is what makes "zero behavior change" trivially true for Phase 1.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest-benchmark | 5.2.3 (current; pin `>=5,<6`) | Committed timing baselines + regression gate; auto-calibrated rounds; `benchmark` fixture | De-facto pytest timing plugin; integrates with the existing pytest suite; saves JSON baselines and fails on regression via `--benchmark-compare-fail`. [VERIFIED: PyPI — pytest-benchmark 5.2.3, released 2025-11-09, supports CPython 3.9-3.14, repo github.com/ionelmc/pytest-benchmark] |
| py-spy | 0.4.2 (current; pin `>=0.4`) | Sampling profiler that attaches to a running `fc26 serve` / refresh PID (flame graphs, no code change) | Production/Stable sampling profiler; attaches to a live process without restart — ideal for the async refresh + running API. [VERIFIED: PyPI — py-spy 0.4.2, Production/Stable, MIT, repo github.com/benfred/py-spy] |
| cProfile | stdlib (Python 3.14.5) | Deterministic call-graph attribution ("where does the time go") for refresh + build/upgrade | Stdlib, zero dependency, function-level totals; perfect for confirming the JSON re-parse / chem-recompute hot paths before/after a change. [CITED: docs.python.org/3/library/profile.html] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8 (already a dev dep) | Test runner hosting the benchmark + golden suites | Already present (`pyproject.toml:16`). |
| Starlette `TestClient` (via `fastapi.testclient`) | bundled with fastapi>=0.111 | In-process API calls for `/api/*` benchmarks + golden | Already used (`tests/test_api.py:4`). No new dep. |
| snakeviz | latest (optional, dev-only) | Browser visualization of a cProfile `.prof` dump | Optional convenience for BENCH-04; document, don't require. [ASSUMED — not verified on PyPI this session] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-benchmark | `pytest-codspeed` | CodSpeed gives instruction-count stability (great for noisy CI) but is SaaS-oriented and there is no CI here; pytest-benchmark's committed local JSON baselines fit a single-dev, no-CI repo better. |
| pytest-benchmark | hand-rolled `time.perf_counter` harness | Loses auto-calibration, statistics, save/compare/compare-fail; reinvents the safety net. Don't. |
| py-spy | `austin` | Both are sampling profilers; py-spy is more widely documented and the research files converged on it. austin is a fine alternative if py-spy's macOS sudo requirement is a blocker. |
| Frozen-corpus golden | Golden against the live `data/players.json` | Live DB changes on every refresh → golden would break on data updates, not on behavior changes. Frozen corpus is mandatory for build/upgrade/api golden. |

**Installation:**
```bash
# add to pyproject.toml [project.optional-dependencies] dev, then:
pip install -e ".[dev]"
# (snakeviz optional, dev-only: pip install snakeviz)
```

**Version verification:** pytest-benchmark 5.2.3 and py-spy 0.4.2 confirmed against PyPI on 2026-06-18 with established source repos (see Package Legitimacy Audit). The repo runs Python 3.14.5 (`python3 --version`), within pytest-benchmark's supported range. The repo currently declares only `dev = ["pytest>=8", "pytest-cov>=5"]` (`pyproject.toml:16`) — no benchmark/profiling tooling exists yet (confirmed: QUALITY.md:41).

## Package Legitimacy Audit

> slopcheck was **not available** in this environment (`command -v slopcheck` → not found) and `pip index`/`pip` were restricted in the sandbox. Versions and source repos were verified directly against the PyPI JSON API via WebFetch. Both packages are long-established, widely used, and have authoritative source repositories. Per protocol, because slopcheck could not run, the planner should still gate the actual `pip install` behind a `checkpoint:human-verify` (or a one-line manual `pip index versions` check) before installing — strictly safer, near-zero cost given these are well-known packages.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| pytest-benchmark | PyPI | mature (5.x line; 5.2.3 released 2025-11-09) | very high (standard pytest plugin) | github.com/ionelmc/pytest-benchmark | unavailable | Approved — verify install via `pip index versions pytest-benchmark` |
| py-spy | PyPI | mature (Production/Stable, 0.4.2) | very high (standard profiler) | github.com/benfred/py-spy | unavailable | Approved — verify install via `pip index versions py-spy` |
| snakeviz | PyPI | mature (optional) | high | github.com/jiffyclub/snakeviz | unavailable | Optional — `[ASSUMED]`, gate before install if added |

**Packages removed due to slopcheck [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────────────────────┐
                         │  pyproject.toml [dev] += pytest-benchmark,    │
                         │  py-spy   +   [tool.pytest] markers           │
                         └───────────────────────┬─────────────────────┘
                                                 │ registers
                                                 ▼
   pytest invocation ──► tests/conftest.py ──► --run-bench / -m benchmark gate
        │                  (mirror live)         (skip benchmark+golden by default)
        │                                                │
        │ default run (fast, offline)                    │ opt-in run
        ▼                                                ▼
   existing ~346 tests (unchanged)        tests/benchmarks/
   = CORRECTNESS floor                    ├── conftest.py / fixtures.py
                                          │     deterministic corpus + tmp DB
                                          │
        ┌─────────────────────────────────┼──────────────────────────────────┐
        ▼                                  ▼                                   ▼
  BENCHMARK suite                   GOLDEN-CAPTURE                      PROFILING (BENCH-04)
  (BENCH-01/02)                     (BENCH-03)                          docs + scripts
        │                                  │                                   │
        │ benchmark(fn) ──► .benchmarks/   │ capture mode: write golden/*.json │ profile_refresh.py
        │  committed JSON baselines        │ assert mode:  diff vs committed    │   → cProfile .prof
        │                                  │                                   │ py-spy record --pid
        ▼                                  ▼                                   ▼
  targets:                          golden targets:                     attach to `fc26 serve`
   db.find_all / find_by_id          refresh: players.json bytes         or refresh process,
   db.upsert (single)                 + Expand/EnrichResult tuples       flame graph hot paths
   refresh_data (mocked HTTP)         + on_progress sequence
   build_squad / find_upgrades        build/upgrade matrix (asdict)
   /api/cards|build|upgrade|meta      /api/* JSON envelopes
   (via TestClient)                   CLI stdout (search/show/build)

   --benchmark-compare-fail mean:10%  ◄── REGRESSION GATE for Phases 2-5
   golden assert ───────────────────  ◄── ZERO-BEHAVIOR-CHANGE GATE for Phases 2-5
```

Data flow for the gate (how later phases consume Phase 1): a Phase-2..5 change runs `pytest -m benchmark --benchmark-compare=<ro-HEAD baseline> --benchmark-compare-fail=mean:10%` (must not regress) **and** `pytest -m golden` (outputs must be byte/structurally identical). A speedup only counts when the benchmark improves AND golden stays green.

### Recommended Project Structure
```
tests/
├── conftest.py              # EXTEND: add --run-bench option + benchmark/golden skip logic
├── fixtures/                # EXISTING html fixtures (reuse for refresh golden)
└── benchmarks/              # NEW — all Phase 1 code lives here
    ├── __init__.py
    ├── conftest.py          # corpus fixtures: frozen sample DB, tmp DB, TestClient
    ├── corpus.py            # builds/loads the committed deterministic card corpus
    ├── test_bench_db.py     # BENCH-01: find_all / find_by_id / upsert
    ├── test_bench_refresh.py# BENCH-01: refresh_data, mocked fetch_html + stub sleep
    ├── test_bench_builder.py# BENCH-01: build_squad / find_upgrades
    ├── test_bench_api.py    # BENCH-01: /api/cards|build|upgrade|meta via TestClient
    ├── test_golden_refresh.py   # BENCH-03: players.json bytes + tuples + progress
    ├── test_golden_builder.py   # BENCH-03: formation×objective×budget matrix (asdict)
    ├── test_golden_api.py       # BENCH-03: /api/* JSON envelopes
    ├── test_golden_cli.py       # BENCH-03: CLI stdout text
    ├── golden/              # COMMITTED golden fixtures (regenerated intentionally)
    │   ├── corpus.json          # the frozen deterministic card pool (~30-60 cards)
    │   ├── refresh_players.json # expected bytes after a fixtured refresh of corpus
    │   ├── refresh_result.json  # expected Expand/EnrichResult tuples + progress lines
    │   ├── builder_matrix.json  # asdict() of build/upgrade over the matrix
    │   ├── api_*.json            # expected /api/* envelopes
    │   └── cli_*.txt             # expected CLI stdout
    ├── profile_refresh.py   # BENCH-04: cProfile wrapper for refresh
    ├── profile_builder.py   # BENCH-04: cProfile wrapper for build/upgrade
    └── README.md            # BENCH-04: how to run benchmarks, baselines, cProfile, py-spy
.benchmarks/                 # COMMITTED pytest-benchmark baseline store (ro HEAD numbers)
```

### Pattern 1: Marker gating mirroring `live` (keeps default pytest fast)
**What:** Register a `benchmark` (and optionally `golden`) marker + a `--run-bench` option, and skip those tests unless opted in — exactly how `live` works today.
**When to use:** All benchmark tests and the slower golden tests; the default `pytest` run must stay fast/offline (locked constraint).
**Example:**
```python
# tests/conftest.py — EXTEND the existing file (currently conftest.py:4-19)
import pytest

def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="run tests that hit the real network")
    parser.addoption("--run-bench", action="store_true", default=False,
                     help="run perf benchmark + golden tests (opt-in)")

def pytest_collection_modifyitems(config, items):
    skip_live = pytest.mark.skip(reason="live crawl test: pass --run-live to run")
    skip_bench = pytest.mark.skip(reason="benchmark/golden test: pass --run-bench (or -m benchmark)")
    run_live = config.getoption("--run-live")
    # benchmark tests also run when the user explicitly selects -m benchmark/-m golden
    selected = config.getoption("-m") or ""
    run_bench = config.getoption("--run-bench") or "benchmark" in selected or "golden" in selected
    for item in items:
        if "live" in item.keywords and not run_live:
            item.add_marker(skip_live)
        if ("benchmark" in item.keywords or "golden" in item.keywords) and not run_bench:
            item.add_marker(skip_bench)
```
```toml
# pyproject.toml [tool.pytest.ini_options] — EXTEND markers (currently line 29)
markers = [
  "live: hits the real network (opt-in via --run-live)",
  "benchmark: perf baseline timing (opt-in via --run-bench or -m benchmark)",
  "golden: output-equivalence check (opt-in via --run-bench or -m golden)",
]
# keep default run fast: benchmark stats add overhead; only collect on opt-in.
addopts = "-p no:benchmark"   # disable the plugin's hooks on the default run; re-enable for -m benchmark
```
> Note on `addopts`/`-p no:benchmark`: the plugin's calibration adds per-test overhead even for skipped tests in some versions. The simplest robust approach is the marker-skip above; the `-p no:benchmark` toggle is an optional belt-and-suspenders. Verify the default-run timing after wiring and drop the toggle if unnecessary. [ASSUMED — exact overhead is version-dependent; measure]

### Pattern 2: Benchmark a function with the `benchmark` fixture (BENCH-01)
**What:** Wrap the target call in the `benchmark` fixture; it auto-calibrates rounds and returns the function's result so you can also assert correctness in the same test.
**When to use:** Every BENCH-01 target.
**Example:**
```python
# tests/benchmarks/test_bench_db.py
import pytest

pytestmark = pytest.mark.benchmark

def test_bench_find_all(benchmark, corpus_repo):       # corpus_repo: fixture, see conftest
    cards = benchmark(corpus_repo.find_all)
    assert len(cards) == EXPECTED_CORPUS_SIZE          # pins output while timing

def test_bench_upsert_single(benchmark, corpus_repo, sample_card):
    # benchmark a single upsert into a populated DB (the O(n) cost Phase 2 must beat)
    benchmark(corpus_repo.upsert, sample_card)
```
[CITED: pytest-benchmark.readthedocs.io/en/latest/usage.html — `benchmark(callable, *args, **kwargs)` returns the callable's result]

### Pattern 3: Offline deterministic refresh via injected fetch_html (BENCH-01 + BENCH-03)
**What:** Drive `refresh_data` with a `fetch_html` that maps URLs to committed HTML fixtures and a `sleep` that is a no-op. This is exactly the existing test idiom — refresh is fully injected (`refresh.py:45-46`, `tests/test_refresh.py:22-25`).
**When to use:** Both the refresh benchmark (timing without network variance) and the refresh golden (byte/tuple/progress capture).
**Example:**
```python
# tests/benchmarks/conftest.py (sketch)
def make_offline_fetch(fixture_map):
    def fetch_html(url: str) -> str:
        for needle, path in fixture_map.items():
            if needle in url:
                return path.read_text(encoding="utf-8")
        raise KeyError(f"no fixture for {url}")   # forces deterministic, total mapping
    return fetch_html

# usage in a benchmark/golden test:
from fc26.ingest.refresh import refresh_data
progress = []
result = refresh_data(
    repo, min_ovr=87,
    fetch_html=make_offline_fetch(FUTBIN_FIXTURES),
    sleep=lambda _s: None,                      # stub sleep -> offline + fast
    on_progress=progress.append,                # capture the progress sequence
    manifest_path=None,
)
```

### Anti-Patterns to Avoid
- **Golden against the live `data/players.json`.** It mutates on every refresh — golden would fail on data updates, not behavior changes. Use the frozen corpus. (The real DB is only for read/parse *benchmarks*, gated like `_REAL_DB`.)
- **Editing a behavioral test to make a future optimization pass.** The ~346 existing tests are the correctness floor; the benchmark/golden suite is a *separate* speed/equivalence gate (QUALITY.md, SUMMARY.md §4).
- **Capturing golden non-deterministically.** Anything with `datetime.now()` (e.g. the refresh manifest `refreshed_at`, refresh.py:78) must be excluded/normalized before diffing, or `manifest_path=None` to skip it.
- **Letting benchmarks run in the default `pytest`.** Breaks the "default run fast/offline" constraint. Always gate behind the marker.
- **Asserting absolute milliseconds in a test.** Benchmarks record numbers; the *gate* is relative (`--benchmark-compare-fail`), not an absolute assertion (laptop variance, §Pitfalls).
- **Committing baseline JSON captured on a busy machine.** Capture `ro` HEAD baselines on a quiet machine, single-purpose run.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timing with statistics + warmup | `time.perf_counter()` loops + manual mean/stddev | `pytest-benchmark` `benchmark` fixture | Auto-calibration, outlier handling, rounds, JSON save/compare/compare-fail — all the parts you'd get wrong. |
| Committed baselines + regression detection | A custom JSON file + manual % comparison | `--benchmark-autosave` / `--benchmark-compare` / `--benchmark-compare-fail` | Battle-tested storage + comparison semantics; one flag is the whole gate. |
| Live-process profiling | Inserting `cProfile` into `fc26 serve` | `py-spy record --pid <pid>` | Attaches without code change or restart; no behavior risk to the running server. |
| Offline deterministic scrape | Mocking httpx with `responses`/`respx` | The existing injected `fetch_html`/`sleep` seam | The code already takes these as parameters — no patching library needed (QUALITY.md "injected, not patched"). |
| Byte-equality of JSON | Field-by-field comparison | Compare the exact serialized string / `read_bytes()` | `_save` already sorts by id (db.py:99) and uses fixed `indent=2`/`ensure_ascii=False`; the on-disk bytes are deterministic, so a raw byte compare is the truest gate. |

**Key insight:** Phase 1's entire value is *not* writing custom measurement code. pytest-benchmark + the existing injection seam + raw-bytes comparison give a complete harness with almost no bespoke logic; the only real authoring is (a) the deterministic corpus, (b) the golden capture/assert helpers, and (c) the cProfile/py-spy docs.

## Common Pitfalls

### Pitfall 1: Benchmark timing variance on a dev laptop
**What goes wrong:** Wall-clock benchmarks swing 5-20% run-to-run from thermal throttling, background apps, and OS scheduling — a strict gate produces false regressions.
**Why it happens:** macOS dev machine, no isolated CI runner, GIL/event-loop scheduling.
**How to avoid:** Start the gate loose (`--benchmark-compare-fail=mean:10%`), capture `ro` HEAD baselines on a quiet machine, prefer `min` or `median` over `mean` for the comparison metric if variance is high, and let pytest-benchmark auto-calibrate rounds (don't pin tiny `--benchmark-rounds`). Tighten only once baselines are stable. [CITED: FRONTEND-TOOLING.md B3; SUMMARY.md §7]
**Warning signs:** The same code "regresses" then "improves" across consecutive runs; large stddev in the benchmark table.

### Pitfall 2: Golden brittleness from non-determinism
**What goes wrong:** Golden diffs fail on timestamps, dict ordering, or float formatting that aren't behavior changes.
**Why it happens:** `refreshed_at` timestamp in the manifest (refresh.py:78); any set→list ordering; price/score floats.
**How to avoid:** Use `manifest_path=None` for refresh golden (or strip `refreshed_at`); rely on the existing id-sort in `_save` (db.py:99) and the `versions`-no-filter / `leagues|nations|clubs`-filter-falsy quirk in `/api/meta` (app.py:331-334) being reproduced verbatim; serialize the build/upgrade matrix with `dataclasses.asdict` (stable field order) and `json.dumps(..., sort_keys=True)` for the diff. Capture and assert with the *same* serializer.
**Warning signs:** Golden fails immediately on re-run with no code change.

### Pitfall 3: Golden coupled to the live DB (the headline trap)
**What goes wrong:** Golden fixtures built from `data/players.json` break whenever the card pool is refreshed — punishing data updates, not behavior changes.
**Why it happens:** Convenience of using the real DB; the live test pattern (`_REAL_DB`) reads the real file.
**How to avoid:** Build golden + most benchmarks on a **committed frozen corpus** (`tests/benchmarks/golden/corpus.json`, ~30-60 cards carved from the real DB once, with stable ids/prices). Reserve the real 4.4 MB DB only for the read/parse benchmarks where size realism matters, and gate those exactly like `_REAL_DB` (skip if absent). [CITED: task brief focus #4; CACHING.md §verification]
**Warning signs:** A golden test that imports `data/players.json` directly; a golden test that fails after `fc26 refresh`.

### Pitfall 4: Benchmarks slow down / pollute the default test run
**What goes wrong:** `pytest` (the fast offline gate everyone runs) gets slow or hits the benchmark plugin's calibration overhead.
**Why it happens:** Forgetting the marker skip, or the plugin's global hooks.
**How to avoid:** Marker-gate everything (Pattern 1); verify `pytest` (no flags) collects and skips all `benchmark`/`golden` tests; measure default-run wall time before/after Phase 1 and confirm it's unchanged. [CITED: locked constraint; conftest.py:13-19]
**Warning signs:** `pytest` runtime jumps after Phase 1 lands.

### Pitfall 5: py-spy can't attach on macOS
**What goes wrong:** `py-spy record --pid …` fails with a permissions error.
**Why it happens:** macOS requires py-spy to run as **root** (`sudo`), and System Integrity Protection blocks reading memory of binaries in `/usr/bin` (the system Python). [VERIFIED: github.com/benfred/py-spy README — "OSX always requires running as root"]
**How to avoid:** Document `sudo py-spy record --pid <pid> -o profile.svg`. The repo's interpreter is Homebrew (`/opt/homebrew/bin/python3`), not `/usr/bin`, so SIP does **not** block it — note this in the README so the operator uses the venv/Homebrew python, never the system one. cProfile (stdlib, no sudo) is the no-friction default for BENCH-04; py-spy is the live-process complement.
**Warning signs:** "Permission denied" / "Operation not permitted" from py-spy.

## Code Examples

### Capture baselines on ro HEAD, then gate later phases (BENCH-01 + BENCH-02)
```bash
# Source: pytest-benchmark.readthedocs.io/en/latest/usage.html (flags verified 2026-06-18)

# 1) On ro HEAD, capture + commit baselines (the reference for all later phases):
pytest -m benchmark --run-bench \
  --benchmark-autosave \
  --benchmark-storage=file://./.benchmarks
git add .benchmarks && git commit -m "perf: commit ro-HEAD benchmark baselines"

# 2) In any later optimization phase, fail the run if a path regresses:
pytest -m benchmark --run-bench \
  --benchmark-storage=file://./.benchmarks \
  --benchmark-compare \
  --benchmark-compare-fail=mean:10%        # also accepts e.g. min:5% or mean:0.001 (seconds)
```
Flag reference (verified): `--benchmark-save NAME` / `--benchmark-autosave` (save into `STORAGE/…json`), `--benchmark-storage URI` (default `file://./.benchmarks`), `--benchmark-compare [NUM|ID]` (compare vs a saved run or the latest), `--benchmark-compare-fail EXPR` (fail on regression; EXPR is `metric:threshold`, threshold a `%` or seconds; repeatable). [CITED: pytest-benchmark.readthedocs.io/en/latest/usage.html]

### Golden capture/assert with a regen switch (BENCH-03)
```python
# Source: pattern derived from dataclasses.asdict + repo's deterministic _save (db.py:96-101)
import json, os
from dataclasses import asdict
from pathlib import Path

GOLDEN = Path(__file__).parent / "golden"
REGEN = os.environ.get("REGEN_GOLDEN") == "1"   # intentional regeneration switch

def golden_check(name: str, value) -> None:
    path = GOLDEN / name
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if REGEN:
        path.write_text(serialized, encoding="utf-8")   # regenerate intentionally
        return
    assert serialized == path.read_text(encoding="utf-8"), f"golden drift: {name}"

# build/upgrade matrix golden:
import pytest
from itertools import product
from fc26.chem.formations import FORMATIONS
from fc26.builder.build import build_squad

pytestmark = pytest.mark.golden
OBJECTIVES = ("meta", "rating")          # fc26/builder/meta.py:18 VALID_OBJECTIVES
BUDGETS = (50_000, 250_000, 5_000_000)   # tight / mid / generous

def test_golden_build_matrix(corpus_pool):
    results = {}
    for formation, objective, budget in product(FORMATIONS, OBJECTIVES, BUDGETS):
        try:
            r = build_squad(formation, corpus_pool, budget=budget, objective=objective)
            results[f"{formation}|{objective}|{budget}"] = asdict(r)
        except Exception as exc:                       # capture deterministic errors too
            results[f"{formation}|{objective}|{budget}"] = {"error": type(exc).__name__, "msg": str(exc)}
    golden_check("builder_matrix.json", results)
```
Regeneration is **intentional and explicit** (`REGEN_GOLDEN=1 pytest -m golden --run-bench`); the default mode **asserts**. This is the "regenerated intentionally vs asserted" requirement.

### Byte-identical refresh golden (BENCH-03)
```python
# Source: db.py _save is deterministic (sorted by id, fixed indent) -> raw bytes are stable
import pytest
pytestmark = pytest.mark.golden

def test_golden_refresh_bytes(tmp_path, corpus_seed_repo, offline_fetch):
    progress = []
    from fc26.ingest.refresh import refresh_data
    result = refresh_data(
        corpus_seed_repo, min_ovr=87,
        fetch_html=offline_fetch, sleep=lambda _s: None,
        on_progress=progress.append, manifest_path=None,   # skip the timestamped manifest
    )
    produced = corpus_seed_repo._path.read_text(encoding="utf-8")
    golden_check_text("refresh_players.json", produced)             # exact bytes
    golden_check("refresh_result.json", {                           # tuples + progress
        "expand": list(result.expand.new_ids), "new": result.expand.new,
        "merged": result.expand.merged, "enriched": list(result.enrich.enriched),
        "progress": progress,
    })
```

### API golden + benchmark via TestClient (BENCH-01 + BENCH-03)
```python
# Source: tests/test_api.py:4,60 — existing TestClient(create_app(...)) idiom
from fastapi.testclient import TestClient
from fc26.api.app import create_app

def test_bench_api_cards(benchmark, corpus_db, corpus_squads):
    client = TestClient(create_app(corpus_db, corpus_squads))
    r = benchmark(lambda: client.get("/api/cards?limit=5000"))
    assert r.status_code == 200

def test_golden_api_meta(corpus_db, corpus_squads):       # @pytest.mark.golden
    client = TestClient(create_app(corpus_db, corpus_squads))
    golden_check("api_meta.json", client.get("/api/meta").json())
```

### CLI golden via captured stdout (BENCH-03)
```python
# Source: typer CliRunner over fc26.cli:app (cli.py:38)
from typer.testing import CliRunner
from fc26.cli import app

def test_golden_cli_search(corpus_db):                   # @pytest.mark.golden
    runner = CliRunner()
    res = runner.invoke(app, ["search", "Player", "--db", str(corpus_db), "--json"])
    assert res.exit_code == 0
    golden_check_text("cli_search.txt", res.stdout)
```
Note: `--json` output (`cli.py:53`) is the most stable to diff; rich `Table` rendering depends on `Console(width=200)` (cli.py:39) and terminal width, so prefer `--json` variants for CLI golden where the command supports it; for table-only commands, pin width via `CliRunner` env or accept the fixed `width=200`.

## Benchmark Target Map (BENCH-01)

| Benchmark | Target (file:line) | Call shape | Fixture | Guards (CONCERNS) |
|-----------|--------------------|-----------|---------|-------------------|
| db read (full parse) | `CardRepository.find_all` (db.py:48-60) | `benchmark(repo.find_all)` | real DB (gated) + corpus | 1.x / 3.1 root-cause re-parse |
| db read by id (O(n) scan) | `CardRepository.find_by_id` (db.py:62-66) | `benchmark(repo.find_by_id, some_id)` | real DB (gated) | 3.4 N+1 scans → Phase 2 O(1) |
| db write (single upsert) | `CardRepository.upsert` (db.py:85-94) | `benchmark(repo.upsert, card)` into populated DB | corpus DB | 1.1 O(n²) rewrite |
| refresh (offline) | `refresh_data` (refresh.py:41-88) | injected `fetch_html`+`sleep=noop` | corpus + html fixtures | 1.1/1.2/1.5 |
| build | `build_squad` (build.py:46) | `benchmark(build_squad, "4-2-3-1", pool, budget=…, objective=…)` | corpus pool | 3.5 chem recompute |
| upgrade | `find_upgrades` (upgrade.py:87) | `benchmark(find_upgrades, lineup, slot_cards, pool, budget=…, max_swaps=3)` | corpus pool | 3.5 |
| /api/cards | `list_cards` via TestClient (app.py:157) | `client.get("/api/cards?limit=5000")` | corpus DB | 3.1/3.2 |
| /api/build | `post_build` via TestClient (app.py:292) | `client.post("/api/build", json=…)` | corpus DB | 3.5 |
| /api/upgrade | `post_upgrade` via TestClient (app.py:278) | `client.post("/api/upgrade", json=…)` | corpus DB | 3.5 |
| /api/meta | `get_meta` via TestClient (app.py:327) | `client.get("/api/meta")` | corpus DB | 3.3 |

## Golden Capture Design (BENCH-03)

| Output domain | What to capture | Determinism notes | Source |
|---------------|-----------------|-------------------|--------|
| Refresh → `players.json` | Raw file text/bytes after a fixtured refresh of the corpus seed | `_save` sorts by id + fixed `indent=2`/`ensure_ascii=False` → bytes stable (db.py:96-101); use `manifest_path=None` to drop `refreshed_at` | refresh.py:41; db.py:96 |
| Refresh → results | `ExpandResult`/`EnrichResult` fields (new/merged/new_ids/enriched/skipped/missed) | tuples are deterministic given fixed fixtures + serial upsert | expand.py:79; enrich.py |
| Refresh → progress | The full `on_progress` line sequence (captured into a list) | order deterministic because progress is emitted from the serial loop | refresh.py:51-69 |
| Build/upgrade matrix | `asdict()` of `BuildResult`/`UpgradePlan` over FORMATIONS(12) × objectives(2) × budgets(3+); include deterministic error cases | iterate `product()`; preserve candidate order (tie-break sensitive, upgrade.py:137-139); sort_keys on diff | build.py:46; upgrade.py:87; formations.py:10; meta.py:18 |
| API responses | `.json()` of `/api/cards`, `/api/build`, `/api/upgrade`, `/api/meta` (and optionally `/api/chem`, `/api/value`) | reproduce `/api/meta` versions-no-filter quirk verbatim (app.py:334); fixed corpus → fixed JSON | app.py:157,278,292,327 |
| CLI text | `CliRunner` stdout for `search --json`, `show --json`, `build` over the corpus DB | prefer `--json` variants; table output depends on `Console(width=200)` | cli.py:38,53,112 |

## Profiling Entrypoints (BENCH-04)

| Tool | Hot path | Invocation | Notes |
|------|----------|-----------|-------|
| cProfile | refresh | `python tests/benchmarks/profile_refresh.py` → writes `refresh.prof`; view `python -m pstats refresh.prof` or `snakeviz refresh.prof` | Stdlib, deterministic attribution; runs offline via injected `fetch_html`/`sleep`. No sudo. |
| cProfile | build/upgrade | `python tests/benchmarks/profile_builder.py` → `builder.prof` | Calls `build_squad`/`find_upgrades` over the corpus (or real DB) pool. |
| py-spy | live `fc26 serve` | `sudo py-spy record --pid <pid> -o serve.svg` (or `py-spy dump --pid <pid>`) | macOS needs **sudo**; use the Homebrew/venv python (not `/usr/bin`) to avoid SIP. [VERIFIED: github.com/benfred/py-spy] |
| py-spy | live refresh process | run `fc26 refresh` in one terminal, `sudo py-spy record --pid <pid> -o refresh-live.svg` in another | Flame graph of the real network-bound refresh; complements the offline cProfile run. |

cProfile wrapper sketch (lands as `profile_refresh.py`):
```python
# Source: docs.python.org/3/library/profile.html
import cProfile, pstats
from fc26.ingest.refresh import refresh_data
# build corpus repo + offline_fetch as in benchmarks/conftest.py ...
pr = cProfile.Profile()
pr.enable()
refresh_data(repo, min_ovr=87, fetch_html=offline_fetch, sleep=lambda _s: None, manifest_path=None)
pr.disable()
pr.dump_stats("refresh.prof")
pstats.Stats("refresh.prof").sort_stats("cumulative").print_stats(25)
```

## Runtime State Inventory

> Phase 1 is purely additive test/dev tooling — it writes no runtime state, registers nothing with the OS, and renames nothing. Included for completeness per the rename/refactor checklist; all categories are "none."

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 1 adds committed fixture files under `tests/benchmarks/golden/` and `.benchmarks/`, not runtime datastores. The real `data/players.json` is read-only for benchmarks. | none |
| Live service config | None — verified: no service config changes; `fc26 serve` is unaffected. | none |
| OS-registered state | None — verified: no Task Scheduler/launchd/systemd/pm2 entries created. | none |
| Secrets/env vars | One *optional* env var introduced by the harness itself: `REGEN_GOLDEN=1` (developer-controlled golden regeneration switch). No secrets. | document in README |
| Build artifacts | None new from Phase 1 itself. Note: adding `[dev]` deps means `pip install -e ".[dev]"` must be re-run (existing `fc26.egg-info` already present from the editable install). | re-run `pip install -e ".[dev]"` after pyproject edit |

**Nothing found** in stored data, live service config, or OS-registered state — verified by reading the planned change set (test files + pyproject/conftest only).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled `timeit`/`perf_counter` timing | `pytest-benchmark` fixture + committed JSON baselines + compare-fail gate | mature (5.x) | One plugin gives calibration, stats, storage, regression gate. |
| `cProfile` only | `cProfile` (attribution) + `py-spy` (live sampling, no restart) | py-spy 0.4.x | Can profile a running server/refresh without code changes. |
| No marker for slow tests | `live` marker + `--run-live` (already in this repo) | existing | Phase 1 mirrors it with `benchmark`/`golden` + `--run-bench`. |

**Deprecated/outdated:**
- `pytest-benchmark` `--benchmark-compare-fail` format is `metric:threshold` (e.g. `mean:10%`, `min:5%`, `mean:0.001s`) — confirmed current syntax, unchanged across 4.x→5.x.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `snakeviz` is a current, legitimate PyPI package (optional viz for cProfile) | Standard Stack (Supporting) | Low — optional; if wrong, drop it, cProfile `pstats` works without it. Verify before adding. |
| A2 | The `-p no:benchmark` / addopts toggle is needed to keep the default run fast | Pattern 1 note | Low — measure default-run time; if marker-skip alone keeps it fast, drop the toggle. |
| A3 | A ~30-60 card frozen corpus is large enough to exercise build/upgrade meaningfully yet small enough to be fast/stable | Recommended Structure; Pitfall 3 | Medium — if too small, build/upgrade may hit "no eligible card" errors for some formations; size the corpus to cover every position across ≥2 leagues/nations. Validate against FORMATIONS during corpus authoring. |
| A4 | Reusing existing `tests/fixtures/*.html` covers the refresh golden's fetch_html needs (futbin list pages + futgg/fcratings player pages) | Pattern 3; Golden Capture | Medium — the existing fixtures were authored for unit tests; the refresh golden may need a couple more committed HTML pages to drive a full expand→enrich pass. Inventory fixture coverage during planning. |
| A5 | py-spy installs cleanly on macOS arm64 via pip (prebuilt wheel) | Standard Stack; Profiling | Low — py-spy ships wheels; if a wheel is missing for this platform, the cProfile path still satisfies BENCH-04 and py-spy can be documented as optional. |

**Note:** The version facts for pytest-benchmark (5.2.3) and py-spy (0.4.2), their Python-3.14 support, the macOS-sudo/SIP behavior, and the `--benchmark-*` flag syntax are **VERIFIED/CITED** (PyPI JSON + official docs, 2026-06-18), not assumed.

## Open Questions

1. **Exact composition of the deterministic corpus.**
   - What we know: ~30-60 cards carved from `data/players.json`, must cover every position in FORMATIONS across ≥2 leagues/nations/clubs and have stable prices, for build/upgrade to produce non-trivial, deterministic results.
   - What's unclear: the precise card set; whether to script its extraction (reproducible) or hand-curate.
   - Recommendation: write a small `corpus.py` that deterministically selects cards from the real DB by id (committed selection list) so it can be regenerated and reviewed; commit the resulting `golden/corpus.json`.

2. **Refresh-golden fixture completeness.**
   - What we know: refresh = expand (futbin list pages) → enrich (fcratings top100 + player/club pages). Some HTML fixtures exist; `expand`/`enrich` are injected.
   - What's unclear: whether the committed fixtures drive a *complete* expand→enrich pass over the corpus, or whether a few more committed HTML pages are needed.
   - Recommendation: during planning, inventory `tests/fixtures/` against the URLs `refresh_data` will request for the corpus; add any missing committed HTML. Alternatively, scope the refresh golden to a tightly fixtured mini-refresh (a few pages/cards) — enough to pin bytes/tuples/progress without a full 2,400-card scrape.

3. **`/api/build` and `/api/upgrade` golden over the matrix may be slow.**
   - What we know: build/upgrade are CPU-heavy even on a small pool; the matrix is 12×2×3 = 72 builds.
   - What's unclear: total wall time on the corpus.
   - Recommendation: it's gated behind `--run-bench`/`-m golden` so default `pytest` is unaffected; if the matrix is too slow even opt-in, subset formations for golden (keep full matrix for the benchmark a couple of representative cells) — but prefer full coverage since it's the equivalence gate for Phase 3.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | all of Phase 1 | ✓ | 3.14.5 (Homebrew, `/opt/homebrew/bin/python3`) | — |
| pytest | benchmark+golden tests | ✓ (declared dev dep) | >=8 | — |
| pytest-benchmark | BENCH-01/02 | ✗ (not installed; not in pyproject) | needs 5.2.3 | none — must `pip install` (add to `[dev]`) |
| py-spy | BENCH-04 (live profiling) | ✗ (not installed) | needs 0.4.2 | cProfile (stdlib, already available) covers BENCH-04's documented entrypoints; py-spy is the live-process complement |
| cProfile | BENCH-04 | ✓ (stdlib) | 3.14.5 | — |
| fastapi `TestClient` | API benchmarks/golden | ✓ (via fastapi>=0.111) | bundled | — |
| typer `CliRunner` | CLI golden | ✓ (via typer>=0.12) | bundled | — |
| `data/players.json` (real DB) | read/parse benchmarks (size realism) | ✓ | 2,434 cards / 4.43 MB | frozen corpus (already the primary fixture; real DB only for realistic-size read benches, gated like `_REAL_DB`) |
| pip (sandbox) | installing dev deps | ✗ restricted in research sandbox; `pip3` present at `/opt/homebrew/bin/pip3` | — | install happens at execution time, not research time |

**Missing dependencies with no fallback:**
- `pytest-benchmark` — required for BENCH-01/02; must be added to `pyproject.toml [dev]` and installed. (This is the intended, allowed dev-dependency addition.)

**Missing dependencies with fallback:**
- `py-spy` — BENCH-04 is satisfiable with cProfile alone (stdlib, no sudo); py-spy adds live-process flame graphs and is strongly recommended but not strictly blocking. On macOS it needs `sudo` and the Homebrew python.

## Validation Architecture

> nyquist_validation is `true` in `.planning/config.json` — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8 (+ pytest-benchmark 5.2.3 to be added) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (markers at line 29); `tests/conftest.py` (skip logic at lines 4-19) |
| Quick run command | `pytest -q` (default: fast, offline, benchmark+golden skipped) |
| Full suite command | `pytest --run-live` (correctness) + `pytest -m "benchmark or golden" --run-bench` (Phase 1 deliverables) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BENCH-01 | Benchmarks exist + capture committed baselines for db/refresh/builder/api | benchmark | `pytest -m benchmark --run-bench --benchmark-autosave` | ❌ Wave 0 (`tests/benchmarks/test_bench_*.py`) |
| BENCH-02 | Regression gate fails on >threshold slowdown vs committed baseline | benchmark/gate | `pytest -m benchmark --run-bench --benchmark-compare --benchmark-compare-fail=mean:10%` | ❌ Wave 0 (gate is a flag combo; needs committed `.benchmarks/`) |
| BENCH-03 | Golden outputs (refresh bytes/tuples/progress, build/upgrade matrix, api JSON, cli text) asserted unchanged | golden/equivalence | `pytest -m golden --run-bench` | ❌ Wave 0 (`tests/benchmarks/test_golden_*.py` + `golden/` fixtures) |
| BENCH-04 | cProfile + py-spy entrypoints documented for refresh + build/upgrade | docs + smoke | `python tests/benchmarks/profile_refresh.py` (smoke) ; manual py-spy per README | ❌ Wave 0 (`profile_*.py` + `README.md`) |
| (all) | Default `pytest` stays fast/offline + all existing tests green | regression | `pytest -q` (assert runtime unchanged; 0 failures) | ✅ existing ~346 tests |

### Sampling Rate
- **Per task commit:** `pytest -q` (fast offline floor must stay green) + `pytest -m golden --run-bench` for the golden task being built.
- **Per wave merge:** `pytest -m "benchmark or golden" --run-bench` (full Phase 1 suite) + `pytest --run-live` if a live path was touched.
- **Phase gate:** `ro` HEAD baselines committed in `.benchmarks/`; golden fixtures committed in `tests/benchmarks/golden/`; default `pytest` runtime confirmed unchanged; all existing tests green.

### Wave 0 Gaps
- [ ] `pyproject.toml` — add `pytest-benchmark>=5,<6` and `py-spy` to `[dev]`; add `benchmark`/`golden` markers
- [ ] `tests/conftest.py` — add `--run-bench` + skip logic for `benchmark`/`golden` (mirror `live`)
- [ ] `tests/benchmarks/conftest.py` + `corpus.py` — deterministic corpus fixtures, offline fetch helper, golden helpers (`golden_check` / `golden_check_text` with `REGEN_GOLDEN`)
- [ ] `tests/benchmarks/golden/corpus.json` — committed frozen card pool
- [ ] `tests/benchmarks/test_bench_{db,refresh,builder,api}.py` — BENCH-01 benchmarks
- [ ] `tests/benchmarks/test_golden_{refresh,builder,api,cli}.py` — BENCH-03 golden
- [ ] `tests/benchmarks/golden/*.json|*.txt` — committed golden fixtures (captured on ro HEAD)
- [ ] `.benchmarks/` — committed pytest-benchmark baseline store (captured on ro HEAD)
- [ ] `tests/benchmarks/profile_refresh.py` + `profile_builder.py` + `README.md` — BENCH-04
- [ ] Framework install: `pip install -e ".[dev]"` after pyproject edit

## Security Domain

> `security_enforcement` is not set in `.planning/config.json` (absent = enabled). However Phase 1 introduces **no** runtime surface: no new endpoints, no auth, no input handling, no network, no crypto, no data persistence. It adds dev/test tooling only.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase adds no auth surface |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No access-controlled resources added |
| V5 Input Validation | no | No new user inputs; `fetch_html` is injected with committed fixtures, not network input |
| V6 Cryptography | no | No crypto |
| V12 Files/Resources | minimal | Golden/baseline files are committed test fixtures under `tests/` — review they contain no real secrets/PII (card data is public game data) |
| V14 Configuration | minimal | New dev deps must be legitimacy-verified before install (see Package Legitimacy Audit) — supply-chain is the only relevant surface |

### Known Threat Patterns for this phase's stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious/typosquatted dev dependency (`pytest-benchmark`, `py-spy`) | Tampering / Elevation | Verify on PyPI with established source repo before install (done: both verified); planner gates install behind `checkpoint:human-verify` since slopcheck was unavailable |
| Committing secrets into golden/baseline fixtures | Information Disclosure | Golden corpus is public FUT card data only; review fixtures before commit |
| `sudo py-spy` on a dev machine | Elevation (operator action) | Document as an explicit manual step; not part of the automated test run; never required for the default gate (cProfile covers BENCH-04 sudo-free) |

## Sources

### Primary (HIGH confidence)
- PyPI JSON API — `pypi.org/pypi/pytest-benchmark/json` (version 5.2.3, 2025-11-09, Python 3.9-3.14, repo github.com/ionelmc/pytest-benchmark)
- PyPI JSON API — `pypi.org/pypi/py-spy/json` (version 0.4.2, Production/Stable, MIT, repo github.com/benfred/py-spy)
- pytest-benchmark docs — `pytest-benchmark.readthedocs.io/en/latest/usage.html` (`--benchmark-save`/`--benchmark-autosave`/`--benchmark-storage`/`--benchmark-compare`/`--benchmark-compare-fail` syntax)
- py-spy README — `github.com/benfred/py-spy` (macOS always requires root; SIP blocks `/usr/bin` binaries)
- The footie codebase (read directly): `fc26/db.py:42-114`, `fc26/ingest/refresh.py:29-88`, `fc26/ingest/expand.py:29-95`, `fc26/ingest/enrich.py:16-83`, `fc26/api/app.py:157-342`, `fc26/builder/build.py:46-105`, `fc26/builder/upgrade.py:87-126`, `fc26/chem/formations.py:10-23`, `fc26/builder/meta.py:18`, `fc26/cli.py:1-130`, `pyproject.toml`, `tests/conftest.py`, `tests/test_api.py:38-61,540-583`, `tests/test_refresh.py`, `tests/test_db.py:1-44`, `tests/test_expand.py`
- The planning research: `.planning/research/{SUMMARY,FRONTEND-TOOLING,CACHING,BACKEND-COMPUTE,ASYNC-SCRAPING}.md`; `.planning/codebase/{QUALITY,CONCERNS}.md`; `.planning/{PROJECT,REQUIREMENTS,ROADMAP,STATE}.md`

### Secondary (MEDIUM confidence)
- FRONTEND-TOOLING.md §B (the harness recommendation: pytest-benchmark + cProfile + py-spy), cross-verified against the official docs above

### Tertiary (LOW confidence)
- snakeviz (optional cProfile viz) — referenced in research files; not independently verified on PyPI this session (`[ASSUMED]`)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pytest-benchmark 5.2.3 + py-spy 0.4.2 verified against PyPI with source repos; Python 3.14 support confirmed; flag syntax confirmed against official docs.
- Architecture: HIGH — every benchmark/golden target mapped to a real file:line in this repo; capture approach built directly on the existing injected-`fetch_html` seam and deterministic `_save`; reuses the established `live`/`_REAL_DB`/`TestClient`/`CliRunner` patterns.
- Pitfalls: HIGH — timing variance, golden brittleness, live-DB coupling, default-run pollution, and macOS py-spy permissions are all concrete and sourced.

**Research date:** 2026-06-18
**Valid until:** 2026-07-18 (stable tooling; re-verify pytest-benchmark/py-spy versions if revisited after 30 days)
