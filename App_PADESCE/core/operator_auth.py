"""Helpers shared by the operator authentication and account-audit flows."""

from __future__ import annotations

import unicodedata


def normalize_login_identifier(value: str | None) -> str:
    """Return the canonical, non-empty representation of a login identifier.

    The function intentionally keeps accents: removing them could merge distinct
    existing accounts. It normalizes Unicode compatibility forms, removes format
    characters (including common zero-width characters), collapses whitespace,
    and applies Unicode-aware case folding.

    It is safe to use for diagnostics immediately. Authentication must not use it
    in production until the collision report has been reviewed.
    """

    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKC", str(value))
    without_format_characters = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    )
    return " ".join(without_format_characters.split()).casefold()
