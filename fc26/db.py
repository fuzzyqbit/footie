"""JSON card repository with an in-process cache and atomic, durable writes.

The card pool lives in one JSON file. To avoid re-parsing the whole file on
every read and rewriting it on every card, each resolved file path has a
process-global cache entry (parsed snapshot + id index), shared across the many
short-lived ``CardRepository`` instances the API/CLI construct. Reads serve from
RAM and reload only when the file's mtime/size changes; writes mutate the cache
and flush to disk (immediately by default, or once per ``batch()`` context).

On-disk format and all public behavior are unchanged: ``_save`` still id-sorts
and serializes identically (byte-for-byte), ``upsert`` still validates + merges,
and ``find_all`` still returns an immutable snapshot tuple.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .errors import DatabaseError
from .known_names import alias_targets, fold
from .merge import merge_cards
from .models import Card, FaceStats, SubStats, validate_card

SCHEMA_VERSION = 1


def card_to_dict(card: Card) -> dict[str, Any]:
    data = asdict(card)
    data["alt_positions"] = list(card.alt_positions)
    data["playstyles"] = list(card.playstyles)
    data["playstyles_plus"] = list(card.playstyles_plus)
    return data


def card_from_dict(data: dict[str, Any]) -> Card:
    try:
        payload = dict(data)
        payload["face"] = FaceStats(**payload.get("face") or {})
        subs = payload.get("subs")
        payload["subs"] = SubStats(**subs) if subs else None
        payload["alt_positions"] = tuple(payload.get("alt_positions") or ())
        payload["playstyles"] = tuple(payload.get("playstyles") or ())
        payload["playstyles_plus"] = tuple(payload.get("playstyles_plus") or ())
        return Card(**payload)
    except TypeError as exc:
        raise DatabaseError(f"malformed card record: {exc}") from exc


class _CacheEntry:
    """Shared, process-global cache for one resolved file path."""

    __slots__ = ("lock", "cards", "by_id", "mtime", "size", "dirty")

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.cards: tuple[Card, ...] | None = None   # immutable snapshot
        self.by_id: dict[str, Card] = {}             # index into the snapshot
        self.mtime: float | None = None
        self.size: int | None = None
        self.dirty: bool = False                     # in-memory writes not yet flushed


_CACHES: dict[Path, _CacheEntry] = {}
_CACHES_LOCK = threading.Lock()


def _entry_for(path: Path) -> _CacheEntry:
    key = path.resolve()
    with _CACHES_LOCK:
        entry = _CACHES.get(key)
        if entry is None:
            entry = _CACHES[key] = _CacheEntry()
        return entry


class CardRepository:
    """Load/save/search/upsert cards in a JSON file, backed by a shared cache."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._entry = _entry_for(self._path)
        self._in_batch = False

    @classmethod
    def _reset_cache(cls) -> None:
        """Clear the process-global cache (test hook)."""
        with _CACHES_LOCK:
            _CACHES.clear()

    def _stat_or_none(self) -> os.stat_result | None:
        try:
            return self._path.stat()
        except OSError:
            return None

    def _parse_file(self) -> tuple[Card, ...]:
        """The only json.loads of the file. Preserves original error semantics."""
        if not self._path.exists():
            return ()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            version = data.get("schema_version")
            if version != SCHEMA_VERSION:
                raise DatabaseError(
                    f"{self._path}: schema_version {version!r}, expected {SCHEMA_VERSION}"
                )
            return tuple(card_from_dict(item) for item in data["cards"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise DatabaseError(f"cannot read {self._path}: {exc}") from exc

    def _ensure_loaded(self) -> None:
        e = self._entry
        with e.lock:
            if e.dirty:
                return                       # in-memory writes are the source of truth
            st = self._stat_or_none()
            fresh = (
                e.cards is not None
                and st is not None
                and st.st_mtime == e.mtime
                and st.st_size == e.size
            )
            if fresh:
                return
            cards = self._parse_file()
            e.cards = cards
            e.by_id = {c.id: c for c in cards}
            if st is not None:
                e.mtime, e.size = st.st_mtime, st.st_size
            else:
                e.mtime, e.size = None, None

    def find_all(self) -> tuple[Card, ...]:
        self._ensure_loaded()
        return self._entry.cards or ()

    def find_by_id(self, card_id: str) -> Card | None:
        self._ensure_loaded()
        return self._entry.by_id.get(card_id)

    def search(self, text: str) -> tuple[Card, ...]:
        self._ensure_loaded()
        needle = fold(text)
        extras = alias_targets(needle)
        result = []
        for card in self._entry.cards or ():
            name = fold(card.player_name)
            if (
                needle in name
                or needle in fold(card.club or "")
                or needle in fold(card.version)
                or any(t in name for t in extras)
            ):
                result.append(card)
        return tuple(result)

    def upsert(self, card: Card) -> Card:
        validate_card(card)
        e = self._entry
        with e.lock:
            self._ensure_loaded()
            existing = e.by_id.get(card.id)
            if existing is not None:
                card = merge_cards(existing, card)
                # merge_cards output is valid by construction: both inputs were
                # validated on their own upserts and _pick never invents values.
            new_by_id = dict(e.by_id)
            new_by_id[card.id] = card
            e.by_id = new_by_id
            # keep id-sort so the on-disk byte order is unchanged
            e.cards = tuple(sorted(new_by_id.values(), key=lambda c: c.id))
            e.dirty = True
            if not self._in_batch:
                self._flush_locked()
        return card

    def flush(self) -> None:
        e = self._entry
        with e.lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        e = self._entry
        if not e.dirty:
            return
        self._save(e.cards or ())
        st = self._stat_or_none()   # re-stat AFTER write so our own bytes don't trigger a reload
        if st is not None:
            e.mtime, e.size = st.st_mtime, st.st_size
        e.dirty = False

    @contextlib.contextmanager
    def batch(self):
        """Defer disk writes until the context exits (one write instead of N).

        Flushes on normal exit and again in ``finally`` so a partial scrape that
        raises still persists what it wrote.
        """
        self._in_batch = True
        try:
            yield self
            self.flush()
        finally:
            self._in_batch = False
            self.flush()

    def _save(self, cards: tuple[Card, ...]) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "cards": [card_to_dict(card) for card in sorted(cards, key=lambda c: c.id)],
        }
        _atomic_write(self._path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())          # flush file contents to disk
        os.replace(tmp_name, path)
        _fsync_dir(path.parent)                 # flush the rename itself (POSIX)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _fsync_dir(directory: Path) -> None:
    """fsync a directory so a rename survives power loss. No-op where unsupported."""
    if not hasattr(os, "O_DIRECTORY"):
        return                                  # not available on Windows
    try:
        dir_fd = os.open(directory, os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)
