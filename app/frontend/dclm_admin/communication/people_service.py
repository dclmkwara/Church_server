from __future__ import annotations

from time import time
from typing import Any

from ..backend import BackendClientError, format_public_person_code, split_scope_path
from ..backend.config import get_backend_config
from ..mock_data import STORE
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .request_cache import request_cached
from .ttl_cache import ttl_cached


def _sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("name") or "").lower(), str(row.get("location") or "").lower())


def _normalize_worker(row: dict[str, Any]) -> dict[str, Any]:
    created_at = str(row.get("created_at") or "")
    path = str(row.get("path") or "")
    scope_bits = split_scope_path(path)
    state_value = str(row.get("state") or scope_bits.get("state_id") or "")
    public_code = format_public_person_code(state_value, row.get("phone"))
    return {
        "worker_id": str(row.get("worker_id") or ""),
        "user_id": str(row.get("user_id") or ""),
        "public_code": public_code,
        "name": str(row.get("name") or "Unknown worker"),
        "gender": str(row.get("gender") or ""),
        "phone": str(row.get("phone") or ""),
        "unit": str(row.get("unit") or ""),
        "status": str(row.get("status") or "Unknown"),
        "approval_status": str(row.get("approval_status") or ""),
        "location": str(row.get("location_name") or row.get("location_id") or ""),
        "location_id": str(row.get("location_id") or ""),
        "group": str(row.get("group") or ""),
        "region": str(row.get("region") or ""),
        "state": str(row.get("state") or ""),
        "added_date": created_at[:10] if created_at else "",
        "path": path,
        "email": str(row.get("email") or ""),
        "marital_status": str(row.get("marital_status") or ""),
        "occupation": str(row.get("occupation") or ""),
        "address": str(row.get("address") or ""),
    }


def _normalize_user(row: dict[str, Any]) -> dict[str, Any]:
    roles_source = row.get("roles") or []
    roles = [str(role.get("role_name") or "") for role in roles_source if role.get("role_name")]
    role_ids = [int(role["id"]) for role in roles_source if role.get("id") is not None]
    status = "active" if row.get("is_active", False) else "inactive"
    path = str(row.get("path") or "")
    scope_bits = split_scope_path(path)
    state_value = str(row.get("state") or scope_bits.get("state_id") or "")
    return {
        "account_id": str(row.get("user_id") or ""),
        "public_code": format_public_person_code(state_value, row.get("phone")),
        "name": str(row.get("name") or "Unknown user"),
        "phone": str(row.get("phone") or ""),
        "location": str(row.get("location_id") or ""),
        "roles": roles or ["No role assigned"],
        "role_ids": role_ids,
        "approval_status": str(row.get("approval_status") or ""),
        "status": status,
        "worker_id": str(row.get("worker_id") or ""),
        "path": path,
        "email": str(row.get("email") or ""),
        "rejection_reason": str(row.get("rejection_reason") or ""),
    }


def _normalize_role(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row.get("id") or 0),
        "role_name": str(row.get("role_name") or "Unknown role"),
        "description": str(row.get("description") or ""),
        "score_value": row.get("score_value"),
    }


def _normalize_location(row: dict[str, Any]) -> dict[str, Any]:
    path = str(row.get("path") or "")
    location_code = str(row.get("location_code") or (path.split(".")[-1] if path else ""))
    return {
        "location_id": str(row.get("location_id") or ""),
        "location_code": location_code,
        "location_name": str(row.get("location_name") or row.get("location_id") or "Unknown location"),
        "group_id": str(row.get("group_id") or ""),
        "group_code": str(row.get("group_code") or ""),
        "path": path,
        "church_type": str(row.get("church_type") or ""),
    }


def _normalize_location_details(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "location_id": str(row.get("location_id") or ""),
        "location_code": str(row.get("location_code") or ""),
        "location_name": str(row.get("location_name") or row.get("location_id") or ""),
        "church_type": str(row.get("church_type") or ""),
        "group_id": str(row.get("group_id") or ""),
        "group_code": str(row.get("group_code") or ""),
        "group_name": str(row.get("group_name") or ""),
        "region_id": str(row.get("region_id") or ""),
        "region_code": str(row.get("region_code") or ""),
        "region_name": str(row.get("region_name") or ""),
        "state_id": str(row.get("state_id") or ""),
        "state_code": str(row.get("state_code") or ""),
        "state_name": str(row.get("state_name") or ""),
    }


def _fallback_locations(ctx, worker_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for worker in worker_rows or []:
        location_id = str(worker.get("location_id") or "")
        location_name = str(worker.get("location") or location_id or "")
        path = str(worker.get("path") or "")
        if not location_name:
            continue
        key = (location_id, location_name)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "location_id": location_id or location_name,
                "location_name": location_name,
                "group_id": "",
                "path": path,
                "church_type": "",
            }
        )
    scope_path = str(getattr(ctx, "current_scope_path", "") or "")
    scope_bits = split_scope_path(scope_path)
    fallback_name = str(
        scope_bits.get("location_id")
        or scope_bits.get("group_id")
        or scope_bits.get("region_id")
        or scope_bits.get("state_id")
        or getattr(ctx, "current_scope_label", "")
        or ""
    )
    if fallback_name:
        key = (fallback_name, fallback_name)
        if key not in seen:
            rows.append(
                {
                    "location_id": fallback_name,
                    "location_name": fallback_name,
                    "group_id": "",
                    "path": scope_path,
                    "church_type": "",
                }
            )
    return rows


def _normalize_official_appointment(row: dict[str, Any]) -> dict[str, Any]:
    path = str(row.get("path") or "")
    return {
        "appointment_id": str(row.get("appointment_id") or ""),
        "worker_id": str(row.get("worker_id") or ""),
        "worker_name": str(row.get("worker_name") or "Unknown worker"),
        "appointed_role": str(row.get("appointed_role") or ""),
        "assigned_scope": str(row.get("assigned_scope_label") or ""),
        "assigned_scope_path": path,
        "appointed_by": str(row.get("appointed_by_name") or ""),
        "appointed_by_id": str(row.get("appointed_by_id") or ""),
        "appointment_date": str(row.get("appointment_date") or ""),
        "status": str(row.get("status") or "active"),
        "location": str(row.get("location_name") or row.get("location_id") or ""),
        "location_id": str(row.get("location_id") or ""),
        "path": path,
        "note": str(row.get("note") or ""),
        "revoked_note": str(row.get("revoked_note") or ""),
    }


def _normalize_fellowship(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fellowship_id": str(row.get("fellowship_id") or ""),
        "fellowship_code": str(row.get("fellowship_code") or ""),
        "name": str(row.get("fellowship_name") or row.get("fellowship_id") or "Unknown fellowship"),
        "location": str(row.get("location_name") or row.get("location_id") or ""),
        "location_id": str(row.get("location_id") or ""),
        "location_code": str(row.get("location_code") or ""),
        "leader_name": str(row.get("leader_in_charge") or ""),
        "leader_phone": str(row.get("leader_contact") or ""),
        "description": str(row.get("associate_church") or row.get("fellowship_address") or ""),
        "path": str(row.get("path") or ""),
        "formatted_id": str(row.get("formatted_id") or ""),
    }


def _normalize_member(row: dict[str, Any], fellowship_lookup: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    fellowship_lookup = fellowship_lookup or {}
    fellowship_id = str(row.get("fellowship_id") or "")
    fellowship = fellowship_lookup.get(fellowship_id, {})
    member_since = str(row.get("member_since") or row.get("created_at") or "")
    return {
        "member_id": str(row.get("id") or ""),
        "name": str(row.get("name") or "Unknown member"),
        "phone": str(row.get("phone") or ""),
        "gender": str(row.get("gender") or ""),
        "marital_status": str(row.get("marital_status") or ""),
        "location": str(row.get("location_id") or ""),
        "location_id": str(row.get("location_id") or ""),
        "status": str(row.get("status") or "active"),
        "fellowship_id": fellowship_id,
        "fellowship_name": str(fellowship.get("name") or fellowship_id or ""),
        "date_joined": member_since[:10] if member_since else "",
        "address": str(row.get("address") or ""),
        "email": str(row.get("email") or ""),
        "occupation": str(row.get("occupation") or ""),
        "unit": str(row.get("unit") or ""),
        "path": str(row.get("path") or ""),
        "is_worker": bool(row.get("is_worker")),
        "worker_id": str(row.get("worker_id") or ""),
    }


def _with_public_code(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    state_value = str(data.get("state") or split_scope_path(str(data.get("path") or "")).get("state_id") or "")
    data["public_code"] = format_public_person_code(state_value, data.get("phone"))
    return data


class PeopleService:
    @staticmethod
    async def effective_scope_path(request, ctx) -> str:
        identity = AuthService.get_identity(request)
        if identity and identity.scope_path:
            return identity.scope_path
        return ctx.current_scope_path

    @staticmethod
    async def live_enabled(request) -> bool:
        return get_backend_config().enabled and bool(AuthService.get_access_token(request))

    @staticmethod
    async def use_mock(request) -> bool:
        if get_backend_config().enabled:
            if not AuthService.get_access_token(request):
                raise BackendClientError("Backend session required for people data.")
            return False
        return True

    @staticmethod
    async def list_workers(request, ctx, *, search: str = "", status: str = "", approval: str = "") -> list[dict[str, Any]]:
        if await PeopleService.use_mock(request):
            return [_with_public_code(row) for row in STORE.list_workers(ctx.current_scope_path, search=search, status=status, approval=approval)]
        scope_path = await PeopleService.effective_scope_path(request, ctx)

        async def load_rows() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            try:
                source = (
                    await client.list_pending_workers(access_token, scope_path=scope_path)
                    if approval == "pending_verification"
                    else await client.list_workers(access_token, scope_path=scope_path)
                )
            except BackendClientError:
                return []
            return [_normalize_worker(row) for row in source]

        rows = await request_cached(request, ("people", "workers", scope_path, approval), load_rows)
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["name"].lower()
                or term in row["unit"].lower()
                or term in row["location"].lower()
                or term in row["user_id"].lower()
                or term in row.get("public_code", "").lower()
                or term in row["phone"].lower()
            ]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if approval:
            rows = [row for row in rows if row["approval_status"] == approval]
        return sorted(rows, key=_sort_key)

    @staticmethod
    async def list_users(request, worker_id: str) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            row = STORE.get_worker(worker_id)
            return _with_public_code(row) if row else None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        async def load_worker() -> dict[str, Any]:
            row = await maybe_await(ttl_cached(
                ("people", "worker", worker_id),
                60.0,
                lambda: client.get_worker(access_token, worker_id),
            ))
            return _normalize_worker(row)

        return await request_cached(request, ("people", "worker", worker_id), load_worker)

    @staticmethod
    async def list_pending_workers(request, ctx, *, search: str = "", approval: str = "", status: str = "") -> list[dict[str, Any]]:
        if await PeopleService.use_mock(request):
            return [_with_public_code(row) for row in STORE.list_users(ctx.current_scope_path, search=search, approval=approval, status=status)]
        scope_path = await PeopleService.effective_scope_path(request, ctx)

        async def load_rows() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            try:
                rows = await client.list_users(access_token, scope_path=scope_path)
            except BackendClientError:
                return []
            return [_normalize_user(row) for row in rows]

        rows = await request_cached(request, ("people", "users", scope_path), load_rows)
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["name"].lower()
                or term in row["location"].lower()
                or any(term in role.lower() for role in row["roles"])
                or term in row.get("public_code", "").lower()
                or term in row["phone"].lower()
            ]
        if approval:
            rows = [row for row in rows if row["approval_status"] == approval]
        if status:
            rows = [row for row in rows if row["status"] == status]
        return sorted(rows, key=_sort_key)

    @staticmethod
    async def list_pending_users(request, account_id: str) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            row = STORE.get_user(account_id)
            return _with_public_code(row) if row else None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)

        async def load_user() -> dict[str, Any]:
            detail = await maybe_await(ttl_cached(
                ("people", "user", account_id),
                60.0,
                lambda: client.get_user_details(access_token, account_id),
            ))
            row = _normalize_user(detail)
            worker = detail.get("worker") or {}
            row["worker"] = _normalize_worker(worker) if worker else None
            return row

        return await request_cached(request, ("people", "user", account_id), load_user)

    @staticmethod
    async def get_worker(request, ctx, worker_id: str) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            row = STORE.get_user_by_worker(worker_id)
            return _with_public_code(row) if row else None
        worker = await PeopleService.get_worker(request, worker_id)
        if worker and worker.get("user_id"):
            return await PeopleService.get_user(request, str(worker["user_id"]))
        rows = await PeopleService.list_users(request, ctx)
        return next((row for row in rows if row.get("worker_id") == worker_id), None)

    @staticmethod
    async def get_user_details(request, ctx, *, search: str = "", status: str = "", appointed_role: str = "") -> list[dict[str, Any]]:
        if await PeopleService.use_mock(request):
            return STORE.list_official_appointments(
                ctx.current_scope_path,
                search=search,
                status=status,
                appointed_role=appointed_role,
            )
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = await PeopleService.effective_scope_path(request, ctx)

        async def load_rows() -> list[dict[str, Any]]:
            return [
                _normalize_official_appointment(row)
                for row in await client.list_official_appointments(
                    access_token,
                    scope_path=scope_path,
                    search=search or None,
                    status=status or None,
                    appointed_role=appointed_role or None,
                    limit=200,
                )
            ]

        rows = await request_cached(
            request,
            ("people", "official_appointments", scope_path, search, status, appointed_role),
            load_rows,
        )
        return sorted(rows, key=lambda row: (row["appointment_date"], row["worker_name"].lower()), reverse=True)

    @staticmethod
    async def list_members(request, ctx) -> dict[str, int]:
        if await PeopleService.use_mock(request):
            return STORE.official_appointment_summary(ctx.current_scope_path)
        rows = await PeopleService.list_official_appointments(request, ctx)
        scopes = {row["assigned_scope_path"] for row in rows if row.get("assigned_scope_path")}
        return {
            "total": len(rows),
            "active": sum(1 for row in rows if row["status"] == "active"),
            "revoked": sum(1 for row in rows if row["status"] == "revoked"),
            "scopes": len(scopes),
        }

    @staticmethod
    async def list_locations(request, appointment_id: str) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return STORE.get_official_appointment(appointment_id)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        async def load_appointment() -> dict[str, Any]:
            row = await maybe_await(ttl_cached(
                ("people", "official_appointment", appointment_id),
                60.0,
                lambda: client.get_official_appointment(access_token, appointment_id),
            ))
            return _normalize_official_appointment(row)

        return await request_cached(request, ("people", "official_appointment", appointment_id), load_appointment)

    @staticmethod
    async def list_official_appointments(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.create_official_appointment(access_token, payload)
        return _normalize_official_appointment(result)

    @staticmethod
    async def get_official_appointment(request, appointment_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.update_official_appointment(access_token, appointment_id, payload)
        return _normalize_official_appointment(result)

    @staticmethod
    async def approve_user(request, appointment_id: str, note: str | None = None) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.revoke_official_appointment(access_token, appointment_id, note)
        return _normalize_official_appointment(result)

    @staticmethod
    async def reject_user(request, account_id: str, reason: str | None = None) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.deactivate_user(access_token, account_id, reason)
        return _normalize_user(result)

    @staticmethod
    async def deactivate_user(request, account_id: str) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.reactivate_user(access_token, account_id)
        return _normalize_user(result)

    @staticmethod
    async def reactivate_user(request) -> list[dict[str, Any]]:
        if await PeopleService.use_mock(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        rows = await request_cached(
            request,
            ("people", "assignable_roles"),
            lambda: ttl_cached(
                ("people", "assignable_roles"),
                60.0,
                lambda: client.list_available_roles(access_token),
            ),
        )
        return sorted([_normalize_role(row) for row in rows], key=lambda row: str(row["role_name"]).lower())

    @staticmethod
    async def approve_worker(request, ctx) -> list[dict[str, Any]]:
        if await PeopleService.use_mock(request):
            return [
                {
                    "location_id": str(row.get("location_id") or row.get("location") or ""),
                    "location_name": str(row.get("location") or row.get("location_id") or ""),
                    "path": str(row.get("path") or ""),
                    "group_id": "",
                    "church_type": row.get("church_type", ""),
                }
                for row in STORE.visible_locations(ctx.current_scope_path)
            ]
        scope_path = await PeopleService.effective_scope_path(request, ctx)

        async def load_rows() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            try:
                rows = await maybe_await(ttl_cached(
                    ("people", "locations"),
                    60.0,
                    lambda: client.list_locations(access_token),
                ))
                return [_normalize_location(row) for row in rows]
            except BackendClientError:
                return _fallback_locations(ctx, await PeopleService.list_workers(request, ctx))

        rows = await request_cached(request, ("people", "locations"), load_rows)
        filtered = [row for row in rows if not scope_path or row["path"].startswith(scope_path)]
        return sorted(filtered, key=lambda row: (row["location_name"].lower(), row["location_id"]))

    @staticmethod
    async def reject_worker(request, location_id: str) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            visible = next((row for row in STORE.visible_locations("") if row["location_id"] == location_id), None)
            if visible is None:
                return None
            return {
                "location_id": visible["location_id"],
                "location_name": visible["location"],
                "church_type": visible.get("church_type", ""),
                "group_id": "",
                "group_name": visible.get("group", ""),
                "region_id": "",
                "region_name": visible.get("region", ""),
                "state_id": "",
                "state_name": visible.get("state", ""),
            }
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        async def load_details() -> dict[str, Any]:
            row = await maybe_await(ttl_cached(
                ("people", "location_details", location_id),
                120.0,
                lambda: client.get_location_details(access_token, location_id),
            ))
            return _normalize_location_details(row)

        return await request_cached(request, ("people", "location_details", location_id), load_details)

    @staticmethod
    async def create_worker(request, *, location_id: str | None = None) -> list[dict[str, Any]]:
        if await PeopleService.use_mock(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        async def load_rows() -> list[dict[str, Any]]:
            try:
                rows = await maybe_await(ttl_cached(
                    ("people", "fellowships", location_id or ""),
                    45.0,
                    lambda: client.list_fellowships(access_token, location_id=location_id, limit=500),
                ))
                return [_normalize_fellowship(row) for row in rows]
            except BackendClientError:
                return []

        rows = await request_cached(request, ("people", "fellowships", location_id or ""), load_rows)
        return sorted(rows, key=lambda row: (row["name"].lower(), row["location"].lower()))

    @staticmethod
    async def create_user(request, ctx, *, search: str = "", location_id: str = "", status: str = "", fellowship_id: str = "") -> list[dict[str, Any]]:
        if await PeopleService.use_mock(request):
            rows = STORE.list_church_members(
                ctx.current_scope_path,
                search=search,
                location=location_id,
                status=status,
                fellowship_id=fellowship_id,
            )
            return rows
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = await PeopleService.effective_scope_path(request, ctx)
        fellowships = await PeopleService.list_fellowships(request, location_id=location_id or None)
        fellowship_lookup = {row["fellowship_id"]: row for row in fellowships}
        async def load_members() -> list[dict[str, Any]]:
            source = await client.list_members(
                access_token,
                scope_path=scope_path,
                location_id=location_id or None,
                limit=500,
            )
            return [
                _normalize_member(row, fellowship_lookup)
                for row in source
            ]

        rows = await request_cached(request, ("people", "members", scope_path, location_id or ""), load_members)
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["name"].lower()
                or term in row["phone"].lower()
                or term in row["location"].lower()
                or term in row["fellowship_name"].lower()
            ]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if fellowship_id:
            rows = [row for row in rows if row["fellowship_id"] == fellowship_id]
        return sorted(rows, key=lambda row: (row["name"].lower(), row["location"].lower()))

    @staticmethod
    async def create_member(request, ctx) -> dict[str, int]:
        if await PeopleService.use_mock(request):
            return STORE.church_member_summary(ctx.current_scope_path)
        rows = await PeopleService.list_members(request, ctx)
        represented = {row["fellowship_id"] for row in rows if row.get("fellowship_id")}
        return {
            "total": len(rows),
            "active": sum(1 for row in rows if row["status"] == "active"),
            "fellowships": len(represented),
        }

    @staticmethod
    async def list_available_roles(request, member_id: str) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return STORE.get_church_member(member_id)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)

        async def load_member() -> dict[str, Any]:
            row = await maybe_await(ttl_cached(
                ("people", "member", member_id),
                60.0,
                lambda: client.get_member(access_token, member_id),
            ))
            location_id = str(row.get("location_id") or "") or None
            fellowship_lookup = {item["fellowship_id"]: item for item in await PeopleService.list_fellowships(request, location_id=location_id)}
            return _normalize_member(row, fellowship_lookup)

        return await request_cached(request, ("people", "member", member_id), load_member)

    @staticmethod
    async def list_rbac_roles(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        row = await client.create_member(access_token, payload)
        fellowship_lookup = {item["fellowship_id"]: item for item in await PeopleService.list_fellowships(request, location_id=str(row.get("location_id") or "") or None)}
        return _normalize_member(row, fellowship_lookup)

    @staticmethod
    async def get_rbac_role(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.create_worker(access_token, payload)
        return _normalize_worker(result)

    @staticmethod
    async def list_rbac_permissions(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.create_user(access_token, payload)
        return _normalize_user(result)

    @staticmethod
    async def list_rbac_scores(request, account_id: str, role_ids: list[int]) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.assign_roles(access_token, account_id, role_ids)
        return _normalize_user(result)

    @staticmethod
    async def assign_roles(request, account_id: str) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.approve_user(access_token, account_id)
        return _normalize_user(result)

    @staticmethod
    async def create_official_appointment(request, account_id: str, reason: str) -> dict[str, Any] | None:
        if await PeopleService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.reject_user(access_token, account_id, reason)
        return _normalize_user(result)

    @staticmethod
    async def update_official_appointment(request, worker_id: str) -> dict[str, Any] | None:
        if not await PeopleService.live_enabled(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.approve_worker(access_token, worker_id)
        return _normalize_worker(result)

    @staticmethod
    async def revoke_official_appointment(request, worker_id: str, reason: str) -> dict[str, Any] | None:
        if not await PeopleService.live_enabled(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        result = await client.reject_worker(access_token, worker_id, reason)
        return _normalize_worker(result)

async def _list_assignable_roles(request) -> list[dict[str, Any]]:
    if await PeopleService.use_mock(request):
        return []
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    rows = await client.list_available_roles(access_token)
    return sorted([_normalize_role(row) for row in rows], key=lambda row: str(row["role_name"]).lower())


async def _update_user_roles(request, account_id: str, role_ids: list[int]) -> dict[str, Any] | None:
    if await PeopleService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return _normalize_user(await client.assign_roles(access_token, account_id, role_ids))


async def _get_worker_by_id(request, worker_id: str) -> dict[str, Any] | None:
    if await PeopleService.use_mock(request):
        row = STORE.get_worker(worker_id)
        return _with_public_code(row) if row else None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return _normalize_worker(await client.get_worker(access_token, worker_id))


async def _list_user_accounts(request, ctx, *, search: str = "", approval: str = "", status: str = "") -> list[dict[str, Any]]:
    if await PeopleService.use_mock(request):
        return [_with_public_code(row) for row in STORE.list_users(ctx.current_scope_path, search=search, approval=approval, status=status)]
    scope_path = await PeopleService.effective_scope_path(request, ctx)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    rows = [_normalize_user(row) for row in await client.list_users(access_token, scope_path=scope_path)]
    if search:
        term = search.lower().strip()
        rows = [row for row in rows if term in row["name"].lower() or term in row["phone"].lower() or term in row["email"].lower() or any(term in role.lower() for role in row["roles"])]
    if approval:
        rows = [row for row in rows if row["approval_status"] == approval]
    if status:
        rows = [row for row in rows if row["status"] == status]
    return sorted(rows, key=_sort_key)


async def _get_user(request, account_id: str) -> dict[str, Any] | None:
    if await PeopleService.use_mock(request):
        row = STORE.get_user(account_id)
        return _with_public_code(row) if row else None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    detail = await client.get_user_details(access_token, account_id)
    row = _normalize_user(detail)
    worker = detail.get("worker") or {}
    row["worker"] = _normalize_worker(worker) if worker else None
    return row


async def _get_user_by_worker(request, ctx, worker_id: str) -> dict[str, Any] | None:
    if await PeopleService.use_mock(request):
        row = STORE.get_user_by_worker(worker_id)
        return _with_public_code(row) if row else None
    rows = await _list_user_accounts(request, ctx)
    return next((row for row in rows if row.get("worker_id") == worker_id), None)


async def _create_user_account(request, payload: dict[str, Any]) -> dict[str, Any] | None:
    if await PeopleService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return _normalize_user(await client.create_user(access_token, payload))


async def _list_locations(request, ctx) -> list[dict[str, Any]]:
    if await PeopleService.use_mock(request):
        return [
            {
                "location_id": str(row.get("location_id") or row.get("location") or ""),
                "location_name": str(row.get("location") or row.get("location_id") or ""),
                "path": str(row.get("path") or ""),
                "group_id": "",
                "church_type": row.get("church_type", ""),
            }
            for row in STORE.visible_locations(ctx.current_scope_path)
        ]
    scope_path = await PeopleService.effective_scope_path(request, ctx)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    try:
        rows = [_normalize_location(row) for row in await client.list_locations(access_token)]
    except BackendClientError:
        rows = _fallback_locations(ctx, await PeopleService.list_workers(request, ctx))
    filtered = [row for row in rows if not scope_path or row["path"].startswith(scope_path)]
    return sorted(filtered, key=lambda row: (row["location_name"].lower(), row["location_id"]))


async def _list_fellowships(request, *, location_id: str | None = None) -> list[dict[str, Any]]:
    if await PeopleService.use_mock(request):
        return STORE.list_fellowships("", location=location_id or "")
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    try:
        rows = [_normalize_fellowship(row) for row in await client.list_fellowships(access_token, location_id=location_id, limit=500)]
    except BackendClientError:
        return []
    return sorted(rows, key=lambda row: (row["name"].lower(), row["location"].lower()))


async def _list_members(request, ctx, *, search: str = "", location_id: str = "", status: str = "", fellowship_id: str = "") -> list[dict[str, Any]]:
    if await PeopleService.use_mock(request):
        return STORE.list_church_members(ctx.current_scope_path, search=search, location=location_id, status=status, fellowship_id=fellowship_id)
    scope_path = await PeopleService.effective_scope_path(request, ctx)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    fellowships = await _list_fellowships(request, location_id=location_id or None)
    fellowship_lookup = {row["fellowship_id"]: row for row in fellowships}
    rows = [
        _normalize_member(row, fellowship_lookup)
        for row in await client.list_members(access_token, scope_path=scope_path, location_id=location_id or None, limit=500)
    ]
    if search:
        term = search.lower().strip()
        rows = [row for row in rows if term in row["name"].lower() or term in row["phone"].lower() or term in row["location"].lower() or term in row["fellowship_name"].lower()]
    if status:
        rows = [row for row in rows if row["status"] == status]
    if fellowship_id:
        rows = [row for row in rows if row["fellowship_id"] == fellowship_id]
    return sorted(rows, key=lambda row: (row["name"].lower(), row["location"].lower()))


async def _member_summary(request, ctx) -> dict[str, int]:
    if await PeopleService.use_mock(request):
        return STORE.church_member_summary(ctx.current_scope_path)
    rows = await _list_members(request, ctx)
    represented = {row["fellowship_id"] for row in rows if row.get("fellowship_id")}
    return {
        "total": len(rows),
        "active": sum(1 for row in rows if row["status"] == "active"),
        "fellowships": len(represented),
    }


async def _list_official_appointments(request, ctx, *, search: str = "", status: str = "", appointed_role: str = "") -> list[dict[str, Any]]:
    if await PeopleService.use_mock(request):
        return STORE.list_official_appointments(ctx.current_scope_path, search=search, status=status, appointed_role=appointed_role)
    scope_path = await PeopleService.effective_scope_path(request, ctx)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    rows = [
        _normalize_official_appointment(row)
        for row in await client.list_official_appointments(
            access_token,
            scope_path=scope_path,
            search=search or None,
            status=status or None,
            appointed_role=appointed_role or None,
            limit=200,
        )
    ]
    return sorted(rows, key=lambda row: (row["appointment_date"], row["worker_name"].lower()), reverse=True)


async def _official_appointment_summary(request, ctx) -> dict[str, int]:
    if await PeopleService.use_mock(request):
        return STORE.official_appointment_summary(ctx.current_scope_path)
    rows = await _list_official_appointments(request, ctx)
    scopes = {row["assigned_scope_path"] for row in rows if row.get("assigned_scope_path")}
    return {
        "total": len(rows),
        "active": sum(1 for row in rows if row["status"] == "active"),
        "revoked": sum(1 for row in rows if row["status"] == "revoked"),
        "scopes": len(scopes),
    }


async def _get_official_appointment(request, appointment_id: str) -> dict[str, Any] | None:
    if await PeopleService.use_mock(request):
        return STORE.get_official_appointment(appointment_id)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return _normalize_official_appointment(await client.get_official_appointment(access_token, appointment_id))


async def _create_official_appointment(request, payload: dict[str, Any]) -> dict[str, Any] | None:
    if await PeopleService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return _normalize_official_appointment(await client.create_official_appointment(access_token, payload))


async def _update_official_appointment(request, appointment_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if await PeopleService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return _normalize_official_appointment(await client.update_official_appointment(access_token, appointment_id, payload))


async def _revoke_official_appointment(request, appointment_id: str, note: str | None = None) -> dict[str, Any] | None:
    if await PeopleService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return _normalize_official_appointment(await client.revoke_official_appointment(access_token, appointment_id, note))


PeopleService.list_assignable_roles = staticmethod(_list_assignable_roles)
PeopleService.update_user_roles = staticmethod(_update_user_roles)
PeopleService.get_worker = staticmethod(_get_worker_by_id)
PeopleService.list_users = staticmethod(_list_user_accounts)
PeopleService.get_user = staticmethod(_get_user)
PeopleService.get_user_by_worker = staticmethod(_get_user_by_worker)
PeopleService.create_user = staticmethod(_create_user_account)
PeopleService.list_locations = staticmethod(_list_locations)
PeopleService.list_fellowships = staticmethod(_list_fellowships)
PeopleService.list_members = staticmethod(_list_members)
PeopleService.member_summary = staticmethod(_member_summary)
PeopleService.list_official_appointments = staticmethod(_list_official_appointments)
PeopleService.official_appointment_summary = staticmethod(_official_appointment_summary)
PeopleService.get_official_appointment = staticmethod(_get_official_appointment)
PeopleService.create_official_appointment = staticmethod(_create_official_appointment)
PeopleService.update_official_appointment = staticmethod(_update_official_appointment)
PeopleService.revoke_official_appointment = staticmethod(_revoke_official_appointment)


dual_mode_class(PeopleService)

__all__ = ["PeopleService"]
