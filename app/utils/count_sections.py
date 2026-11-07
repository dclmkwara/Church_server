"""Compatibility helpers for section labels stored in legacy count notes."""

from typing import Any


def legacy_section_label(note: Any) -> str:
    """Read the interim ``Section: <label> |`` prefix without parsing other note text."""
    value = str(note or "")
    if not value.startswith("Section: "):
        return ""
    return value.removeprefix("Section: ").split(" | ", 1)[0].strip()
