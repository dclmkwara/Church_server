"""Helpers for explicit audit actions that do not mutate audited ORM rows."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.audit import AuditLog
from app.models.user import User


def add_audit_record(
    db: AsyncSession,
    *,
    actor: User,
    action: str,
    resource_type: str,
    resource_id: str | None,
    scope_path: str,
    fields: dict[str, Any] | None = None,
) -> AuditLog:
    roles = list(getattr(actor, "roles", None) or [])
    role = max(roles, key=lambda item: getattr(item, "score_value", 0), default=None)
    row = AuditLog(
        user_id=actor.user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        changes={
            "actor_name": str(getattr(actor, "name", "User") or "User"),
            "role_name": str(getattr(role, "role_name", "") or ""),
            "role_score": deps.highest_role_score(actor),
            "scope_path": scope_path,
            "actor_scope_path": deps.effective_scope_path(actor),
            "fields": fields or {},
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(row)
    return row
