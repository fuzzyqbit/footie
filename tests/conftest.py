import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run tests that hit the real network",
    )
    parser.addoption(
        "--run-bench",
        action="store_true",
        default=False,
        help="run benchmark + golden-output tests (opt-in; skipped by default)",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-live"):
        skip_live = pytest.mark.skip(reason="live crawl test: pass --run-live to run")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)

    if not config.getoption("--run-bench"):
        skip_bench = pytest.mark.skip(
            reason="benchmark/golden test: pass --run-bench to run"
        )
        for item in items:
            if "benchmark" in item.keywords or "golden" in item.keywords:
                item.add_marker(skip_bench)
