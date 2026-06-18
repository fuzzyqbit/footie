# Performance harness (`tests/benchmarks/`)

The measurement instrument + behavior-equivalence safety net for the
performance milestone. **Purely additive** — nothing here changes `fc26/`
runtime behavior. The default `pytest` run never touches it: benchmark and
golden tests are gated behind `--run-bench` (mirrors the existing `--run-live`).

> **Env note:** this repo's CI/dev shell may set `FORCE_COLOR`, which makes Rich
> emit ANSI codes into captured output. Run the suite with `NO_COLOR=1` for
> stable, env-independent results (the CLI golden test also forces no-color
> internally).

## Layout

```
tests/benchmarks/
  corpus.py                 # frozen-corpus loader, offline fetch, golden helpers
  conftest.py               # tmp_repo / corpus_cards fixtures
  golden/corpus.json        # frozen 40-card pool (committed; decoupled from live DB)
  golden/*.json|*.txt       # committed golden fixtures
  test_bench_*.py           # BENCH-01 benchmarks
  test_golden_*.py          # BENCH-03 equivalence checks
  profile_*.py              # BENCH-04 cProfile entrypoints
.benchmarks/                # committed pytest-benchmark baselines (ro HEAD)
```

The **frozen corpus** (`golden/corpus.json`) is a small, diverse, fully-usable
40-card pool selected once from the real `data/players.json` and committed.
Benchmarks and golden tests read it — never the live `data/players.json`, which
mutates on every refresh. (It covers 12 of 15 formation positions; CF/LWB/RWB
have no usable cards in the source data, so builder tests use formations that
don't need them: 4-2-3-1, 4-3-3, 4-4-2.)

## Running benchmarks (BENCH-01)

```bash
NO_COLOR=1 pytest tests/benchmarks/ -m benchmark --run-bench
```

What's measured:
- **db** — `find_all`, `find_by_id`, single `upsert` (and a `live`-gated read of
  the real ~4.4 MB DB for realistic-size numbers, run with `--run-live`).
- **refresh** — bulk `upsert` of the whole corpus into an empty repo: the O(n²)
  whole-file-rewrite-per-card write amplification that Phase 2 fixes. (The
  network fetch stages — expand listing pages, enrich per-card pages — are
  excluded by design: I/O-bound, rate-limited, Phase 4's concern, and not
  offline-reproducible here.)
- **builder** — `build_squad` + `find_upgrades` (the chemistry compute hot loop).
- **api** — `/api/cards`, `/api/meta`, `/api/build`, `/api/upgrade` via TestClient.

## Baselines + regression gate (BENCH-02)

Baselines are captured on `ro` HEAD and committed under `.benchmarks/`:

```bash
NO_COLOR=1 pytest tests/benchmarks/ -m benchmark --run-bench \
  --benchmark-autosave --benchmark-storage=.benchmarks
```

The regression gate fails the run if any benchmarked path's mean is >10% slower
than the committed baseline:

```bash
NO_COLOR=1 pytest tests/benchmarks/ -m benchmark --run-bench \
  --benchmark-storage=.benchmarks --benchmark-compare=0001 \
  --benchmark-compare-fail=mean:10%
```

Use this in later phases: after an optimization, the targeted path should get
**faster** and nothing else should regress past +10%.

> **Note on variance:** `test_bench_bulk_upsert` is comparatively noisy (few
> rounds, large work unit). After a *real* improvement in a later phase,
> re-baseline (`--benchmark-autosave`) and commit the new reference rather than
> chasing single-run noise.

## Profiling (BENCH-04)

### cProfile (default, no sudo)

Two runnable entrypoints attribute time within the hot paths:

```bash
python tests/benchmarks/profile_refresh.py   # refresh write amplification
python tests/benchmarks/profile_builder.py   # build/upgrade compute
```

Each prints the top 30 functions by cumulative time. Use these to confirm
*where* the time goes before optimizing in Phases 2-3 (e.g. `_save` / `json`
for refresh; `compute_chemistry` / `canonical_*` for the builder).

### py-spy (live sampling — manual, macOS caveat)

py-spy samples a running process and renders flamegraphs. On macOS it requires
`sudo`, and System Integrity Protection blocks attaching to the SIP-protected
`/usr/bin/python3` — use a Homebrew interpreter (`/opt/homebrew/bin/python3`,
which this project uses) instead:

```bash
sudo py-spy record -o profile.svg -- /opt/homebrew/bin/python3 tests/benchmarks/profile_refresh.py
sudo py-spy top -- /opt/homebrew/bin/python3 tests/benchmarks/profile_builder.py
```

py-spy is **never** part of the automated test run — it's an interactive,
sudo-requiring tool. cProfile (above) covers the sudo-free default.
