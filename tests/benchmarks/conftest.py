"""Fixtures for the Phase 1 benchmark + golden harness."""

from __future__ import annotations

import pytest

from fc26.db import CardRepository

from .corpus import load_corpus_repo


@pytest.fixture
def tmp_repo(tmp_path) -> CardRepository:
    """A CardRepository over a tmp copy of the frozen corpus."""
    return load_corpus_repo(tmp_path)


@pytest.fixture
def corpus_cards(tmp_repo):
    """The frozen corpus as a tuple of Card objects."""
    return tmp_repo.find_all()
