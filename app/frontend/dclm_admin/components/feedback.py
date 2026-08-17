from __future__ import annotations

from typing import Any

from fasthtml.common import Div

from faststrap import ModernToast, ModernToastStack


def simple_toast_response(
    content: Any,
    message: str,
    *,
    variant: str = "success",
    title: str | None = None,
    duration: int = 3500,
    toast_id: str = "toast-region",
) -> Any:
    toast = ModernToast(
        title or _toast_title_for_variant(variant),
        message,
        variant=variant,
        duration=duration,
        position="top-end",
        style="glass",
    )
    toast_host = ModernToastStack(
        toast,
        id=toast_id,
        hx_swap_oob=f"outerHTML:#{toast_id}",
    )
    if isinstance(content, (list, tuple)):
        return (*content, toast_host)
    return (content, toast_host)


def toast_stack(
    message: str | None = None,
    *,
    variant: str = "info",
    title: str | None = None,
    duration: int = 3500,
    toast_id: str = "toast-region",
) -> Any:
    if not message:
        return ModernToastStack(id=toast_id)
    return ModernToastStack(
        ModernToast(
            title or _toast_title_for_variant(variant),
            message,
            variant=variant,
            duration=duration,
            position="top-end",
            style="glass",
        ),
        id=toast_id,
    )


def _toast_title_for_variant(variant: str) -> str:
    return {
        "success": "Saved",
        "danger": "Action needed",
        "warning": "Please check",
        "info": "Notice",
        "primary": "Update",
    }.get(variant, "Notice")
