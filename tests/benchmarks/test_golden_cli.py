"""BENCH-03 — CLI output equivalence via CliRunner.

Goldens stdout of deterministic --json commands over the frozen corpus. Uses
--json (plain output, no Rich tables) and forces NO_COLOR so the golden is
portable regardless of the environment's FORCE_COLOR setting.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from fc26.cli import app

from .corpus import corpus_path, golden_check_text

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("FORCE_COLOR", raising=False)


def _db() -> str:
    return str(corpus_path())


@pytest.mark.golden
def test_golden_cli_list():
    result = runner.invoke(app, ["list", "--sort", "ovr", "--db", _db(), "--json"])
    assert result.exit_code == 0, result.output
    golden_check_text("cli_list.json", result.output)


@pytest.mark.golden
def test_golden_cli_list_pos():
    result = runner.invoke(app, ["list", "--pos", "ST", "--db", _db(), "--json"])
    assert result.exit_code == 0, result.output
    golden_check_text("cli_list_st.json", result.output)


@pytest.mark.golden
def test_golden_cli_show():
    from fc26.db import CardRepository
    card_id = sorted(CardRepository(corpus_path()).find_all(), key=lambda c: c.id)[0].id
    result = runner.invoke(app, ["show", card_id, "--db", _db(), "--json"])
    assert result.exit_code == 0, result.output
    golden_check_text("cli_show.json", result.output)
