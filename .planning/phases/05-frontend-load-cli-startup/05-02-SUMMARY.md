# 05-02 SUMMARY — CLI startup

**Status:** ✅ complete · **Wave:** 1 · **Requirements:** CLI-01

## What was built
- New `fc26/ingest/constants.py` (light, no heavy imports) holding `DEFAULT_MIN_OVR`/`DEFAULT_INTERVAL_HOURS`. `refresh.py` re-exports them (`from .constants import …` + `__all__`) so `from fc26.ingest.refresh import DEFAULT_*` in `app.py` + tests keeps working. cli.py now imports the defaults from `.ingest.constants` (cheap) instead of `.ingest.refresh` (which transitively pulls selectolax/httpx).
- `fc26/cli.py`: slimmed the module-top imports to the light set (`typer`, `rich`, `asyncio`, `json`, `Path`, `.db`, `.errors`, `.models`, `.ingest.constants`). Deferred the whole scrape+builder+chem graph + `httpx` into the command bodies that use them (add/sync/seed/enrich/expand/images/refresh/refresh-objectives/refresh-sbcs/upgrade/build/plan/chem/advise/boost). `serve` already deferred uvicorn/create_app. Dropped dead imports (`time`, `fetch_html`, sync `jittered_sleep`/`refresh_data`/`enrich_cards`/`expand_cards`/`upgrade_card_images`). `console = Console(width=200)` left at top (out of scope).
- `tests/test_cli_startup.py` (Wave 0): subprocess asserts `import fc26.cli` does NOT pull `selectolax`/`httpx`.
- `tests/test_cli.py`: retargeted the 12 monkeypatches from `fc26.cli.<sym>` to the source modules (`fc26.ingest.futgg.fetch_futgg_card`, `fc26.ingest.fcratings.fetch_top100`, `fc26.ingest.enrich.enrich_cards_async`, `fc26.ingest.expand.expand_cards_async`) — required because those symbols are now local command-body imports. Stubs + assertions unchanged.

## Before / after (`import fc26.cli`)
| | Before | After |
|---|--------|-------|
| `selectolax` loaded | **yes** | **no** |
| `httpx` loaded | **yes** | **no** |
| total modules in `sys.modules` | **416** | **273** (−143, −34%) |

`fc26 --help` / `search` / `show` / `list` no longer import the HTML parser or HTTP client (or the builder/chem graph) — they load only when a scrape/build command actually runs.

## Verification
- `import fc26.cli` → selectolax False, httpx False, 273 modules (subprocess test green).
- `tests/test_cli.py` (62) + `tests/test_cli_startup.py` (1) → **63 passed**.
- `pytest -m golden --run-bench` → **10 passed** — cli_list/cli_show byte-identical.
- Full suite → **365 passed, 29 skipped** (was 364 + 1 startup test); `from fc26.api.app import create_app` clean (DEFAULT_* re-export intact).

## Decisions
- Deferred imports placed as the first body line(s) after each docstring; imported locally in each using command (clarity over DRY for lazy imports).
- Behavior byte-identical: deferral changes *when* modules load, not *what* commands do (golden + test_cli confirm).
