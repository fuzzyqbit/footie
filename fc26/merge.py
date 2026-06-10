"""Merge rules for upserting cards. See Task 4 for the real rules."""

from .models import Card


def merge_cards(existing: Card, incoming: Card) -> Card:
    return incoming
