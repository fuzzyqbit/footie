# Quality & Testing

**Analysis Date:** 2026-06-17

## Test Suite At A Glance
| Suite | Location | Runner | Count | Network |
|-------|----------|--------|-------|---------|
| Python unit/integration | `tests/*.py` | pytest | ~346 `test_` / 28 files | mocked (DI + monkeypatch) |
| Python live | `tests/` marker `live` | pytest `--run-live` | 5 | real network / real DB |
| Web unit | `web/src/**/*.test.{ts,tsx}` | Vitest + jsdom | ~72 / 20 files | mocked (MSW) |
| Web e2e | `web/e2e/app.spec.ts` | Playwright (chromium) | 7 | live full stack |

## How Tests Run
- Python: `pytest` (live auto-skipped), `pytest --run-live`, `pytest --cov=fc26`. Skip logic `tests/conftest.py:4-19`; marker `pyproject.toml:28-29`.
- Web: `npm test` (vitest, unit only), `npm run coverage` (v8), `npm run e2e` (`build && playwright test`).

## Test Types
- **Unit (majority):** pure parse/chem/builder over local HTML fixtures in `tests/fixtures/`.
- **Integration:** `tmp_path` JSON DB (`CardRepository(tmp_path/"players.json")`); FastAPI via `TestClient(create_app(...))`.
- **Live (5):** real crawl + real committed DB assertions (`total >= 2400`, chem 33/33); `pytest.skip` when DB absent.
- **Web e2e:** live smoke of all pages against real `fc26 serve` on :8026; assertions data-resilient.

## Mocking Strategy (strong signal)
Side effects are **injected, not patched**: `fetch_html`/`sleep`/`on_progress` passed in; throttle `sleep` stubbed everywhere → default run deterministic, offline, fast.

## Coverage Shape
- **Well covered:** parsers, chem engine/rules/styles/lineup, builders, DB invariants, API filtering/pagination/chem/meta, CLI (`tests/test_cli.py` ~723 lines).
- **Thin/missing:** no dedicated tests for `fc26/ingest/sbc.py` (337 lines), `objectives.py` (241), `markdown.py`; `tests/test_web.py` thin vs `fc26/api/app.py` (~477 lines).

## Lint / Type-check / CI
- **Python:** none — no ruff/black/flake8/mypy config; pytest is the only gate.
- **Web:** strong — TS `strict`, build runs `tsc -b` (type errors fail build), Vitest 80% coverage thresholds. No ESLint.
- **No CI** — `.github/workflows` absent; all gating is local/manual.

## Error Handling
Typed hierarchy `fc26/errors.py`; CLI is the single conversion point (~20 `except FC26Error` → `typer.Exit(1)`).

## Performance Lens (verification safety net for the milestone)
- **Default pytest is fast & fully offline** (network mocked, sleeps stubbed) — safe to run repeatedly while optimizing.
- **Slow tier is opt-in:** 5 live tests + Playwright e2e (120s webServer timeout, serial).
- **No benchmark/profiling harness:** zero `pytest-benchmark`/`cProfile`/`perf_counter` baselines committed.
- **Implication:** behavioral coverage is strong but **nothing measures latency/throughput**. A perf milestone must add its own profiling/benchmark harness; first targets: `fc26/db.py` full-file load, `/api/cards` filter path, `fc26/chem/engine.py`, `builder/upgrade.py`.
