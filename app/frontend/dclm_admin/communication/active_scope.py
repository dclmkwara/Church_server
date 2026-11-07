from __future__ import annotations

from dataclasses import dataclass, is_dataclass, replace
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from starlette.exceptions import HTTPException

from .auth_service import AuthService


def _path_in_scope(maximum: str, selected: str) -> bool:
    normalized_maximum = _normalize_path(maximum)
    normalized_selected = _normalize_path(selected)
    return bool(normalized_maximum and normalized_selected and (
        normalized_selected == normalized_maximum or normalized_selected.startswith(f"{normalized_maximum}.")
    ))


def _normalize_path(path: str) -> str:
    parts = [part.strip().lower() for part in str(path or "").split(".") if part.strip()]
    return ".".join(parts)


def requested_scope_path(request: Any) -> str:
    query = getattr(request, "query_params", {})
    values = query.getlist("scope_path") if hasattr(query, "getlist") else []
    return str((values[-1] if values else query.get("scope_path")) or "").strip()


@dataclass(frozen=True)
class ActiveScope:
    maximum_path: str
    path: str
    period: str
    include_pending: bool


def resolve_active_scope(request: Any, ctx: Any) -> ActiveScope:
    """Build page context for the selected descendant, bounded by authenticated identity."""
    identity = getattr(getattr(request, "state", None), "identity", None)
    if identity is None and hasattr(request, "query_params"):
        identity = AuthService.get_identity(request)
    extras = getattr(ctx, "query_extras", {}) or {}
    profile = getattr(ctx, "profile", None)
    maximum = str((getattr(identity, "maximum_scope_path", "") if identity else "") or extras.get("home_path") or getattr(profile, "root_path", "") or getattr(ctx, "current_scope_path", "") or "").strip()
    selected = requested_scope_path(request) or str(getattr(ctx, "current_scope_path", "") or maximum)
    if not selected:
        raise HTTPException(status_code=400, detail="No authorized scope is available")
    if selected != maximum and not _path_in_scope(maximum, selected):
        raise HTTPException(status_code=403, detail="Requested scope is outside your allowed scope")

    query = getattr(request, "query_params", {})
    period = str(query.get("period") or "").strip()
    if period not in {"", "recent", "month", "quarter", "year"}:
        raise HTTPException(status_code=400, detail="Invalid reporting period")
    include_pending_raw = str(query.get("include_pending") or "false").strip().lower()
    if include_pending_raw not in {"", "true", "false", "1", "0"}:
        raise HTTPException(status_code=400, detail="Invalid include_pending value")
    include_pending = include_pending_raw in {"true", "1"}
    return ActiveScope(maximum, selected, period or "recent", include_pending)


def active_scope_context(request: Any, ctx: Any) -> Any:
    if not is_dataclass(ctx):
        return ctx
    active = resolve_active_scope(request, ctx)
    query = getattr(request, "query_params", {})
    extras = dict(getattr(ctx, "query_extras", {}) or {})
    extras["scope_path"] = active.path
    extras["scope_kind"] = _scope_kind(active.path)
    extras["scope_label"] = _scope_label(active.path)
    if active.period != "recent" or query.get("period"):
        extras["period"] = active.period
    else:
        extras.pop("period", None)
    if active.include_pending:
        extras["include_pending"] = "true"
    elif query.get("include_pending") is not None:
        extras["include_pending"] = "false"
    else:
        extras.pop("include_pending", None)
    weeks = str(query.get("weeks") or "").strip()
    if weeks in {"4", "8"}:
        extras["weeks"] = weeks
    return replace(
        ctx,
        current_scope_path=active.path,
        current_scope_kind=_scope_kind(active.path),
        current_scope_label=_scope_label(active.path),
        query_extras=extras,
    )


def _scope_kind(path: str) -> str:
    depth = max(len([part for part in path.split(".") if part]) - 1, 0)
    return {0: "global", 1: "nation", 2: "state", 3: "region", 4: "group", 5: "location", 6: "fellowship"}.get(depth, "location")


def _scope_label(path: str) -> str:
    from ..backend import format_scope_display_id

    return format_scope_display_id(path) or path.rsplit(".", 1)[-1]


def scope_link(ctx: Any, path: str, **overrides: str | None) -> str:
    """Create navigation links that retain the selected reporting scope and filters."""
    raw = ctx.url_for(path, **overrides)
    parts = urlsplit(raw)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    extras = getattr(ctx, "query_extras", {}) or {}
    current_path = str(getattr(ctx, "current_scope_path", "") or "")
    if current_path and current_path != extras.get("home_path") and "scope_path" not in overrides:
        params["scope_path"] = current_path
    # Preserve explicit false values too: links must reproduce the exact view
    # represented by the active controls, including include_pending=false.
    for key in ("scope_path", "period", "include_pending", "weeks"):
        value = extras.get(key)
        if value is not None and key not in overrides:
            params[key] = str(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))
