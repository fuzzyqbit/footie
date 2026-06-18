"""BENCH-03 — refresh / write-path equivalence (the zero-behavior-change gate).

Phase 2 rewrites how cards are cached + persisted. The hard contract it must
keep: the bytes written to players.json, and the cards read back, are
unchanged. This goldens the deterministic write output (db._save id-sorts with
fixed indent/encoding) so any Phase 2 change that alters a single byte fails
loudly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fc26.db import CardRepository, card_from_dict

from .corpus import corpus_path, golden_check, golden_check_bytes


@pytest.mark.golden
def test_golden_refresh_write_bytes(tmp_path):
    """Upsert the whole corpus into an empty repo; the resulting players.json
    bytes are the equivalence contract Phase 2 must preserve."""
    cards = [card_from_dict(c) for c in json.loads(
        corpus_path().read_text(encoding="utf-8"))["cards"]]
    db = Path(tmp_path) / "players.json"
    repo = CardRepository(db)
    for card in cards:
        repo.upsert(card)
    golden_check_bytes("refresh_players.json", db.read_bytes())


@pytest.mark.golden
def test_golden_refresh_readback(tmp_path):
    """The cards read back (ids + a stable structural digest) are unchanged."""
    cards = [card_from_dict(c) for c in json.loads(
        corpus_path().read_text(encoding="utf-8"))["cards"]]
    db = Path(tmp_path) / "players.json"
    repo = CardRepository(db)
    for card in cards:
        repo.upsert(card)
    readback = repo.find_all()
    digest = [
        {"id": c.id, "name": c.player_name, "ovr": c.ovr, "pos": c.position,
         "price": c.price, "league": c.league, "nation": c.nation}
        for c in readback
    ]
    golden_check("refresh_readback.json", digest)
