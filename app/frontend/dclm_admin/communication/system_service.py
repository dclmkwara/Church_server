from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..backend import BackendClientError
from ..backend.config import get_backend_config
from ..mock_data import STORE
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class
from .auth_service import AuthService
from .request_cache import request_cached
from .ttl_cache import ttl_cached


def _display_time(value: Any) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    cleaned = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw[:16]


def _audit_status(action: str) -> str:
    lowered = action.lower()
    if any(word in lowered for word in ("approve", "assign", "create", "seed", "activate", "update")):
        return "success"
    if any(word in lowered for word in ("reject", "remove", "delete", "deactivate", "suspend")):
        return "warning"
    return "info"


def _normalize_audit_row(row: dict[str, Any]) -> dict[str, Any]:
    resource_type = str(row.get("resource_type") or "system").replace("_", " ")
    resource_id = str(row.get("resource_id") or "").strip()
    action = str(row.get("action") or "system_action").replace("_", " ").title()
    target = resource_type.title() if not resource_id else f"{resource_type.title()} {resource_id}"
    return {
        "audit_id": str(row.get("id") or ""),
        "time": _display_time(row.get("ts_utc")),
        "actor": str(row.get("user_id") or "System"),
        "action": action,
        "target": target,
        "scope_label": str(row.get("ip_address") or "Governance scope"),
        "status": _audit_status(str(row.get("action") or "")),
    }


def _normalize_notification_history_row(row: dict[str, Any], scope_path: str) -> dict[str, Any]:
    return {
        "notification_id": str(row.get("notification_key") or ""),
        "source_id": str(row.get("source_id") or ""),
        "title": str(row.get("title") or "Notification"),
        "body": str(row.get("body") or ""),
        "kind": str(row.get("kind") or ""),
        "priority": str(row.get("priority") or "low"),
        "status": str(row.get("status") or "unread"),
        "time": _display_time(row.get("created_at")),
        "path": scope_path,
        "read_at": _display_time(row.get("read_at")),
    }


def _normalize_app_version(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "version_id": str(row.get("id") or ""),
        "app_name": str(row.get("app_name") or "Client App"),
        "platform": str(row.get("platform") or ""),
        "version_number": str(row.get("version_number") or row.get("version_tag") or ""),
        "version_tag": str(row.get("version_tag") or ""),
        "release_date": str(row.get("release_date") or ""),
        "status": "active" if bool(row.get("is_active")) else "draft",
        "force_update": "Not set",
        "min_os_version": str(row.get("min_os_version") or "Not set"),
        "notes": str(row.get("description") or ""),
        "build": str(row.get("build") or ""),
        "download_url": str(row.get("download_url") or ""),
    }


def _normalize_public_contact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "submission_id": str(row.get("id") or ""),
        "kind": "contact",
        "name": str(row.get("name") or "Unknown"),
        "email": str(row.get("email") or ""),
        "phone": str(row.get("phone") or ""),
        "subject": str(row.get("subject") or ""),
        "message": str(row.get("message") or ""),
        "status": str(row.get("status") or "new"),
        "review_note": str(row.get("review_note") or ""),
        "reviewed_at": _display_time(row.get("reviewed_at")),
        "created_at": _display_time(row.get("created_at")),
    }


def _normalize_public_prayer(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "submission_id": str(row.get("id") or ""),
        "kind": "prayer",
        "name": str(row.get("name") or "Unknown"),
        "email": str(row.get("email") or ""),
        "phone": str(row.get("phone") or ""),
        "request": str(row.get("request") or ""),
        "is_urgent": bool(row.get("is_urgent")),
        "status": str(row.get("status") or "new"),
        "review_note": str(row.get("review_note") or ""),
        "reviewed_at": _display_time(row.get("reviewed_at")),
        "created_at": _display_time(row.get("created_at")),
    }


def _sort_app_version(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("release_date") or ""), str(row.get("platform") or ""), str(row.get("version_number") or ""))


def _normalize_sync_conflict(row: dict[str, Any]) -> dict[str, Any]:
    model = str(row.get("model") or "record")
    kind = str(row.get("kind") or "conflict")
    count = int(row.get("count") or 0)
    location_id = str(row.get("location_id") or "")
    event_id = str(row.get("event_id") or "")
    client_id = str(row.get("client_id") or "")
    detail_bits = []
    if location_id:
        detail_bits.append(f"Location {location_id}")
    if event_id:
        detail_bits.append(f"Event {event_id}")
    if client_id:
        detail_bits.append(f"Client {client_id}")
    if row.get("fund_type"):
        detail_bits.append(str(row.get("fund_type")))
    if row.get("worker_id"):
        detail_bits.append(f"Worker {row.get('worker_id')}")
    detail = " | ".join(detail_bits) if detail_bits else "Scope-visible duplicate records detected."
    title = f"{model.replace('_', ' ').title()} {kind.replace('_', ' ')} conflict"
    merge_allowed = kind == "key" and model in {"counts", "offerings"}
    return {
        "conflict_id": str(row.get("conflict_id") or ""),
        "model": model,
        "kind": kind,
        "title": title,
        "count": count,
        "detail": detail,
        "merge_allowed": merge_allowed,
        "location_id": location_id,
        "event_id": event_id,
        "client_id": client_id,
        "date": str(row.get("date") or ""),
    }


def _normalize_rbac_permission(row: dict[str, Any]) -> dict[str, Any]:
    key = str(row.get("permission") or "")
    family = key.split(":", 1)[0] if ":" in key else "general"
    scope = key.split(":", 1)[1] if ":" in key else "general"
    return {
        "permission_id": str(row.get("id") or ""),
        "key": key,
        "family": family,
        "scope": scope,
        "name": str(row.get("name") or key),
        "description": str(row.get("description") or ""),
    }


def _normalize_rbac_role(row: dict[str, Any]) -> dict[str, Any]:
    permissions = [_normalize_rbac_permission(item) for item in (row.get("permissions") or [])]
    return {
        "role_id": str(row.get("id") or ""),
        "name": str(row.get("role_name") or "Unknown Role"),
        "description": str(row.get("description") or ""),
        "level": int(row.get("score_value") or 0),
        "status": "active",
        "scope": "backend",
        "permission_count": len(permissions),
        "permission_ids": [int(item["permission_id"]) for item in permissions if item["permission_id"].isdigit()],
        "permissions": permissions,
        "score_id": int(row.get("score_id") or 0),
    }


class SystemService:
    LIVE_NOTIFICATION_FILTERS = [
        ("all", "All activity"),
        ("pending_workers", "Workers"),
        ("pending_users", "App users"),
        ("worker_removals", "Removals"),
        ("counts", "Counts"),
        ("offerings", "Finance"),
        ("prayer_requests", "Prayer"),
        ("fellowship_attendance", "Fellowship"),
    ]

    @staticmethod
    async def live_enabled(request) -> bool:
        return get_backend_config().enabled and bool(AuthService.get_access_token(request))

    @staticmethod
    async def use_mock(request) -> bool:
        if get_backend_config().enabled:
            if not AuthService.get_access_token(request):
                raise BackendClientError("Backend session required for system data.")
            return False
        return True

    @staticmethod
    async def _token(request) -> bool:
        return True

    @staticmethod
    async def get_health(request) -> list[tuple[str, str]]:
        if await SystemService.live_enabled(request):
            return SystemService.LIVE_NOTIFICATION_FILTERS
        return [
            ("all", "All kinds"),
            ("health", "Health"),
            ("release", "Release"),
            ("audit", "Audit"),
            ("rbac", "RBAC"),
        ]

    @staticmethod
    async def get_system_metadata(request) -> str:
        return ""

    @staticmethod
    async def get_system_metrics(request, ctx, *, status: str = "all", kind: str = "all") -> list[dict[str, Any]]:
        if await SystemService.use_mock(request):
            return STORE.list_system_notifications(ctx.current_scope_path, status=status, kind=kind)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        identity = AuthService.get_identity(request)
        scope_path = identity.scope_path if identity and identity.scope_path else ctx.current_scope_path
        async def load_notifications() -> list[dict[str, Any]]:
            source = await client.get_notification_history(access_token, kind=kind, limit=200)
            return [
                _normalize_notification_history_row(row, scope_path)
                for row in source
            ]

        rows = await request_cached(request, ("system", "notifications", scope_path, kind), load_notifications)
        if status != "all":
            rows = [row for row in rows if row["status"] == status]
        return rows

    @staticmethod
    async def list_audit_logs(request, ctx) -> dict[str, int]:
        if await SystemService.use_mock(request):
            return STORE.system_notification_summary(ctx.current_scope_path)
        rows = await SystemService.list_notifications(request, ctx)
        return {
            "total": len(rows),
            "unread": sum(1 for row in rows if row.get("status") != "read"),
            "high_priority": sum(1 for row in rows if row["priority"] == "high"),
            "health_items": sum(1 for row in rows if row["kind"] in {"counts", "offerings", "fellowship_attendance"}),
        }

    @staticmethod
    async def seed_database(request, ctx, notification_id: str, *, status: str = "all", kind: str = "all") -> dict[str, Any] | None:
        if await SystemService.use_mock(request):
            row = STORE.get_system_notification(notification_id)
            if row is None or (row["path"] != "global" and not row["path"].startswith(ctx.current_scope_path)):
                return None
            return row
        rows = await SystemService.list_notifications(request, ctx, status=status, kind=kind)
        return next((row for row in rows if row["notification_id"] == notification_id), None)

    @staticmethod
    async def get_sync_changes(request, notification_id: str, *, status: str) -> dict[str, Any] | None:
        if await SystemService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        if status == "read":
            result = await client.mark_notification_read(access_token, notification_id)
        else:
            result = await client.mark_notification_unread(access_token, notification_id)
        return {
            "notification_id": str(result.get("notification_key") or notification_id),
            "status": str(result.get("status") or status),
            "read_at": _display_time(result.get("read_at")),
        }

    @staticmethod
    async def list_sync_conflicts(request) -> dict[str, Any]:
        if await SystemService.use_mock(request):
            return STORE.get_system_health()
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        health = await request_cached(request, ("system", "health"), lambda: ttl_cached(("system", "health"), 15.0, client.get_health))
        metrics = await request_cached(
            request,
            ("system", "metrics"),
            lambda: ttl_cached(("system", "metrics"), 15.0, lambda: client.get_system_metrics(access_token)),
        )
        tables = dict(metrics.get("database", {}).get("tables") or {})
        services = [
            {
                "name": "API",
                "status": str(health.get("status") or "unknown"),
                "note": f"Backend API version {health.get('version') or metrics.get('api', {}).get('version') or 'unknown'} is responding.",
            },
            {
                "name": "Database",
                "status": "healthy" if health.get("database") == "connected" else "warning",
                "note": f"Database connection is {health.get('database') or 'unknown'}.",
            },
            {
                "name": "Counts table",
                "status": "healthy",
                "note": f"{tables.get('counts', 0)} count record(s) currently exist.",
            },
            {
                "name": "Offerings table",
                "status": "healthy",
                "note": f"{tables.get('offerings', 0)} offering record(s) currently exist.",
            },
        ]
        return {
            "status": str(health.get("status") or "unknown"),
            "api_latency_ms": metrics.get("api", {}).get("total_endpoints", 0),
            "queue_wait_seconds": 0,
            "db_connections": tables.get("users", 0),
            "background_jobs": tables.get("workers", 0),
            "services": services,
            "database_status": str(health.get("database") or "unknown"),
            "api_version": str(health.get("version") or metrics.get("api", {}).get("version") or ""),
            "endpoint_count": int(metrics.get("api", {}).get("total_endpoints") or 0),
            "tables": {
                "counts": int(tables.get("counts") or 0),
                "offerings": int(tables.get("offerings") or 0),
                "users": int(tables.get("users") or 0),
                "workers": int(tables.get("workers") or 0),
                "locations": int(tables.get("locations") or 0),
            },
            "timestamp": str(metrics.get("system", {}).get("timestamp") or ""),
        }

    @staticmethod
    async def resolve_sync_conflict(request, ctx) -> dict[str, Any]:
        if await SystemService.use_mock(request):
            notif = STORE.system_notification_summary(ctx.current_scope_path)
            health = STORE.get_system_health()
            return {
                "notification_total": notif["total"],
                "notification_unread": notif["unread"],
                "api_value": f"{health['api_latency_ms']} ms",
                "api_label": "API latency",
                "support_value": str(health["background_jobs"]),
                "support_label": "Open jobs",
            }
        notif = await SystemService.notification_summary(request, ctx)
        health = await SystemService.health_snapshot(request)
        return {
            "notification_total": notif["total"],
            "notification_unread": notif["unread"],
            "api_value": f"v{health['api_version']}" if health.get("api_version") else "Live",
            "api_label": "API version",
            "support_value": str(health.get("endpoint_count") or 0),
            "support_label": "Known endpoints",
        }

    @staticmethod
    async def list_public_contact_submissions(request, ctx, *, search: str = "", status: str = "all") -> list[dict[str, Any]]:
        if await SystemService.use_mock(request):
            return STORE.list_audit_logs(ctx.current_scope_path, search=search, status=status)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        async def load_audit_logs() -> list[dict[str, Any]]:
            source = await client.list_audit_logs(access_token, limit=100)
            return [_normalize_audit_row(row) for row in source]

        rows = await request_cached(request, ("system", "audit_logs"), load_audit_logs)
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["actor"].lower()
                or term in row["action"].lower()
                or term in row["target"].lower()
                or term in row["scope_label"].lower()
            ]
        if status != "all":
            rows = [row for row in rows if row["status"] == status]
        return rows

    @staticmethod
    async def review_public_contact_submission(request, *, platform: str = "", status: str = "all") -> list[dict[str, Any]]:
        if await SystemService.use_mock(request):
            return STORE.list_app_versions(platform=platform, status=status)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        is_active = None
        if status == "active":
            is_active = True
        elif status == "draft":
            is_active = False
        rows = await request_cached(
            request,
            ("system", "app_versions", platform, status),
            lambda: ttl_cached(
                ("system", "app_versions", platform, status),
                30.0,
                lambda: client.list_app_versions(access_token, platform=platform or None, is_active=is_active, limit=200),
            ),
        )
        rows = [_normalize_app_version(row) for row in rows]
        return sorted(rows, key=_sort_app_version, reverse=True)

    @staticmethod
    async def list_public_prayer_submissions(request, version_id: str) -> dict[str, Any] | None:
        if await SystemService.use_mock(request):
            return STORE.get_app_version(version_id)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        return _normalize_app_version(await client.get_app_version(access_token, version_id))

    @staticmethod
    async def review_public_prayer_submission(request, payload: dict[str, str]) -> dict[str, Any] | None:
        if await SystemService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        backend_payload = {
            "app_name": payload.get("app_name") or "DCLM Admin",
            "platform": payload.get("platform") or "Android",
            "version_number": payload.get("version_number") or None,
            "release_date": payload.get("release_date") or None,
            "description": payload.get("notes") or None,
            "min_os_version": payload.get("min_os_version") or None,
            "is_active": payload.get("status", "draft") == "active",
        }
        return _normalize_app_version(await client.create_app_version(access_token, backend_payload))

    @staticmethod
    async def poll_notifications(request, version_id: str) -> dict[str, Any] | None:
        if await SystemService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        current = await client.get_app_version(access_token, version_id)
        siblings = await client.list_app_versions(
            access_token,
            app_name=str(current.get("app_name") or ""),
            platform=str(current.get("platform") or ""),
            limit=200,
        )
        for row in siblings:
            sibling_id = str(row.get("id") or "")
            sibling_active = bool(row.get("is_active"))
            if sibling_id == version_id:
                continue
            if sibling_active:
                await client.update_app_version(access_token, sibling_id, {"is_active": False})
        updated = await client.update_app_version(access_token, version_id, {"is_active": True})
        return _normalize_app_version(updated)

    @staticmethod
    async def get_notification_history(request, action: str) -> dict[str, Any]:
        if await SystemService.use_mock(request):
            return STORE.run_system_utility(action, actor_name="System")
        if action != "seed_programs":
            return {
                "message": "This utility is not available for the current backend connection.",
                "ok": False,
            }
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.seed_database(access_token, confirm=True)
        return {
            "message": str(result.get("message") or "Database seed request completed."),
            "ok": True,
        }

    @staticmethod
    async def mark_notification_read(request) -> str:
        if await SystemService.use_mock(request):
            return "Backend mode required. Sync governance uses the real /sync endpoints and does not run against demo data."
        return ""

    @staticmethod
    async def mark_notification_unread(request) -> list[dict[str, Any]]:
        if await SystemService.use_mock(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        payload = await request_cached(request, ("system", "sync_conflicts"), lambda: client.list_sync_conflicts(access_token))
        rows = [_normalize_sync_conflict(row) for row in (payload.get("conflicts") or [])]
        return sorted(rows, key=lambda row: (row["model"], row["kind"], row["conflict_id"]))

    @staticmethod
    async def list_notifications(request) -> dict[str, int]:
        rows = await SystemService.list_sync_conflicts(request)
        return {
            "total": len(rows),
            "client_id": sum(1 for row in rows if row["kind"] == "client_id"),
            "key": sum(1 for row in rows if row["kind"] == "key"),
            "merge_ready": sum(1 for row in rows if row["merge_allowed"]),
        }

    @staticmethod
    async def list_app_versions(request, conflict_id: str) -> dict[str, Any] | None:
        rows = await SystemService.list_sync_conflicts(request)
        return next((row for row in rows if row["conflict_id"] == conflict_id), None)

    @staticmethod
    async def get_app_version(request, *, since: str = "") -> dict[str, Any]:
        if await SystemService.use_mock(request):
            return {"since": "", "counts": 0, "offerings": 0, "records": 0, "total_changes": 0}
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        snapshot_since = since or (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0).isoformat()
        payload = await client.get_sync_changes(access_token, since=snapshot_since)
        return {
            "since": str(payload.get("since") or snapshot_since),
            "counts": len(payload.get("counts") or []),
            "offerings": len(payload.get("offerings") or []),
            "records": len(payload.get("records") or []),
            "total_changes": int(payload.get("total_changes") or 0),
        }

    @staticmethod
    async def create_app_version(request, conflict_id: str, *, resolution: str) -> dict[str, Any] | None:
        if await SystemService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        return await client.resolve_sync_conflict(access_token, conflict_id, resolution)

    @staticmethod
    async def update_app_version(request, *, status: str = "all", search: str = "") -> list[dict[str, Any]]:
        if not await SystemService.live_enabled(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        rows = await request_cached(
            request,
            ("system", "public_contacts", status, search),
            lambda: client.list_public_contact_submissions(
                access_token,
                status=None if status == "all" else status,
                search=search or None,
                limit=200,
            ),
        )
        return [_normalize_public_contact(row) for row in rows]

    @staticmethod
    async def list_media_galleries(request, *, status: str = "all", urgent: str = "all", search: str = "") -> list[dict[str, Any]]:
        if not await SystemService.live_enabled(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        urgent_value = None
        if urgent == "urgent":
            urgent_value = True
        elif urgent == "regular":
            urgent_value = False
        rows = await request_cached(
            request,
            ("system", "public_prayers", status, urgent, search),
            lambda: client.list_public_prayer_submissions(
                access_token,
                status=None if status == "all" else status,
                urgent=urgent_value,
                search=search or None,
                limit=200,
            ),
        )
        return [_normalize_public_prayer(row) for row in rows]

    @staticmethod
    async def get_media_gallery(request, submission_id: str, *, status: str, review_note: str = "") -> dict[str, Any] | None:
        if not await SystemService.live_enabled(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        row = await client.review_public_contact_submission(
            access_token,
            submission_id,
            {"status": status, "review_note": review_note or None},
        )
        return _normalize_public_contact(row)

    @staticmethod
    async def create_media_gallery(request, submission_id: str, *, status: str, review_note: str = "") -> dict[str, Any] | None:
        if not await SystemService.live_enabled(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        row = await client.review_public_prayer_submission(
            access_token,
            submission_id,
            {"status": status, "review_note": review_note or None},
        )
        return _normalize_public_prayer(row)

    @staticmethod
    async def delete_media_gallery(request) -> list[dict[str, Any]]:
        if not await SystemService.live_enabled(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        rows = await request_cached(
            request,
            ("system", "rbac_roles"),
            lambda: ttl_cached(
                ("system", "rbac_roles"),
                60.0,
                lambda: client.list_rbac_roles(access_token, limit=200),
            ),
        )
        rows = [_normalize_rbac_role(row) for row in rows]
        return sorted(rows, key=lambda row: (-row["level"], row["name"].lower()))

    @staticmethod
    async def list_media_items(request, *, family: str = "all", search: str = "") -> list[dict[str, Any]]:
        if not await SystemService.live_enabled(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        rows = await request_cached(
            request,
            ("system", "rbac_permissions"),
            lambda: ttl_cached(
                ("system", "rbac_permissions"),
                60.0,
                lambda: client.list_rbac_permissions(access_token, limit=500),
            ),
        )
        rows = [_normalize_rbac_permission(row) for row in rows]
        if family != "all":
            rows = [row for row in rows if row["family"] == family]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["key"].lower()
                or term in row["family"].lower()
                or term in row["name"].lower()
                or term in row["description"].lower()
            ]
        return sorted(rows, key=lambda row: (row["family"], row["key"]))

    @staticmethod
    async def create_media_item(request, role_id: str) -> dict[str, Any] | None:
        if not await SystemService.live_enabled(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        return _normalize_rbac_role(await client.get_rbac_role(access_token, role_id))

    @staticmethod
    async def delete_media_item(request, permission_id: str) -> dict[str, Any] | None:
        if not await SystemService.live_enabled(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        return _normalize_rbac_permission(await client.get_rbac_permission(access_token, permission_id))

    @staticmethod
    async def list_rbac_roles_system(request, role_id: str, *, description: str, permission_ids: list[int]) -> dict[str, Any] | None:
        if not await SystemService.live_enabled(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        current = await SystemService.get_rbac_role(request, role_id)
        if current is None:
            return None
        payload = {
            "role_name": current["name"],
            "description": description,
            "score_id": current["score_id"],
            "permission_ids": permission_ids,
        }
        updated = await client.update_rbac_role(access_token, role_id, payload)
        return _normalize_rbac_role(updated)

async def _system_health_snapshot(request) -> dict[str, Any]:
    if await SystemService.use_mock(request):
        return STORE.get_system_health()
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    health = await client.get_health()
    metrics = await client.get_system_metrics(access_token)
    tables = dict(metrics.get("database", {}).get("tables") or {})
    return {
        "status": str(health.get("status") or metrics.get("system", {}).get("status") or "unknown"),
        "database_status": str(health.get("database") or "unknown"),
        "api_version": str(health.get("version") or metrics.get("api", {}).get("version") or ""),
        "endpoint_count": int(metrics.get("api", {}).get("total_endpoints") or 0),
        "tables": {
            "counts": int(tables.get("counts") or 0),
            "offerings": int(tables.get("offerings") or 0),
            "users": int(tables.get("users") or 0),
            "workers": int(tables.get("workers") or 0),
            "locations": int(tables.get("locations") or 0),
        },
        "timestamp": str(metrics.get("system", {}).get("timestamp") or ""),
    }


async def _system_list_notifications(request, ctx, *, status: str = "all", kind: str = "all") -> list[dict[str, Any]]:
    if await SystemService.use_mock(request):
        return STORE.list_system_notifications(ctx.current_scope_path, status=status, kind=kind)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    identity = AuthService.get_identity(request)
    scope_path = identity.scope_path if identity and identity.scope_path else str(getattr(ctx, "current_scope_path", "") or "")
    rows = [_normalize_notification_history_row(row, scope_path) for row in await client.get_notification_history(access_token, kind=kind, limit=200)]
    if status != "all":
        rows = [row for row in rows if row["status"] == status]
    return rows


async def _system_notification_summary(request, ctx) -> dict[str, int]:
    if await SystemService.use_mock(request):
        return STORE.system_notification_summary(ctx.current_scope_path)
    rows = await _system_list_notifications(request, ctx)
    return {
        "total": len(rows),
        "unread": sum(1 for row in rows if row.get("status") != "read"),
        "high_priority": sum(1 for row in rows if row.get("priority") == "high"),
        "health_items": sum(1 for row in rows if row.get("kind") in {"counts", "offerings", "fellowship_attendance"}),
    }


async def _system_set_notification_status(request, notification_id: str, *, status: str) -> dict[str, Any] | None:
    if await SystemService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    result = (
        await client.mark_notification_read(access_token, notification_id)
        if status == "read"
        else await client.mark_notification_unread(access_token, notification_id)
    )
    return {
        "notification_id": str(result.get("notification_key") or notification_id),
        "status": str(result.get("status") or status),
        "read_at": _display_time(result.get("read_at")),
    }


async def _system_list_app_versions(request, *, platform: str = "", status: str = "all") -> list[dict[str, Any]]:
    if await SystemService.use_mock(request):
        return STORE.list_app_versions(platform=platform, status=status)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    is_active = True if status == "active" else False if status == "draft" else None
    rows = [
        _normalize_app_version(row)
        for row in await client.list_app_versions(access_token, platform=platform or None, is_active=is_active, limit=200)
    ]
    return sorted(rows, key=_sort_app_version, reverse=True)


async def _system_get_app_version(request, version_id: str) -> dict[str, Any] | None:
    if await SystemService.use_mock(request):
        return STORE.get_app_version(version_id)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return _normalize_app_version(await client.get_app_version(access_token, version_id))


async def _system_activate_app_version(request, version_id: str) -> dict[str, Any] | None:
    if await SystemService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    current = await client.get_app_version(access_token, version_id)
    siblings = await client.list_app_versions(
        access_token,
        app_name=str(current.get("app_name") or ""),
        platform=str(current.get("platform") or ""),
        limit=200,
    )
    for row in siblings:
        sibling_id = str(row.get("id") or "")
        if sibling_id != version_id and bool(row.get("is_active")):
            await client.update_app_version(access_token, sibling_id, {"is_active": False})
    return _normalize_app_version(await client.update_app_version(access_token, version_id, {"is_active": True}))


async def _system_list_public_contacts(request, *, status: str = "all", search: str = "") -> list[dict[str, Any]]:
    if not await SystemService.live_enabled(request):
        return []
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return [
        _normalize_public_contact(row)
        for row in await client.list_public_contact_submissions(
            access_token,
            status=None if status == "all" else status,
            search=search or None,
            limit=200,
        )
    ]


async def _system_review_public_prayer(request, submission_id: str, *, status: str, review_note: str = "") -> dict[str, Any] | None:
    if not await SystemService.live_enabled(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    row = await client.review_public_prayer_submission(access_token, submission_id, {"status": status, "review_note": review_note or None})
    return _normalize_public_prayer(row)


async def _system_list_public_prayers(request, *, status: str = "all", urgent: str = "all", search: str = "") -> list[dict[str, Any]]:
    if not await SystemService.live_enabled(request):
        return []
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    urgent_value = True if urgent == "urgent" else False if urgent == "regular" else None
    return [
        _normalize_public_prayer(row)
        for row in await client.list_public_prayer_submissions(
            access_token,
            status=None if status == "all" else status,
            urgent=urgent_value,
            search=search or None,
            limit=200,
        )
    ]


async def _system_list_sync_conflicts(request) -> list[dict[str, Any]]:
    if await SystemService.use_mock(request):
        return []
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    payload = await client.list_sync_conflicts(access_token)
    rows = [_normalize_sync_conflict(row) for row in (payload.get("conflicts") or [])]
    return sorted(rows, key=lambda row: (row["model"], row["kind"], row["conflict_id"]))


async def _system_sync_conflict_summary(request) -> dict[str, int]:
    rows = await _system_list_sync_conflicts(request)
    return {
        "total": len(rows),
        "client_id": sum(1 for row in rows if row["kind"] == "client_id"),
        "key": sum(1 for row in rows if row["kind"] == "key"),
        "merge_ready": sum(1 for row in rows if row["merge_allowed"]),
    }


async def _system_sync_changes_snapshot(request, *, since: str = "") -> dict[str, Any]:
    if await SystemService.use_mock(request):
        return {"since": "", "counts": 0, "offerings": 0, "records": 0, "total_changes": 0}
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    snapshot_since = since or (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0).isoformat()
    payload = await client.get_sync_changes(access_token, since=snapshot_since)
    return {
        "since": str(payload.get("since") or snapshot_since),
        "counts": len(payload.get("counts") or []),
        "offerings": len(payload.get("offerings") or []),
        "records": len(payload.get("records") or []),
        "total_changes": int(payload.get("total_changes") or 0),
    }


async def _system_resolve_sync_conflict(request, conflict_id: str, *, resolution: str) -> dict[str, Any] | None:
    if await SystemService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return await client.resolve_sync_conflict(access_token, conflict_id, resolution)


async def _system_overview_summary(request, ctx) -> dict[str, Any]:
    if await SystemService.use_mock(request):
        notif = STORE.system_notification_summary(ctx.current_scope_path)
        health = STORE.get_system_health()
        return {
            "notification_total": notif["total"],
            "notification_unread": notif["unread"],
            "api_value": f"{health['api_latency_ms']} ms",
            "api_label": "API latency",
            "support_value": str(health["background_jobs"]),
            "support_label": "Open jobs",
        }
    notif = await SystemService.notification_summary(request, ctx)
    health = await SystemService.health_snapshot(request)
    return {
        "notification_total": notif["total"],
        "notification_unread": notif["unread"],
        "api_value": f"v{health['api_version']}" if health.get("api_version") else "Live",
        "api_label": "API version",
        "support_value": str(health.get("endpoint_count") or 0),
        "support_label": "Known endpoints",
    }


async def _system_supports_notification_status(request) -> bool:
    return not await SystemService.live_enabled(request)


async def _system_notification_kind_filters(request) -> list[tuple[str, str]]:
    return await SystemService.get_health(request)


async def _system_notification_mode_note(request) -> str:
    if await SystemService.live_enabled(request):
        return "Latest backend notifications are shown here."
    return "Backend connection required to manage notification state."


async def _system_get_notification(request, ctx, notification_id: str, *, status: str = "all", kind: str = "all") -> dict[str, Any] | None:
    return await SystemService.seed_database(request, ctx, notification_id, status=status, kind=kind)


async def _system_list_audit_logs(request, ctx, *, search: str = "", status: str = "all") -> list[dict[str, Any]]:
    return await SystemService.list_public_contact_submissions(request, ctx, search=search, status=status)


async def _system_review_public_contact(request, submission_id: str, *, status: str, review_note: str = "") -> dict[str, Any] | None:
    if not await SystemService.live_enabled(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    row = await client.review_public_contact_submission(access_token, submission_id, {"status": status, "review_note": review_note or None})
    return _normalize_public_contact(row)


async def _system_get_sync_conflict(request, conflict_id: str) -> dict[str, Any] | None:
    rows = await SystemService.list_sync_conflicts(request)
    return next((row for row in rows if row["conflict_id"] == conflict_id), None)


async def _system_run_utility(request, action: str) -> dict[str, Any]:
    return {"action": action, "status": "queued" if await SystemService.live_enabled(request) else "mock"}


async def _system_sync_mode_note(request) -> str:
    if await SystemService.live_enabled(request):
        return "Live sync governance is connected to the backend conflict feed."
    return "Backend mode required to review live sync conflicts and change snapshots."


SystemService.overview_summary = staticmethod(_system_overview_summary)
SystemService.supports_notification_status = staticmethod(_system_supports_notification_status)
SystemService.notification_kind_filters = staticmethod(_system_notification_kind_filters)
SystemService.notification_mode_note = staticmethod(_system_notification_mode_note)
SystemService.get_notification = staticmethod(_system_get_notification)
SystemService.health_snapshot = staticmethod(_system_health_snapshot)
SystemService.list_notifications = staticmethod(_system_list_notifications)
SystemService.notification_summary = staticmethod(_system_notification_summary)
SystemService.set_notification_status = staticmethod(_system_set_notification_status)
SystemService.list_app_versions = staticmethod(_system_list_app_versions)
SystemService.get_app_version = staticmethod(_system_get_app_version)
SystemService.activate_app_version = staticmethod(_system_activate_app_version)
SystemService.list_audit_logs = staticmethod(_system_list_audit_logs)
SystemService.list_public_contacts = staticmethod(_system_list_public_contacts)
SystemService.review_public_contact = staticmethod(_system_review_public_contact)
SystemService.list_public_prayers = staticmethod(_system_list_public_prayers)
SystemService.review_public_prayer = staticmethod(_system_review_public_prayer)
SystemService.list_sync_conflicts = staticmethod(_system_list_sync_conflicts)
SystemService.get_sync_conflict = staticmethod(_system_get_sync_conflict)
SystemService.sync_conflict_summary = staticmethod(_system_sync_conflict_summary)
SystemService.sync_changes_snapshot = staticmethod(_system_sync_changes_snapshot)
SystemService.sync_mode_note = staticmethod(_system_sync_mode_note)
SystemService.resolve_sync_conflict = staticmethod(_system_resolve_sync_conflict)
SystemService.list_rbac_roles = staticmethod(SystemService.delete_media_gallery)
SystemService.list_rbac_permissions = staticmethod(SystemService.list_media_items)
SystemService.get_rbac_role = staticmethod(SystemService.create_media_item)
SystemService.get_rbac_permission = staticmethod(SystemService.delete_media_item)
SystemService.update_rbac_role = staticmethod(SystemService.list_rbac_roles_system)
SystemService.run_utility = staticmethod(_system_run_utility)


dual_mode_class(SystemService)

__all__ = ["SystemService"]
