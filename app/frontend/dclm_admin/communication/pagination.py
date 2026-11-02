from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


async def fetch_all_pages(
    fetch_page: Callable[[int, int], Awaitable[list[dict[str, Any]]]],
    *,
    page_size: int = 500,
) -> list[dict[str, Any]]:
    """Fetch an offset-paginated collection completely, failing on any page error."""
    if page_size < 1:
        raise ValueError("page_size must be positive")
    rows: list[dict[str, Any]] = []
    skip = 0
    while True:
        page = await fetch_page(skip, page_size)
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        skip += len(page)
    return rows
