from __future__ import annotations

import re
from typing import Any

from fasthtml.common import Div

from faststrap import ModernToast, ModernToastStack, ToastPlacement

_VARIANT_TO_INTENT: dict[str, str] = {
    "success": "success",
    "danger": "error",
    "error": "error",
    "warning": "warning",
    "info": "info",
    "primary": "info",
    "secondary": "info",
}

_INTENT_ICONS: dict[str, str] = {
    "success": "check-circle",
    "error": "exclamation-circle",
    "warning": "exclamation-triangle",
    "info": "info-circle",
}

_INTENT_TITLES: dict[str, str] = {
    "success": "Saved",
    "error": "Action Needed",
    "warning": "Please Check",
    "info": "Notice",
}


def _clean_user_message(message: str) -> str:
    """Format raw server outputs and error traces into clear, user-friendly copy."""
    if not message:
        return ""
    text = str(message).strip()

    # If message is an HTTP status error trace (e.g. from httpx / requests)
    if "Client error" in text or "Server error" in text or "for url" in text:
        if "401" in text:
            return "Invalid email or password. Please verify your credentials and try again."
        if "403" in text:
            return "You do not have permission to perform this action with your current role."
        if "404" in text:
            return "The requested record could not be found."
        if "409" in text:
            return "A record with this information already exists in the system."
        if "422" in text:
            return "Validation error: please verify that all required fields are correctly filled."
        if "500" in text or "502" in text or "503" in text:
            return "The server encountered an error processing your request. Please try again later."
        return "The server was unable to complete the request. Please try again."

    # Strip raw dictionary or JSON string prefixes like {"detail": ...}
    detail_match = re.search(r"['\"]detail['\"]\s*:\s*['\"]([^'\"]+)['\"]", text)
    if detail_match:
        return detail_match.group(1)

    return text


def simple_toast_response(
    content: Any,
    message: str,
    *,
    variant: str = "success",
    title: str | None = None,
    duration: int = 3500,
    toast_id: str = "toast-region",
) -> Any:
    intent = _VARIANT_TO_INTENT.get(variant, "info")
    icon = _INTENT_ICONS.get(intent, "info-circle")
    heading = title or _INTENT_TITLES.get(intent, "Notice")
    cleaned_message = _clean_user_message(message)

    toast = ModernToast(
        heading,
        cleaned_message,
        intent=intent,
        icon=icon,
        duration=duration,
        placement=ToastPlacement(position="top-end"),
        visual_style="glass",
        dismissible=True,
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

    intent = _VARIANT_TO_INTENT.get(variant, "info")
    icon = _INTENT_ICONS.get(intent, "info-circle")
    heading = title or _INTENT_TITLES.get(intent, "Notice")
    cleaned_message = _clean_user_message(message)

    return ModernToastStack(
        ModernToast(
            heading,
            cleaned_message,
            intent=intent,
            icon=icon,
            duration=duration,
            placement=ToastPlacement(position="top-end"),
            visual_style="glass",
            dismissible=True,
        ),
        id=toast_id,
    )
