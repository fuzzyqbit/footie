"""Unit tests for the in-process cache + batched/durable writes in fc26.db.

These pin the cache behavior added in Phase 2: invalidation, one-parse/one-write
per batch, immutable-snapshot stability, thread-safety, and fsync durability.
The process-global cache is reset before each test for isolation.
"""

from __future__ import annotations

import json
import os
import threading

import pytest

import fc26.db as db
from fc26.db import CardRepository, card_to_dict
from fc26.models import Card, FaceStats


@pytest.fixture(autouse=True)
def _reset_cache():
    CardRepository._reset_cache()
    yield
    CardRepository._reset_cache()


def _card(card_id: str, ovr: int = 85) -> Card:
    return Card(
        id=card_id,
        player_name=f"Player {card_id}",
        version="base",
        ovr=ovr,
        position="ST",
        alt_positions=(),
        face=FaceStats(pac=80, sho=80, pas=80, dri=80, def_=80, phy=80),
        subs=None,
        playstyles=(),
        playstyles_plus=(),
        accelerate=None,
        skill_moves=None,
        weak_foot=None,
        club="Test Club",
        nation="Brazil",
        league="Premier League",
        price=10000,
    )


def _write_raw(path, cards):
    payload = {"schema_version": 1, "cards": [card_to_dict(c) for c in cards]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_invalidation_external_write_reloads(tmp_path):
    db_path = tmp_path / "players.json"
    _write_raw(db_path, [_card("a")])
    repo = CardRepository(db_path)
    assert {c.id for c in repo.find_all()} == {"a"}
    # external writer (e.g. CLI in another process) appends a card
    _write_raw(db_path, [_card("a"), _card("b")])
    assert {c.id for c in repo.find_all()} == {"a", "b"}  # reloaded via mtime/size


def test_invalidation_size_change_reloads_even_if_mtime_pinned(tmp_path):
    db_path = tmp_path / "players.json"
    _write_raw(db_path, [_card("a")])
    repo = CardRepository(db_path)
    repo.find_all()
    st = db_path.stat()
    # rewrite with different size, then pin mtime back to the original
    _write_raw(db_path, [_card("a"), _card("b")])
    os.utime(db_path, (st.st_atime, st.st_mtime))
    assert {c.id for c in repo.find_all()} == {"a", "b"}  # size differs → reload


def test_one_parse_and_one_write_per_batch(tmp_path, monkeypatch):
    db_path = tmp_path / "players.json"
    repo = CardRepository(db_path)

    parses = {"n": 0}
    writes = {"n": 0}
    orig_parse = CardRepository._parse_file
    orig_write = db._atomic_write
    monkeypatch.setattr(CardRepository, "_parse_file",
                        lambda self: (parses.__setitem__("n", parses["n"] + 1) or orig_parse(self)))
    monkeypatch.setattr(db, "_atomic_write",
                        lambda p, c: (writes.__setitem__("n", writes["n"] + 1) or orig_write(p, c)))

    cards = [_card(c) for c in ("a", "b", "c", "d", "e")]
    with repo.batch():
        for c in cards:
            repo.upsert(c)

    assert parses["n"] == 1, "batch should parse the file at most once"
    assert writes["n"] == 1, "batch should write the file exactly once"
    assert {c.id for c in CardRepository(db_path).find_all()} == {"a", "b", "c", "d", "e"}


def test_non_batch_writes_per_upsert(tmp_path, monkeypatch):
    db_path = tmp_path / "players.json"
    repo = CardRepository(db_path)
    writes = {"n": 0}
    orig_write = db._atomic_write
    monkeypatch.setattr(db, "_atomic_write",
                        lambda p, c: (writes.__setitem__("n", writes["n"] + 1) or orig_write(p, c)))
    for c in (_card("a"), _card("b"), _card("c")):
        repo.upsert(c)
    assert writes["n"] == 3, "default (non-batch) upsert writes per card"


def test_find_all_snapshot_is_stable_across_upsert(tmp_path):
    db_path = tmp_path / "players.json"
    repo = CardRepository(db_path)
    repo.upsert(_card("a"))
    snapshot = repo.find_all()
    repo.upsert(_card("b"))
    # the previously returned snapshot is unchanged (immutable)
    assert {c.id for c in snapshot} == {"a"}
    assert {c.id for c in repo.find_all()} == {"a", "b"}


def test_concurrency_smoke(tmp_path):
    db_path = tmp_path / "players.json"
    repo = CardRepository(db_path)
    errors = []

    def writer():
        try:
            with repo.batch():
                for i in range(50):
                    repo.upsert(_card(f"w{i}"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def reader():
        try:
            for _ in range(200):
                repo.find_all()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"concurrent access raised: {errors}"
    assert len(CardRepository(db_path).find_all()) == 50


def test_fsync_called_on_flush(tmp_path, monkeypatch):
    db_path = tmp_path / "players.json"
    repo = CardRepository(db_path)
    calls = {"n": 0}
    orig = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (calls.__setitem__("n", calls["n"] + 1) or orig(fd)))
    repo.upsert(_card("a"))
    assert calls["n"] >= 1, "fsync should be called when flushing to disk"
