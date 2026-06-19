"""Shared helpers for the Phase 1 benchmark + golden-output harness.

Everything here is deterministic and offline:
- ``load_corpus_repo`` materialises a CardRepository from the *frozen* corpus
  (``golden/corpus.json``), never the live ``data/players.json`` which mutates
  on every refresh.
- ``offline_fetch`` builds a ``fetch_html(url) -> str`` backed by an in-memory
  mapping, so scraper code runs with zero network.
- ``golden_check`` / ``golden_check_text`` / ``golden_check_bytes`` compare a
  value against a committed fixture and, when ``REGEN_GOLDEN=1`` is set, rewrite
  the fixture instead of asserting (intentional regeneration).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from fc26.db import CardRepository
from fc26.errors import FetchError

GOLDEN_DIR = Path(__file__).parent / "golden"
CORPUS_FILE = GOLDEN_DIR / "corpus.json"


def corpus_path() -> Path:
    """Path to the frozen corpus (a valid players.json)."""
    return CORPUS_FILE


def load_corpus_repo(tmp_path: Path) -> CardRepository:
    """Copy the frozen corpus into a tmp players.json and return a repo over it.

    The copy keeps tests isolated from each other (upsert benchmarks mutate the
    file) and decoupled from the live DB.
    """
    db = Path(tmp_path) / "players.json"
    db.write_text(CORPUS_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    return CardRepository(db)


def offline_fetch(mapping: dict[str, str]) -> Callable[[str], str]:
    """Return a ``fetch_html(url)`` that serves committed HTML, never the network.

    Unknown URLs raise FetchError (mirrors the real fetch failure type) so a
    test that forgets to stub a page fails loudly instead of hitting the wire.
    """

    def _fetch(url: str) -> str:
        try:
            return mapping[url]
        except KeyError as exc:  # pragma: no cover - defensive
            raise FetchError(f"offline_fetch: no stub for {url!r}") from exc

    return _fetch


class _AsyncStubFetcher:
    """Async analog of ``offline_fetch`` — serves committed HTML, never the wire.

    Usable two ways: passed directly as ``fetcher=`` (it exposes ``async fetch``)
    or as an async context manager (``async with`` returns itself).
    """

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    async def fetch(self, url: str) -> str:
        try:
            return self._mapping[url]
        except KeyError as exc:  # pragma: no cover - defensive
            raise FetchError(f"offline_fetch: no stub for {url!r}") from exc

    async def __aenter__(self) -> "_AsyncStubFetcher":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False


def offline_fetch_async(mapping: dict[str, str]) -> _AsyncStubFetcher:
    """Return an async fetcher stub serving ``mapping``; for ``fetcher=`` args."""
    return _AsyncStubFetcher(mapping)


def async_fetcher_class(mapping: dict[str, str]):
    """Return a drop-in CLASS replacement for ``AsyncFetcher`` (for monkeypatch).

    ``refresh_data_async`` constructs ``AsyncFetcher(concurrency=..., min_interval=...)``
    and uses it as an async context manager, so the stub accepts those kwargs
    (and ignores them) while serving ``mapping``.
    """

    class _StubFetcherClass(_AsyncStubFetcher):
        def __init__(self, *, concurrency: int = 4, min_interval: float = 1.0) -> None:
            super().__init__(mapping)

    return _StubFetcherClass


def _regen() -> bool:
    return os.environ.get("REGEN_GOLDEN") == "1"


def golden_check(name: str, obj: Any) -> None:
    """Assert ``obj`` equals the committed JSON fixture ``golden/<name>``.

    With ``REGEN_GOLDEN=1`` the fixture is (re)written instead of asserted.
    Serialisation is stable (sorted keys, indent=2) so diffs are reviewable.
    """
    path = GOLDEN_DIR / name
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if _regen() or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if not _regen():
            raise AssertionError(
                f"golden {name} did not exist; created it. Re-run to assert."
            )
        return
    expected = path.read_text(encoding="utf-8")
    assert text == expected, f"golden mismatch for {name} (set REGEN_GOLDEN=1 to update)"


def golden_check_text(name: str, text: str) -> None:
    """Assert ``text`` equals the committed text fixture ``golden/<name>``."""
    path = GOLDEN_DIR / name
    if _regen() or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if not _regen():
            raise AssertionError(
                f"golden {name} did not exist; created it. Re-run to assert."
            )
        return
    expected = path.read_text(encoding="utf-8")
    assert text == expected, f"golden mismatch for {name} (set REGEN_GOLDEN=1 to update)"


def golden_check_bytes(name: str, data: bytes) -> None:
    """Assert raw ``data`` equals the committed byte fixture ``golden/<name>``."""
    path = GOLDEN_DIR / name
    if _regen() or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if not _regen():
            raise AssertionError(
                f"golden {name} did not exist; created it. Re-run to assert."
            )
        return
    expected = path.read_bytes()
    assert data == expected, f"golden bytes mismatch for {name} (set REGEN_GOLDEN=1 to update)"
