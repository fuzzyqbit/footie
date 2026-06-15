"""Known/common-name search helpers.

Card data stores legal/birth names (e.g. "Vinícius José de Oliveira Júnior",
"Ronaldo Luís Nazário de Lima"), but players are searched for by the name on the
back of the shirt. Two problems to bridge:

1. Accents — a user typing "vinicius" should match "Vinícius".
2. Nicknames — "R9", "Ronaldinho", "Vini Jr" don't appear in the legal name.
"""

from __future__ import annotations

import unicodedata


def fold(text: str) -> str:
    """Lowercase and strip diacritics, so 'Vinícius' -> 'vinicius'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


# nickname (folded) -> a folded fragment of the legal name as stored in the data
KNOWN_NAMES: dict[str, str] = {
    "r9": "nazario de lima",
    "ronaldo nazario": "nazario de lima",
    "ronaldinho": "de assis moreira",
    "vini jr": "vinicius jose de oliveira",
    "vini": "vinicius jose de oliveira",
    "vinicius jr": "vinicius jose de oliveira",
}


def alias_targets(folded_needle: str) -> list[str]:
    """Legal-name fragments to also match for a folded search term."""
    if not folded_needle:
        return []
    return [
        target
        for alias, target in KNOWN_NAMES.items()
        if folded_needle in alias or alias in folded_needle
    ]
