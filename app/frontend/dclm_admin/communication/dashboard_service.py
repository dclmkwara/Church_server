from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..backend import BackendClientError, format_scope_display_id
from ..backend.config import get_backend_config
from ..mock_data import STORE
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .church_data_service import ChurchDataService
from .people_service import PeopleService
from .report_service import ReportService
from .request_cache import request_cached
from .ttl_cache import ttl_cached
from .workflow_service import WorkflowService

FULL_BOOTSTRAP_SECTIONS = (
    "summary",
    "member_analytics",
    "population_statistics",
    "worker_analytics",
    "program_comparison",
    "worker_meeting_comparison",
    "newcomer_analytics",
    "church_statistics",
    "user_statistics",
    "attendance_summary",
    "trend_series",
    "scope_snapshot",
)


def _safe_ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100, 1)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _age_group_from_dob(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown"
    try:
        born = datetime.fromisoformat(raw[:10]).date()
    except ValueError:
        return "unknown"
    years = date.today().year - born.year - ((date.today().month, date.today().day) < (born.month, born.day))
    if years >= 18:
        return "adults"
    if years >= 13:
        return "youths"
    return "children"


def _normalize_member(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "member_id": str(row.get("id") or row.get("member_id") or ""),
        "name": str(row.get("name") or "Unknown member"),
        "gender": str(row.get("gender") or ""),
        "status": str(row.get("status") or "active"),
        "date_of_birth": str(row.get("date_of_birth") or ""),
        "location_id": str(row.get("location_id") or ""),
        "path": str(row.get("path") or ""),
    }


def _format_scope_label(path: str) -> str:
    cleaned = (path or "").strip()
    if not cleaned:
        return "Current scope"
    return cleaned.split(".")[-1].upper()


class DashboardService:
    @staticmethod
    def configure_bootstrap_sections(request, sections: tuple[str, ...] | list[str]) -> None:
        state = getattr(request, "state", None)
        if state is None:
            return
        normalized = tuple(dict.fromkeys(str(section) for section in sections if section))
        setattr(state, "_dashboard_bootstrap_sections", normalized or FULL_BOOTSTRAP_SECTIONS)

    @staticmethod
    def requested_bootstrap_sections(request) -> tuple[str, ...]:
        state = getattr(request, "state", None)
        if state is None:
            return FULL_BOOTSTRAP_SECTIONS
        configured = getattr(state, "_dashboard_bootstrap_sections", None)
        if not configured:
            return FULL_BOOTSTRAP_SECTIONS
        return tuple(configured)

    @staticmethod
    async def live_enabled(request) -> bool:
        return get_backend_config().enabled and bool(AuthService.get_access_token(request))

    @staticmethod
    async def use_mock(request) -> bool:
        if get_backend_config().enabled:
            if not AuthService.get_access_token(request):
                raise BackendClientError("Backend session required for dashboard analytics.")
            return False
        return True

    @staticmethod
    async def scope_path(request, ctx) -> str:
        identity = AuthService.get_identity(request)
        if identity and identity.scope_path:
            return identity.scope_path
        return ctx.current_scope_path

    @staticmethod
    async def scope_display_id(request, ctx) -> str:
        return format_scope_display_id(await DashboardService.scope_path(request, ctx))

    @staticmethod
    async def bootstrap_payload(request, ctx) -> dict[str, Any] | None:
        if not await DashboardService.live_enabled(request):
            return None

        scope_path = await DashboardService.scope_path(request, ctx)
        requested_sections = DashboardService.requested_bootstrap_sections(request)
        cache_key = ("dashboard", "bootstrap", scope_path, requested_sections)

        # Layer 1 — request-scoped: free for repeated calls within one request lifecycle.
        # Layer 2 — 60-second TTL: reuse result across multiple HTMX requests
        # (e.g. section panel toggles) without re-hitting the backend each time.
        async def _fetch() -> dict[str, Any] | None:
            try:
                client = async_client(get_api_client())
                access_token = AuthService.get_access_token(request)
                bootstrap_fn = getattr(client, "get_dashboard_bootstrap", None)
                if bootstrap_fn is None:
                    raise BackendClientError("Dashboard bootstrap endpoint is not available.")
                return await bootstrap_fn(
                    access_token,
                    scope_path=scope_path,
                    months=12,
                    sections=list(requested_sections),
                )
            except (AttributeError, BackendClientError):
                return None

        return await request_cached(
            request,
            cache_key,
            lambda: ttl_cached(cache_key, 60.0, _fetch),
        )


    @staticmethod
    async def _bootstrap_key(request, ctx, key: str) -> dict[str, Any] | None:
        payload = await DashboardService.bootstrap_payload(request, ctx)
        if not payload:
            return None
        value = payload.get(key)
        return value if isinstance(value, dict) else None

    @staticmethod
    async def _bootstrap_list(request, ctx, key: str) -> list[dict[str, Any]] | None:
        payload = await DashboardService.bootstrap_payload(request, ctx)
        if not payload:
            return None
        value = payload.get(key)
        return value if isinstance(value, list) else None

    @staticmethod
    async def _bootstrap_rows(request, ctx, key: str) -> list[dict[str, Any]] | None:
        return await DashboardService._bootstrap_list(request, ctx, key)

    @staticmethod
    async def _bootstrap_section(request, ctx, key: str):
        """Return bootstrap payload sub-key as dict or list, or None on miss.

        This is the primary accessor used by all service methods that prefer
        the cached bootstrap payload before falling back to individual API calls.
        """
        payload = await DashboardService.bootstrap_payload(request, ctx)
        if not payload:
            return None
        return payload.get(key)

    @staticmethod
    async def live_location_id(request, ctx) -> str | None:
        """Return the first location_id for location-scoped contexts.

        Request-cached so the 500-location fetch happens at most once per request
        regardless of how many service methods call this during a dashboard load.
        """
        if ctx.current_scope_kind != "location":
            return None

        cache_key = ("live_location_id", ctx.current_scope_path)
        state = getattr(request, "state", None)
        if state is not None:
            bucket = getattr(state, "_dclm_request_cache", None)
            if bucket is None:
                bucket = {}
                setattr(state, "_dclm_request_cache", bucket)
            if cache_key in bucket:
                return bucket[cache_key]
            locations = await maybe_await(PeopleService.list_locations(request, ctx))
            result = locations[0]["location_id"] if locations else None
            bucket[cache_key] = result
            return result

        locations = await maybe_await(PeopleService.list_locations(request, ctx))
        return locations[0]["location_id"] if locations else None


    @staticmethod
    async def _dashboard_snapshot(request, ctx) -> list[dict[str, Any]]:
        if await DashboardService.use_mock(request):
            return STORE.list_church_members(ctx.current_scope_path)
        try:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            rows = await client.list_members(access_token, scope_path=await DashboardService.scope_path(request, ctx))
            return [_normalize_member(row) for row in rows]
        except BackendClientError:
            return STORE.list_church_members(ctx.current_scope_path)

    @staticmethod
    async def church_stats(request, ctx) -> dict[str, Any]:
        payload = await DashboardService._bootstrap_section(request, ctx, "summary")
        if payload:
            pending_items = payload.get("pending_items")
            if pending_items is None:
                pending_items = await WorkflowService.pending_item_count(request, ctx)
            return {
                "members_total": _safe_int(payload.get("members_total")),
                "active_members": _safe_int(payload.get("active_members")) or _safe_int(payload.get("members_total")),
                "workers_total": _safe_int(payload.get("workers_total")),
                "pending_items": _safe_int(pending_items),
                "latest_total": _safe_int(payload.get("latest_total")),
                "locations_reporting": _safe_int(payload.get("locations_reporting")),
                "newcomers_total": _safe_int(payload.get("newcomers_total")),
            }
        report_summary = await maybe_await(ReportService.summary_metrics(request, ctx))
        if await DashboardService.live_enabled(request):
            try:
                client = async_client(get_api_client())
                access_token = AuthService.get_access_token(request)
                payload = await client.get_dashboard_summary(
                    access_token,
                    scope_path=await DashboardService.scope_path(request, ctx),
                    location_id=await DashboardService.live_location_id(request, ctx),
                )
                return {
                    "members_total": _safe_int(payload.get("members_total")),
                    "active_members": _safe_int(payload.get("active_members")) or _safe_int(payload.get("members_total")),
                    "workers_total": _safe_int(payload.get("workers_total")) or report_summary["workers_total"],
                    "pending_items": report_summary["pending_items"],
                    "latest_total": _safe_int(payload.get("latest_total")) or report_summary["latest_total"],
                    "locations_reporting": _safe_int(payload.get("locations_reporting")) or report_summary["locations_reporting"],
                    "newcomers_total": _safe_int(payload.get("newcomers_total")),
                }
            except BackendClientError:
                pass
        members = await DashboardService.list_members(request, ctx)
        records = await ChurchDataService.list_records(request, ctx)
        active_members = [row for row in members if str(row.get("status") or "").lower() == "active"]
        newcomers = [row for row in records if str(row.get("record_type") or "").lower() == "newcomer"]
        return {
            "members_total": len(members),
            "active_members": len(active_members) or len(members),
            "workers_total": report_summary["workers_total"],
            "pending_items": report_summary["pending_items"],
            "latest_total": report_summary["latest_total"],
            "locations_reporting": report_summary["locations_reporting"],
            "newcomers_total": len(newcomers),
        }

    @staticmethod
    async def member_analytics(request, ctx) -> dict[str, Any]:
        payload = await DashboardService._bootstrap_section(request, ctx, "member_analytics")
        if payload:
            total = _safe_int(payload.get("total"))
            male = _safe_int(payload.get("male"))
            female = _safe_int(payload.get("female"))
            adults = _safe_int(payload.get("adults"))
            youths = _safe_int(payload.get("youths"))
            children = _safe_int(payload.get("children"))
            return {
                "total": total,
                "male": male,
                "female": female,
                "male_ratio": _safe_ratio(male, total),
                "female_ratio": _safe_ratio(female, total),
                "adults": adults,
                "youths": youths,
                "children": children,
                "unknown_age": max(total - adults - youths - children, 0),
                "adults_ratio": _safe_ratio(adults, total),
                "youths_ratio": _safe_ratio(youths, total),
                "children_ratio": _safe_ratio(children, total),
                "trend": payload.get("trend") or [],
            }
        if await DashboardService.live_enabled(request):
            try:
                client = async_client(get_api_client())
                access_token = AuthService.get_access_token(request)
                payload = await client.get_dashboard_member_analytics(
                    access_token,
                    scope_path=await DashboardService.scope_path(request, ctx),
                    location_id=await DashboardService.live_location_id(request, ctx),
                )
                total = _safe_int(payload.get("total"))
                male = _safe_int(payload.get("male"))
                female = _safe_int(payload.get("female"))
                adults = _safe_int(payload.get("adults"))
                youths = _safe_int(payload.get("youths"))
                children = _safe_int(payload.get("children"))
                return {
                    "total": total,
                    "male": male,
                    "female": female,
                    "male_ratio": _safe_ratio(male, total),
                    "female_ratio": _safe_ratio(female, total),
                    "adults": adults,
                    "youths": youths,
                    "children": children,
                    "unknown_age": max(total - adults - youths - children, 0),
                    "adults_ratio": _safe_ratio(adults, total),
                    "youths_ratio": _safe_ratio(youths, total),
                    "children_ratio": _safe_ratio(children, total),
                    "trend": payload.get("trend") or [],
                }
            except BackendClientError:
                pass
        rows = await DashboardService.list_members(request, ctx)
        male = sum(1 for row in rows if str(row.get("gender") or "").lower() == "male")
        female = sum(1 for row in rows if str(row.get("gender") or "").lower() == "female")
        adults = youths = children = unknown = 0
        for row in rows:
            bucket = _age_group_from_dob(row.get("date_of_birth"))
            if bucket == "adults":
                adults += 1
            elif bucket == "youths":
                youths += 1
            elif bucket == "children":
                children += 1
            else:
                unknown += 1
        total = len(rows)
        return {
            "total": total,
            "male": male,
            "female": female,
            "male_ratio": _safe_ratio(male, total),
            "female_ratio": _safe_ratio(female, total),
            "adults": adults,
            "youths": youths,
            "children": children,
            "unknown_age": unknown,
            "adults_ratio": _safe_ratio(adults, total),
            "youths_ratio": _safe_ratio(youths, total),
            "children_ratio": _safe_ratio(children, total),
        }

    @staticmethod
    async def member_growth(request, ctx) -> dict[str, Any]:
        payload = await DashboardService._bootstrap_section(request, ctx, "population_statistics")
        if payload is not None:
            return payload
        if await DashboardService.use_mock(request):
            rows = await ChurchDataService.list_counts(request, ctx)
            total = sum(_safe_int(row.get("total")) for row in rows)
            adult_male = sum(_safe_int(row.get("adult_male")) for row in rows)
            adult_female = sum(_safe_int(row.get("adult_female")) for row in rows)
            youth_male = sum(_safe_int(row.get("youth_male")) for row in rows)
            youth_female = sum(_safe_int(row.get("youth_female")) for row in rows)
            boys = sum(_safe_int(row.get("boys")) for row in rows)
            girls = sum(_safe_int(row.get("girls")) for row in rows)
            return {
                "adult_male": adult_male,
                "adult_female": adult_female,
                "youth_male": youth_male,
                "youth_female": youth_female,
                "boys": boys,
                "girls": girls,
                "total": total,
                "percentage_men": _safe_ratio(adult_male + youth_male + boys, total),
                "percentage_women": _safe_ratio(adult_female + youth_female + girls, total),
                "percentage_adults": _safe_ratio(adult_male + adult_female, total),
                "percentage_youths": _safe_ratio(youth_male + youth_female, total),
                "percentage_children": _safe_ratio(boys + girls, total),
            }
        return {}

    @staticmethod
    async def worker_analytics(request, ctx) -> dict[str, Any]:
        payload = await DashboardService._bootstrap_section(request, ctx, "worker_analytics")
        if payload:
            total = _safe_int(payload.get("total"))
            male = _safe_int(payload.get("male"))
            female = _safe_int(payload.get("female"))
            active = _safe_int(payload.get("active"))
            inactive = _safe_int(payload.get("inactive")) + _safe_int(payload.get("suspended"))
            return {
                "total": total,
                "male": male,
                "female": female,
                "male_ratio": _safe_ratio(male, total),
                "female_ratio": _safe_ratio(female, total),
                "active": active,
                "inactive": inactive,
                "pending_verification": _safe_int(payload.get("pending_verification")),
            }
        if await DashboardService.live_enabled(request):
            try:
                client = async_client(get_api_client())
                access_token = AuthService.get_access_token(request)
                payload = await client.get_dashboard_worker_analytics(
                    access_token,
                    scope_path=await DashboardService.scope_path(request, ctx),
                    location_id=await DashboardService.live_location_id(request, ctx),
                )
                total = _safe_int(payload.get("total"))
                male = _safe_int(payload.get("male"))
                female = _safe_int(payload.get("female"))
                active = _safe_int(payload.get("active"))
                inactive = _safe_int(payload.get("inactive")) + _safe_int(payload.get("suspended"))
                return {
                    "total": total,
                    "male": male,
                    "female": female,
                    "male_ratio": _safe_ratio(male, total),
                    "female_ratio": _safe_ratio(female, total),
                    "active": active,
                    "inactive": inactive,
                    "pending_verification": _safe_int(payload.get("pending_verification")),
                }
            except BackendClientError:
                pass
        rows = await PeopleService.list_workers(request, ctx)
        male = sum(1 for row in rows if str(row.get("gender") or "").lower() == "male")
        female = sum(1 for row in rows if str(row.get("gender") or "").lower() == "female")
        active = sum(1 for row in rows if str(row.get("status") or "").lower() == "active")
        total = len(rows)
        return {
            "total": total,
            "male": male,
            "female": female,
            "male_ratio": _safe_ratio(male, total),
            "female_ratio": _safe_ratio(female, total),
            "active": active,
            "inactive": max(total - active, 0),
        }

    @staticmethod
    async def program_comparison(request, ctx, *, limit: int = 3) -> list[dict[str, Any]]:
        payload = await DashboardService._bootstrap_section(request, ctx, "program_comparison")
        if payload:
            return [
                {
                    "label": str(row.get("label") or "Unknown program"),
                    "total": _safe_int(row.get("total")),
                    "records": _safe_int(row.get("records")),
                    "domain": str(row.get("domain") or ""),
                }
                for row in (payload.get("ranking") or [])[:limit]
            ]
        if await DashboardService.live_enabled(request):
            try:
                client = async_client(get_api_client())
                access_token = AuthService.get_access_token(request)
                payload = await client.get_dashboard_program_comparison(
                    access_token,
                    scope_path=await DashboardService.scope_path(request, ctx),
                    location_id=await DashboardService.live_location_id(request, ctx),
                    limit=limit,
                )
                return [
                    {
                        "label": str(row.get("label") or "Unknown program"),
                        "total": _safe_int(row.get("total")),
                        "records": _safe_int(row.get("records")),
                        "domain": str(row.get("domain") or ""),
                    }
                    for row in (payload.get("ranking") or [])
                ]
            except BackendClientError:
                pass
        counts = await ChurchDataService.list_counts(request, ctx)
        events = {row["event_id"]: row for row in await ChurchDataService.list_events(request, ctx)}
        bucket: dict[str, dict[str, Any]] = {}
        for row in counts:
            event = events.get(row["event_id"], {})
            label = str(event.get("program_type_name") or row.get("event_title") or "Unknown program")
            item = bucket.setdefault(label, {"label": label, "total": 0, "records": 0})
            item["total"] += _safe_int(row.get("total"))
            item["records"] += 1
        ranked = sorted(bucket.values(), key=lambda row: (row["total"], row["records"]), reverse=True)
        return ranked[:limit]

    @staticmethod
    async def worker_meeting_comparison(request, ctx) -> dict[str, int]:
        payload = await DashboardService._bootstrap_section(request, ctx, "program_comparison")
        if payload and isinstance(payload, dict):
            special = payload.get("special_programs") or payload
            return {
                "month_events": _safe_int(special.get("month_events")),
                "year_events": _safe_int(special.get("year_events")),
                "month_turnout": _safe_int(special.get("month_turnout")),
                "year_turnout": _safe_int(special.get("year_turnout")),
            }
        if await DashboardService.live_enabled(request):
            try:
                client = async_client(get_api_client())
                access_token = AuthService.get_access_token(request)
                payload = await client.get_dashboard_program_comparison(
                    access_token,
                    scope_path=await DashboardService.scope_path(request, ctx),
                    location_id=await DashboardService.live_location_id(request, ctx),
                    limit=6,
                )
                special = payload.get("special_programs") or {}
                return {
                    "month_events": _safe_int(special.get("month_events")),
                    "year_events": _safe_int(special.get("year_events")),
                    "month_turnout": _safe_int(special.get("month_turnout")),
                    "year_turnout": _safe_int(special.get("year_turnout")),
                }
            except BackendClientError:
                pass
        return {
            "month_events": 0,
            "year_events": 0,
            "month_turnout": 0,
            "year_turnout": 0,
        }

    @staticmethod
    async def top_worker_meetings(request, ctx, *, limit: int = 3) -> list[dict[str, Any]]:
        payload = await DashboardService._bootstrap_section(request, ctx, "worker_meeting_comparison")
        if payload:
            return [
                {
                    "label": str(row.get("label") or "Unknown meeting"),
                    "present": _safe_int(row.get("present")),
                    "late": _safe_int(row.get("late")),
                    "absent": _safe_int(row.get("absent")),
                    "records": _safe_int(row.get("records")),
                }
                for row in (payload.get("ranking") or [])[:limit]
            ]
        if await DashboardService.live_enabled(request):
            try:
                client = async_client(get_api_client())
                access_token = AuthService.get_access_token(request)
                payload = await client.get_dashboard_worker_meeting_comparison(
                    access_token,
                    scope_path=await DashboardService.scope_path(request, ctx),
                    location_id=await DashboardService.live_location_id(request, ctx),
                    limit=limit,
                )
                return [
                    {
                        "label": str(row.get("label") or "Unknown meeting"),
                        "present": _safe_int(row.get("present")),
                        "late": _safe_int(row.get("late")),
                        "absent": _safe_int(row.get("absent")),
                        "records": _safe_int(row.get("records")),
                    }
                    for row in (payload.get("ranking") or [])
                ]
            except BackendClientError:
                pass
        attendance = await ChurchDataService.list_attendance(request, ctx)
        events = {row["event_id"]: row for row in await ChurchDataService.list_events(request, ctx)}
        bucket: dict[str, dict[str, Any]] = {}
        for row in attendance:
            event_id = str(row.get("event_id") or "")
            event = events.get(event_id, {})
            label = str(event.get("program_type_name") or row.get("event_title") or "Unknown meeting")
            item = bucket.setdefault(label, {"label": label, "present": 0, "late": 0, "records": 0})
            status = str(row.get("status") or "").lower()
            if status == "present":
                item["present"] += 1
            if status == "late":
                item["late"] += 1
            item["records"] += 1
        ranked = sorted(bucket.values(), key=lambda row: (row["present"] + row["late"], row["records"]), reverse=True)
        return ranked[:limit]

    @staticmethod
    async def attendance_analytics(request, ctx) -> dict[str, Any]:
        payload = await DashboardService._bootstrap_section(request, ctx, "newcomer_analytics")
        if payload:
            return {
                "newcomers_total": _safe_int(payload.get("newcomers_total")),
                "converts_total": _safe_int(payload.get("converts_total")),
                "male": _safe_int(payload.get("male")),
                "female": _safe_int(payload.get("female")),
                "trend": payload.get("trend") or [],
            }
        if await DashboardService.live_enabled(request):
            try:
                client = async_client(get_api_client())
                access_token = AuthService.get_access_token(request)
                payload = await client.get_dashboard_newcomer_analytics(
                    access_token,
                    scope_path=await DashboardService.scope_path(request, ctx),
                    location_id=await DashboardService.live_location_id(request, ctx),
                    months=12,
                )
                return {
                    "newcomers_total": _safe_int(payload.get("newcomers_total")),
                    "converts_total": _safe_int(payload.get("converts_total")),
                    "male": _safe_int(payload.get("male")),
                    "female": _safe_int(payload.get("female")),
                    "trend": payload.get("trend") or [],
                }
            except BackendClientError:
                pass
        rows = await ChurchDataService.list_records(request, ctx)
        newcomers = [row for row in rows if str(row.get("record_type") or "").lower() == "newcomer"]
        converts = [row for row in rows if str(row.get("record_type") or "").lower() == "convert"]
        male = sum(1 for row in rows if str(row.get("gender") or "").lower() == "male")
        female = sum(1 for row in rows if str(row.get("gender") or "").lower() == "female")
        bucket: dict[str, dict[str, int]] = {}
        for row in rows:
            created = str(row.get("submitted_at") or row.get("created_at") or "")
            period = created[:7] if len(created) >= 7 else "Current"
            item = bucket.setdefault(period, {"newcomers": 0, "converts": 0})
            if str(row.get("record_type") or "").lower() == "convert":
                item["converts"] += 1
            else:
                item["newcomers"] += 1
        trend = [
            {"period": key, "newcomers": value["newcomers"], "converts": value["converts"]}
            for key, value in sorted(bucket.items())
        ]
        return {
            "newcomers_total": len(newcomers),
            "converts_total": len(converts),
            "male": male,
            "female": female,
            "trend": trend,
        }

    @staticmethod
    async def summary(request, ctx) -> list[dict[str, str]]:
        if await DashboardService.use_mock(request):
            return STORE.recent_activity(ctx.current_scope_path)
        inbox = (await WorkflowService.list_inbox(request, ctx))[:6]
        tone_map = {
            "high": "danger",
            "medium": "warning",
            "low": "info",
        }
        rows = []
        for item in inbox:
            rows.append(
                {
                    "message": str(item.get("title") or item.get("subject") or "Pending review item"),
                    "meta": f"{item.get('location') or 'Current scope'} • {item.get('submitted_at') or 'Recently submitted'}",
                    "tone": tone_map.get(str(item.get("priority") or "").lower(), "primary"),
                }
            )
        return rows

    @staticmethod
    async def scope_snapshot(request, ctx) -> list[dict[str, Any]]:
        payload = await DashboardService._bootstrap_rows(request, ctx, "scope_snapshot")
        if payload is not None:
            rows = []
            for row in payload[:5]:
                path = str(row.get("path") or "")
                rows.append(
                    {
                        "label": _format_scope_label(path),
                        "display_id": format_scope_display_id(path),
                        "total": _safe_int(row.get("total")),
                        "counts": _safe_int(row.get("total")),
                        "locations": 0,
                        "pending": 0,
                    }
                )
            return rows
        if await DashboardService.use_mock(request):
            group_by = "location" if ctx.level <= 4 else ("group" if ctx.level <= 6 else "state")
            rows = []
            for row in STORE.scope_breakdown(ctx.current_scope_path, group_by=group_by)[:5]:
                rows.append(
                    {
                        "label": row["label"],
                        "display_id": "",
                        "total": _safe_int(row["total"]),
                        "counts": _safe_int(row["counts"]),
                        "locations": _safe_int(row["locations"]),
                        "pending": _safe_int(row["pending"]),
                    }
                )
            return rows
        rows = (await ReportService.breakdown_rows(request, ctx))[:5]
        normalized = []
        for row in rows:
            path = str(row.get("label") or "")
            normalized.append(
                {
                    "label": _format_scope_label(path),
                    "display_id": format_scope_display_id(path),
                    "total": _safe_int(row.get("counts_total")),
                    "counts": _safe_int(row.get("counts_total")),
                    "locations": 0,
                    "pending": 0,
                }
            )
        return normalized

    @staticmethod
    async def trend_series(request, ctx) -> dict[str, list[tuple[str, int]]]:
        payload = await DashboardService._bootstrap_section(request, ctx, "trend_series")
        if payload:
            return {
                "counts": [(str(row.get("date") or ""), _safe_int(row.get("value"))) for row in (payload.get("counts") or [])],
                "finance": [(str(row.get("date") or ""), _safe_int(row.get("value"))) for row in (payload.get("finance") or [])],
                "attendance": [(str(row.get("date") or ""), _safe_int(row.get("value"))) for row in (payload.get("attendance") or [])],
            }
        return {
            "counts": await ReportService.counts_series(request, ctx),
            "finance": await ReportService.finance_series(request, ctx),
            "attendance": await ReportService.attendance_series(request, ctx),
        }

    @staticmethod
    async def church_statistics_section(request, ctx) -> dict[str, Any]:
        payload = await DashboardService._bootstrap_section(request, ctx, "church_statistics")
        if payload:
            return payload
        if not await DashboardService.live_enabled(request):
            return {
                "total_locations": len(STORE.visible_locations(ctx.current_scope_path)),
                "total_groups": 0,
                "total_regions": 0,
                "total": STORE.counts_summary(ctx.current_scope_path)["latest_total"],
            }
        try:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            return await client.get_church_statistics(access_token)
        except BackendClientError:
            return {}

    @staticmethod
    async def user_statistics_section(request, ctx) -> dict[str, Any]:
        payload = await DashboardService._bootstrap_section(request, ctx, "user_statistics")
        if payload:
            return payload
        if not await DashboardService.live_enabled(request):
            users = STORE.list_users(ctx.current_scope_path)
            active = sum(1 for row in users if row.get("status") == "active")
            return {
                "active_user": active,
                "inactive_user": max(len(users) - active, 0),
                "registered_user": len(users),
            }
        try:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            return await client.get_user_statistics(access_token)
        except BackendClientError:
            return {}

    @staticmethod
    async def attendance_summary_section(request, ctx) -> dict[str, Any]:
        payload = await DashboardService._bootstrap_section(request, ctx, "attendance_summary")
        if payload:
            return {
                "expected": _safe_int(payload.get("expected")),
                "present": _safe_int(payload.get("present")),
                "absent": _safe_int(payload.get("absent")),
                "late": _safe_int(payload.get("late")),
                "excused": _safe_int(payload.get("excused")),
                "rate": _safe_int(payload.get("rate")),
            }
        return await ReportService.attendance_summary(request, ctx)

async def _newcomer_analytics_public(request, ctx) -> dict[str, Any]:
    payload = await DashboardService._bootstrap_section(request, ctx, "newcomer_analytics")
    if payload:
        return {
            "newcomers_total": _safe_int(payload.get("newcomers_total")),
            "converts_total": _safe_int(payload.get("converts_total")),
            "male": _safe_int(payload.get("male")),
            "female": _safe_int(payload.get("female")),
            "trend": payload.get("trend") or [],
        }
    if await DashboardService.live_enabled(request):
        try:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            payload = await client.get_dashboard_newcomer_analytics(
                access_token,
                scope_path=await DashboardService.scope_path(request, ctx),
                location_id=await DashboardService.live_location_id(request, ctx),
                months=12,
            )
            return {
                "newcomers_total": _safe_int(payload.get("newcomers_total")),
                "converts_total": _safe_int(payload.get("converts_total")),
                "male": _safe_int(payload.get("male")),
                "female": _safe_int(payload.get("female")),
                "trend": payload.get("trend") or [],
            }
        except BackendClientError:
            pass
    return await DashboardService.attendance_analytics(request, ctx)


DashboardService.newcomer_analytics = staticmethod(_newcomer_analytics_public)

dual_mode_class(DashboardService)

__all__ = ["DashboardService"]


# ── Public-name aliases ───────────────────────────────────────────────────────
# The route layer calls these canonical names. They delegate to the bootstrap-
# aware implementation methods above.
DashboardService.summary_metrics = staticmethod(DashboardService.church_stats)
DashboardService.member_mix = staticmethod(DashboardService.member_analytics)
DashboardService.population_mix = staticmethod(DashboardService.member_growth)
DashboardService.worker_mix = staticmethod(DashboardService.worker_analytics)
DashboardService.church_statistics = staticmethod(DashboardService.church_statistics_section)
DashboardService.user_statistics = staticmethod(DashboardService.user_statistics_section)
DashboardService.top_programs = staticmethod(DashboardService.program_comparison)
DashboardService.special_program_summary = staticmethod(DashboardService.worker_meeting_comparison)
DashboardService.top_worker_meetings = staticmethod(DashboardService.top_worker_meetings)
DashboardService.recent_activity = staticmethod(DashboardService.summary)
DashboardService.attendance_summary = staticmethod(DashboardService.attendance_summary_section)
DashboardService.list_members = staticmethod(PeopleService.list_members)
DashboardService.list_workers = staticmethod(PeopleService.list_workers)
DashboardService.list_records = staticmethod(ChurchDataService.list_records)
