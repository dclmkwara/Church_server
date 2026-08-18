from __future__ import annotations

from typing import Any

from ..backend import BackendClientError, format_scope_display_id
from ..backend.config import get_backend_config
from ..mock_data import STORE, in_scope
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .church_data_service import ChurchDataService
from .people_service import PeopleService
from .request_cache import request_cached
from .ttl_cache import ttl_cached


def _node_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    return (int(row.get("depth") or 0), str(row.get("label") or "").lower())


def _flatten_tree(nodes: list[dict[str, Any]], depth: int = 0) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for node in nodes:
        children = node.get("children") or []
        path = str(node.get("path") or "")
        kind = str(node.get("type") or "")
        label = str(node.get("name") or node.get("id") or "Unknown")
        code = str(node.get("code") or (path.split(".")[-1] if path else ""))
        location_count = 1 if kind == "location" else 0
        fellowship_count = 1 if kind == "fellowship" else 0
        flat.append(
            {
                "entity_id": str(node.get("id") or ""),
                "entity_code": code,
                "label": label,
                "kind": kind,
                "path": path,
                "display_id": format_scope_display_id(path),
                "depth": depth,
                "children_count": len(children),
                "location_count": location_count,
                "fellowship_count": fellowship_count,
                "location_key": str(node.get("id") or "") if kind == "location" else "",
                "location_code": code if kind == "location" else "",
            }
        )
        flat.extend(_flatten_tree(children, depth + 1))
    return flat


def _roll_up(flat_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = {row["path"]: {**row, "member_count": 0, "worker_count": 0} for row in flat_rows}
    for path, row in list(rows.items()):
        descendants = [candidate for candidate in rows.values() if candidate["path"].startswith(f"{path}.")]
        row["location_count"] = row["location_count"] + sum(candidate["location_count"] for candidate in descendants)
        row["fellowship_count"] = row["fellowship_count"] + sum(candidate["fellowship_count"] for candidate in descendants)
        row["children_count"] = len([candidate for candidate in rows.values() if candidate["path"].startswith(f"{path}.") and candidate["depth"] == row["depth"] + 1])
    return sorted(rows.values(), key=_node_sort_key)


async def _profile_or_none(client, access_token: str, location_id: str) -> dict[str, Any] | None:
    try:
        return await client.get_location_profile(access_token, location_id)
    except BackendClientError as exc:
        if "404" in str(exc):
            return None
        raise


class OrganizationService:
    @staticmethod
    async def effective_scope_path(request, ctx) -> str:
        identity = AuthService.get_identity(request)
        if identity and identity.scope_path:
            return identity.scope_path
        return str(getattr(ctx, "current_scope_path", "") or "")

    @staticmethod
    async def live_enabled(request) -> bool:
        return get_backend_config().enabled and bool(AuthService.get_access_token(request))

    @staticmethod
    async def use_mock(request) -> bool:
        if get_backend_config().enabled:
            if not AuthService.get_access_token(request):
                raise BackendClientError("Backend session required for organization data.")
            return False
        return True

    @staticmethod
    async def list_hierarchy_tree(request, ctx) -> list[dict[str, Any]]:
        if await OrganizationService.use_mock(request):
            return [{**row, "display_id": format_scope_display_id(row.get("path"))} for row in STORE.list_hierarchy_tree(ctx.current_scope_path)]
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = await OrganizationService._effective_scope_path(request, ctx)

        async def load_tree_rows() -> list[dict[str, Any]]:
            raw_tree = await client.list_hierarchy_tree(access_token)
            return _roll_up(_flatten_tree(raw_tree))

        rows = await request_cached(
            request,
            ("organization", "hierarchy_tree", scope_path),
            lambda: ttl_cached(
                ("organization", "hierarchy_tree", scope_path),
                45.0,
                load_tree_rows,
            ),
        )
        workers = await maybe_await(PeopleService.list_workers(request, ctx))
        hydrated = [dict(row) for row in rows]
        for row in hydrated:
            row["worker_count"] = sum(1 for worker in workers if str(worker.get("path") or "").startswith(row["path"]))
        return hydrated

    @staticmethod
    async def get_hierarchy_node(request, ctx, node_path: str) -> dict[str, Any] | None:
        rows = await OrganizationService.list_hierarchy_tree(request, ctx) if await OrganizationService.live_enabled(request) else STORE.list_hierarchy_tree(ctx.current_scope_path)
        return next((row for row in rows if row["path"] == node_path), None)

    @staticmethod
    async def list_hierarchy_children(request, ctx, node_path: str) -> list[dict[str, Any]]:
        if await OrganizationService.use_mock(request):
            return STORE.list_hierarchy_children(ctx.current_scope_path, node_path)
        rows = await OrganizationService.list_hierarchy_tree(request, ctx)
        parent = next((row for row in rows if row["path"] == node_path), None)
        if not parent:
            return []
        return [row for row in rows if row["depth"] == parent["depth"] + 1 and row["path"].startswith(f"{node_path}.")]

    @staticmethod
    async def list_locations(request, ctx, *, search: str = "", status: str = "", church_type: str = "") -> list[dict[str, Any]]:
        if await OrganizationService.use_mock(request):
            rows = [
                {**row, "display_id": format_scope_display_id(row.get("path"))}
                for row in STORE.list_location_profiles(ctx.current_scope_path, search="", status=status, church_type=church_type)
            ]
            if search:
                term = search.lower().strip()
                rows = [
                    row for row in rows
                    if term in row["location"].lower()
                    or term in row["address"].lower()
                    or term in row["group"].lower()
                    or term in row["region"].lower()
                    or term in row["state"].lower()
                    or term in row.get("display_id", "").lower()
                ]
            return rows
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = await OrganizationService._effective_scope_path(request, ctx)

        async def load_locations() -> list[dict[str, Any]]:
            all_locations = await maybe_await(
                ttl_cached(
                    ("organization", "all_locations"),
                    45.0,
                    lambda: client.list_locations(access_token),
                )
            )
            return [
                row
                for row in all_locations
                if not scope_path or str(row.get("path") or "").startswith(scope_path)
            ]

        locations = await request_cached(
            request,
            ("organization", "locations", scope_path),
            load_locations,
        )
        details_map: dict[str, dict[str, Any]] = {}
        workers = await PeopleService.list_workers(request, ctx)
        fellowships = [row for row in await OrganizationService.list_hierarchy_tree(request, ctx) if row["kind"] == "fellowship"]
        result = []
        for location in locations:
            location_id = str(location.get("location_id") or "")
            detail = details_map.get(location_id)
            if detail is None:
                detail = await request_cached(
                    request,
                    ("organization", "location_detail", location_id),
                    lambda: ttl_cached(
                        ("organization", "location_detail", location_id),
                        120.0,
                        lambda: client.get_location_details(access_token, location_id),
                    ),
                )
                details_map[location_id] = detail
            profile = await request_cached(
                request,
                ("organization", "location_profile_row", location_id),
                lambda: ttl_cached(
                    ("organization", "location_profile_row", location_id),
                    60.0,
                    lambda: _profile_or_none(client, access_token, location_id),
                ),
            )
            has_profile = "profiled" if profile else "needs_profile"
            row = {
                "location_key": location_id,
                "location_code": str(location.get("location_code") or str(location.get("path") or "").split(".")[-1] or ""),
                "location": str(location.get("location_name") or location_id),
                "address": str(location.get("address") or (profile or {}).get("full_address") or ""),
                "church_type": str(location.get("church_type") or ""),
                "status": has_profile,
                "pastor_name": str((profile or {}).get("founder_name") or (location.get("associate_cord") or "Not set")),
                "assistant_name": str((profile or {}).get("landmark") or "Not set"),
                "phone": str((profile or {}).get("google_maps_url") or ""),
                "group": str(detail.get("group_name") or ""),
                "region": str(detail.get("region_name") or ""),
                "state": str(detail.get("state_name") or ""),
                "path": str(location.get("path") or ""),
                "display_id": format_scope_display_id(str(location.get("path") or "")),
                "worker_count": sum(1 for worker in workers if str(worker.get("location_id") or "") == location_id),
                "fellowship_count": sum(1 for fellowship in fellowships if fellowship.get("path", "").startswith(f"{location.get('path')}.") or fellowship.get("path") == f"{location.get('path')}"),
                "profile": profile,
            }
            result.append(row)
        if search:
            term = search.lower().strip()
            result = [
                row for row in result
                if term in row["location"].lower()
                or term in row["address"].lower()
                or term in row["group"].lower()
                or term in row["region"].lower()
                or term in row["state"].lower()
                or term in row.get("display_id", "").lower()
            ]
        if status:
            result = [row for row in result if row["status"] == status]
        if church_type:
            result = [row for row in result if row["church_type"] == church_type]
        return sorted(result, key=lambda row: (row["location"].lower(), row["location_key"]))

    @staticmethod
    async def get_location_profile(request, ctx, location_key: str) -> dict[str, Any] | None:
        if await OrganizationService.use_mock(request):
            row = STORE.get_location_profile(location_key)
            return {**row, "display_id": format_scope_display_id(row.get("path"))} if row else None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        location = await request_cached(
            request,
            ("organization", "location", location_key),
            lambda: ttl_cached(
                ("organization", "location", location_key),
                120.0,
                lambda: client.get_location(access_token, location_key),
            ),
        )
        detail = await request_cached(
            request,
            ("organization", "location_detail", location_key),
            lambda: ttl_cached(
                ("organization", "location_detail", location_key),
                120.0,
                lambda: client.get_location_details(access_token, location_key),
            ),
        )
        profile = await request_cached(
            request,
            ("organization", "location_profile", location_key),
            lambda: ttl_cached(
                ("organization", "location_profile", location_key),
                60.0,
                lambda: _profile_or_none(client, access_token, location_key) or {},
            ),
        )
        if not location:
            return None

        loc_data = location or {}
        det_data = detail or {}
        prof_data = profile or {}

        is_profiled = bool(prof_data and any(prof_data.get(k) for k in ("founder_name", "history", "full_address", "landmark")))
        return {
            "location_key": location_key,
            "location_code": str(loc_data.get("location_code") or str(loc_data.get("path") or "").split(".")[-1] or ""),
            "location": str(loc_data.get("location_name") or location_key),
            "church_type": str(loc_data.get("church_type") or ""),
            "status": "profiled" if is_profiled else "needs_profile",
            "address": str(loc_data.get("address") or prof_data.get("full_address") or ""),
            "pastor_name": str(prof_data.get("founder_name") or loc_data.get("associate_cord") or "Not set"),
            "assistant_name": str(prof_data.get("landmark") or "Not set"),
            "phone": str(prof_data.get("google_maps_url") or ""),
            "group": str(det_data.get("group_name") or ""),
            "region": str(det_data.get("region_name") or ""),
            "state": str(det_data.get("state_name") or ""),
            "path": str(loc_data.get("path") or ""),
            "display_id": format_scope_display_id(str(loc_data.get("path") or "")),
            "history": str(prof_data.get("history") or ""),
            "founded_date": str(prof_data.get("founded_date") or ""),
            "founder_name": str(prof_data.get("founder_name") or ""),
            "full_address": str(prof_data.get("full_address") or ""),
            "landmark": str(prof_data.get("landmark") or ""),
            "google_maps_url": str(prof_data.get("google_maps_url") or ""),
            "cover_image_url": str(prof_data.get("cover_image_url") or ""),
            "associate_cord": str(loc_data.get("associate_cord") or ""),
            "special_projects": prof_data.get("special_projects") or [],
        }

    @staticmethod
    async def get_location_profile_summary(request, ctx, location_key: str) -> dict[str, Any]:
        if await OrganizationService.use_mock(request):
            return STORE.location_profile_summary(location_key)
        async def load_summary() -> dict[str, Any]:
            profile = await OrganizationService.get_location_profile(request, ctx, location_key)
            if not profile:
                return {"worker_count": 0, "member_count": 0, "fellowship_count": 0, "latest_count": 0}
            workers = await PeopleService.list_workers(request, ctx)
            worker_count = sum(1 for worker in workers if str(worker.get("location_id") or "") == location_key)
            counts = await ChurchDataService.list_counts(request, ctx, location=location_key)
            location_counts = [row for row in counts if str(row.get("location_id") or "") == location_key]
            latest_count = int(location_counts[0].get("total") or 0) if location_counts else 0
            fellowships = [
                row
                for row in await OrganizationService.list_hierarchy_tree(request, ctx)
                if row["kind"] == "fellowship" and row["path"].startswith(f"{profile['path']}.")
            ]
            return {
                "worker_count": worker_count,
                "member_count": 0,
                "fellowship_count": len(fellowships),
                "latest_count": latest_count,
            }

        return await request_cached(
            request,
            ("organization", "location_profile_summary", location_key),
            lambda: ttl_cached(
                ("organization", "location_profile_summary", location_key),
                45.0,
                load_summary,
            ),
        )

    @staticmethod
    async def update_location_profile(request, location_key: str, payload: dict[str, str]) -> dict[str, Any] | None:
        if not await OrganizationService.live_enabled(request):
            return STORE.update_location_profile(location_key, payload)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        location_payload = {
            "location_name": payload.get("location_name") or None,
            "church_type": payload.get("church_type") or None,
            "address": payload.get("address") or None,
            "associate_cord": payload.get("associate_cord") or None,
        }
        location_payload = {key: value for key, value in location_payload.items() if value not in {None, ""}}
        if location_payload:
            await client.update_location(access_token, location_key, location_payload)
        profile_payload = {
            "history": payload.get("history") or None,
            "founded_date": payload.get("founded_date") or None,
            "founder_name": payload.get("founder_name") or None,
            "full_address": payload.get("full_address") or None,
            "landmark": payload.get("landmark") or None,
            "google_maps_url": payload.get("google_maps_url") or None,
            "special_projects": [],
            "cover_image_url": payload.get("cover_image_url") or None,
        }
        await client.upsert_location_profile(access_token, location_key, profile_payload)
        return await OrganizationService.get_location_profile(request, type("Ctx", (), {"current_scope_path": "", "profile": None})(), location_key)

OrganizationService._effective_scope_path = staticmethod(OrganizationService.effective_scope_path)
OrganizationService.list_location_profiles = staticmethod(OrganizationService.list_locations)
OrganizationService.location_profile_summary = staticmethod(OrganizationService.get_location_profile_summary)

dual_mode_class(OrganizationService)

__all__ = ["OrganizationService"]
