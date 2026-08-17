from __future__ import annotations

from starlette.requests import Request

from ..auth_context import build_context
from ..components.shell import shell_layout
from ..components.ui import empty_state, section_card


PLACEHOLDERS = []


async def _build_placeholder_handler(key: str, title: str, body_text: str):
    async def handler(request: Request):
        ctx = build_context(request)
        body = section_card(
            title,
            "This page is not available yet.",
            empty_state("tools", title, body_text),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key=key,
            title=title,
            subtitle="Page not available yet.",
            primary_action=None,
            content=body,
        )

    return handler


def register_placeholder_routes(app) -> None:
    for path, key, title, body_text in PLACEHOLDERS:
        app.get(path)(_build_placeholder_handler(key, title, body_text))
