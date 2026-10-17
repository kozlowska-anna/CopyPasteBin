from __future__ import annotations

import unicodedata


_BIDI_CONTROLS = {
    "\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c",
    "\u202d", "\u202e", "\u2066", "\u2067", "\u2068", "\u2069",
}


def neutralize_for_terminal(value: str) -> str:
    """Remove terminal controls and bidi overrides from display text."""
    safe: list[str] = []
    for character in value:
        category = unicodedata.category(character)
        if character in _BIDI_CONTROLS or category in {"Cc", "Cf"}:
            safe.append(character if character in {"\n", "\t"} else "�")
        else:
            safe.append(character)
    return "".join(safe)
