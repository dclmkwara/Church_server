from __future__ import annotations

import inspect
from typing import Any


async def resolve_async_fragments(value: Any) -> Any:
    while inspect.isawaitable(value):
        try:
            value = await value
        except RuntimeError as exc:
            if "already awaited" in str(exc).lower():
                break
            raise
        except Exception:
            break
    if isinstance(value, tuple):
        return tuple([await resolve_async_fragments(item) for item in value])
    if isinstance(value, list):
        return [await resolve_async_fragments(item) for item in value]
    if isinstance(value, dict):
        return {key: await resolve_async_fragments(item) for key, item in value.items()}
    if hasattr(value, "children") and hasattr(value, "attrs"):
        children = getattr(value, "children", ())
        if children:
            value.children = tuple([await resolve_async_fragments(item) for item in children])
        return value
    return value


def install_async_render_resolution() -> None:
    import fasthtml.core as core

    if getattr(core, "_dclm_async_render_resolution", False):
        return
    original_handle = core._handle

    async def _handle_with_resolution(f, *args, **kwargs):
        return await resolve_async_fragments(await original_handle(f, *args, **kwargs))

    core._handle = _handle_with_resolution
    core._dclm_async_render_resolution = True


__all__ = ["install_async_render_resolution", "resolve_async_fragments"]
