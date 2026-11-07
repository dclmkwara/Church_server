from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ..backend import BackendClientError
from ..backend.config import get_backend_config
from ..mock_data import STORE
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .count_aggregation import summarize_count_submissions
from .people_service import PeopleService
from .pagination import fetch_all_pages
from .request_cache import request_cached
from .ttl_cache import invalidate_ttl_prefix
from app.utils.count_sections import legacy_section_label


PAYMENT_METHOD_LABELS = {
    "cash": "Cash",
    "bank_transfer": "Bank Transfer",
    "mobile_money": "Mobile Money",
    "check": "Check",
}

RECORD_STATUS_TO_UI = {
    "pending": "follow_up_pending",
    "contacted": "contacted",
    "followed_up": "integrated",
}

UI_RECORD_STATUS_TO_BACKEND = {value: key for key, value in RECORD_STATUS_TO_UI.items()}


def _event_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("date") or ""), str(row.get("title") or ""))


def _invalidate_finance_views() -> None:
    invalidate_ttl_prefix(("reports",))
    invalidate_ttl_prefix(("dashboard", "bootstrap"))


def _normalize_event(row: dict[str, Any]) -> dict[str, Any]:
    program_type = row.get("program_type") or {}
    return {
        "event_id": str(row.get("id") or ""),
        "title": str(row.get("title") or "Untitled event"),
        "date": str(row.get("date") or ""),
        "path": str(row.get("path") or ""),
        "program_type_id": str(row.get("program_type_id") or ""),
        "program_type_name": str(program_type.get("name") or ""),
        "program_type_slug": str(program_type.get("slug") or ""),
    }


def _normalize_count(row: dict[str, Any], *, event_map: dict[str, dict[str, Any]], location_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    event = event_map.get(str(row.get("event_id") or ""))
    location = location_map.get(str(row.get("location_id") or ""))
    return {
        "count_id": str(row.get("id") or ""),
        "submitted_at": str(row.get("created_at") or ""),
        "event_id": str(row.get("event_id") or ""),
        "event_title": event["title"] if event else str(row.get("program_type") or row.get("event_id") or "Unknown program"),
        "date": str((event or {}).get("date") or str(row.get("date") or str(row.get("created_at") or "")[:10])[:10]),
        "program_type": str(row.get("program_type") or (event or {}).get("program_type_name") or ""),
        "program_level": str(row.get("program_level") or ""),
        "program_scope_path": str(row.get("program_scope_path") or ""),
        "location": (location or {}).get("location_name") or str(row.get("location_id") or ""),
        "location_id": str(row.get("location_id") or ""),
        "adult_male": int(row.get("adult_male") or 0),
        "adult_female": int(row.get("adult_female") or 0),
        "youth_male": int(row.get("youth_male") or 0),
        "youth_female": int(row.get("youth_female") or 0),
        "boys": int(row.get("boys") or 0),
        "girls": int(row.get("girls") or 0),
        "total": int(row.get("total") or 0),
        "status": str(row.get("status") or "pending").lower(),
        "supersedes_id": str(row.get("supersedes_id") or ""),
        "rejection_reason": str(row.get("rejection_reason") or ""),
        "rejected_by_id": str(row.get("rejected_by_id") or ""),
        "rejected_at": str(row.get("rejected_at") or ""),
        "approved_by_id": str(row.get("approved_by_id") or ""),
        "approved_at": str(row.get("approved_at") or ""),
        "auto_accepted": bool(row.get("auto_accepted")),
        "submitted_by": str(row.get("entered_by_id") or "Recorded in backend"),
        "note": str(row.get("note") or ""),
        "usher_section": str(row.get("usher_section") or _section_from_note(row.get("note"))),
        "assignment_id": str(row.get("assignment_id") or ""),
        "client_id": str(row.get("client_id") or ""),
        "source_role": str(row.get("source_role") or "regular"),
        "campaign_code": str(row.get("campaign_code") or ""),
        "submission_channel": str(row.get("submission_channel") or ""),
    }


def _section_from_note(value: Any) -> str:
    """Read the interim note prefix until B5 adds real count section columns."""
    return legacy_section_label(value)


def _normalize_offering(row: dict[str, Any], *, event_map: dict[str, dict[str, Any]], location_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    event = event_map.get(str(row.get("event_id") or ""))
    location = location_map.get(str(row.get("location_id") or ""))
    amount = row.get("amount")
    return {
        "entry_id": str(row.get("id") or ""),
        "event_id": str(row.get("event_id") or ""),
        "event_title": event["title"] if event else str(row.get("event_id") or "Unknown event"),
        "date": str((event or {}).get("date") or str(row.get("created_at") or "")[:10]),
        "location": (location or {}).get("location_name") or str(row.get("location_id") or ""),
        "location_id": str(row.get("location_id") or ""),
        "amount": float(amount if isinstance(amount, Decimal) else (amount or 0)),
        "fund_type": str(row.get("fund_type") or "offering"),
        "method": PAYMENT_METHOD_LABELS.get(str(row.get("payment_method") or ""), str(row.get("payment_method") or "").replace("_", " ").title()),
        "submitted_by": str(row.get("entered_by_id") or "Recorded in backend"),
        "notes": str(row.get("note") or ""),
        "status": str(row.get("status") or ""),
        "entry_date": str(row.get("date") or "")[:10],
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
        "entered_by_id": str(row.get("entered_by_id") or ""),
        "reviewed_by_id": str(row.get("reviewed_by_id") or ""),
        "reviewed_at": str(row.get("reviewed_at") or ""),
        "review_note": str(row.get("review_note") or ""),
    }


def _normalize_record(row: dict[str, Any], *, event_map: dict[str, dict[str, Any]], location_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    event = event_map.get(str(row.get("event_id") or ""))
    location = location_map.get(str(row.get("location_id") or ""))
    details = row.get("details") or {}
    created_at = str(row.get("created_at") or "")
    return {
        "record_id": str(row.get("id") or ""),
        "name": str(row.get("name") or "Unknown person"),
        "phone": str(row.get("phone") or ""),
        "record_type": str(row.get("record_type") or "newcomer"),
        "gender": str(row.get("gender") or ""),
        "service": event["title"] if event else str(row.get("event_id") or "Unknown event"),
        "event_id": str(row.get("event_id") or ""),
        "location": (location or {}).get("location_name") or str(row.get("location_id") or ""),
        "location_id": str(row.get("location_id") or ""),
        "status": RECORD_STATUS_TO_UI.get(str(row.get("status") or ""), str(row.get("status") or "follow_up_pending")),
        "date": str(details.get("follow_up_date") or created_at[:10]),
        "assigned_to": str(details.get("assigned_to") or details.get("follow_up_worker") or "Follow-up team"),
        "notes": str(row.get("note") or ""),
        "assignment_id": str(row.get("assignment_id") or ""),
        "source_role": str(row.get("source_role") or "regular"),
        "campaign_code": str(row.get("campaign_code") or ""),
        "submission_channel": str(row.get("submission_channel") or ""),
    }


def _normalize_attendance(row: dict[str, Any], *, event_map: dict[str, dict[str, Any]], location_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    event = event_map.get(str(row.get("event_id") or ""))
    location = location_map.get(str(row.get("location_id") or ""))
    created_at = str(row.get("created_at") or "")
    return {
        "attendance_id": str(row.get("id") or ""),
        "worker_id": str(row.get("worker_id") or ""),
        "worker_name": str(row.get("worker_name") or "Unknown worker"),
        "unit": str(row.get("worker_unit") or "General"),
        "event_id": str(row.get("event_id") or ""),
        "event_title": event["title"] if event else str(row.get("event_id") or "Unknown event"),
        "date": str((event or {}).get("date") or created_at[:10]),
        "location": (location or {}).get("location_name") or str(row.get("location_id") or ""),
        "location_id": str(row.get("location_id") or ""),
        "status": str(row.get("status") or "present"),
        "reason": str(row.get("reason") or row.get("note") or ""),
        "recorded_by": str(row.get("entered_by_id") or "Recorded in backend"),
    }


class ChurchDataService:
    @staticmethod
    async def live_enabled(request) -> bool:
        return get_backend_config().enabled and bool(AuthService.get_access_token(request))

    @staticmethod
    async def use_mock(request) -> bool:
        if get_backend_config().enabled:
            if not AuthService.get_access_token(request):
                raise BackendClientError("Backend session required for church data.")
            return False
        return True

    @staticmethod
    async def effective_scope_path(request, ctx) -> str:
        return await PeopleService.effective_scope_path(request, ctx)

    @staticmethod
    async def list_events(request, ctx) -> list[dict[str, Any]]:
        scope_path = await ChurchDataService._scope_path(request, ctx)
        if await ChurchDataService.use_mock(request):
            return [
                {"event_id": row["event_id"], "title": row["title"], "date": row.get("date", ""), "path": row.get("path", "")}
                for row in STORE.list_program_events(scope_path)
            ]

        async def load_rows() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            try:
                source = await fetch_all_pages(lambda skip, limit: client.list_program_events(access_token, scope_path=scope_path, skip=skip, limit=limit), page_size=200)
                return [_normalize_event(row) for row in source]
            except BackendClientError:
                raise

        rows = await request_cached(request, ("church-data", "events", scope_path), load_rows)
        return sorted(rows, key=_event_sort_key, reverse=True)

    @staticmethod
    async def list_counts(request, ctx, *, location: str = "", event_id: str = "") -> list[dict[str, Any]]:
        return await ChurchDataService.list_count_submissions(request, ctx, location=location, event_id=event_id)

    @staticmethod
    async def count_summary(request, ctx) -> dict[str, Any]:
        return await _count_summary_public(request, ctx)

    @staticmethod
    async def list_count_review_groups(request) -> list[dict[str, Any]]:
        if await ChurchDataService.use_mock(request):
            raise BackendClientError("Count review requires a live pastor account.")
        client = async_client(get_api_client())
        return await client.list_count_review_groups(AuthService.get_access_token(request))

    @staticmethod
    async def list_unreported_sunday_locations(request, occurrence_date: str) -> list[dict[str, Any]]:
        if await ChurchDataService.use_mock(request):
            raise BackendClientError("Count reminders require a live pastor account.")
        client = async_client(get_api_client())
        return await client.list_unreported_sunday_locations(AuthService.get_access_token(request), occurrence_date)

    @staticmethod
    async def approve_count_group(request, count_id: str) -> dict[str, Any]:
        if await ChurchDataService.use_mock(request):
            raise BackendClientError("Count review is unavailable in demo mode.")
        client = async_client(get_api_client())
        result = await client.approve_count_group(AuthService.get_access_token(request), count_id)
        invalidate_ttl_prefix(("church_data", "raw_counts"))
        invalidate_ttl_prefix(("dashboard", "bootstrap"))
        invalidate_ttl_prefix(("reports",))
        return result

    @staticmethod
    async def reject_count_group(request, count_id: str, *, reason: str) -> dict[str, Any]:
        if await ChurchDataService.use_mock(request):
            raise BackendClientError("Count review is unavailable in demo mode.")
        client = async_client(get_api_client())
        result = await client.reject_count_group(AuthService.get_access_token(request), count_id, reason=reason)
        invalidate_ttl_prefix(("church_data", "raw_counts"))
        invalidate_ttl_prefix(("dashboard", "bootstrap"))
        invalidate_ttl_prefix(("reports",))
        return result

    @staticmethod
    async def remind_count_location(request, payload: dict[str, Any]) -> dict[str, Any]:
        if await ChurchDataService.use_mock(request):
            raise BackendClientError("Count reminders require a live pastor account.")
        client = async_client(get_api_client())
        return await client.remind_count_location(AuthService.get_access_token(request), payload)

    @staticmethod
    async def list_finance(request, ctx, *, fund_type: str = "", location: str = "", method: str = "") -> list[dict[str, Any]]:
        return await _list_finance_public(request, ctx, fund_type=fund_type, location=location, method=method)

    @staticmethod
    async def finance_summary(request, ctx) -> dict[str, Any]:
        return await _finance_summary_public(request, ctx)

    @staticmethod
    async def review_finance(request, entry_id: str, *, decision: str, note: str = "") -> dict[str, Any]:
        if await ChurchDataService.use_mock(request):
            raise BackendClientError("Finance review is unavailable in demo mode.")
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        reviewed = await client.review_offering(access_token, entry_id, decision=decision, note=note)
        _invalidate_finance_views()
        return _normalize_offering(reviewed, event_map={}, location_map={})

    @staticmethod
    async def correct_finance(request, entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if await ChurchDataService.use_mock(request):
            raise BackendClientError("Finance correction is unavailable in demo mode.")
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        corrected = await client.correct_offering(access_token, entry_id, payload)
        _invalidate_finance_views()
        return _normalize_offering(corrected, event_map={}, location_map={})

    @staticmethod
    async def reverse_finance(request, entry_id: str, reason: str) -> dict[str, Any]:
        if await ChurchDataService.use_mock(request):
            raise BackendClientError("Finance reversal is unavailable in demo mode.")
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        reversed_entry = await client.reverse_offering(access_token, entry_id, reason)
        _invalidate_finance_views()
        return _normalize_offering(reversed_entry, event_map={}, location_map={})

    @staticmethod
    async def finance_audit_history(request, entry_id: str) -> list[dict[str, Any]]:
        if await ChurchDataService.use_mock(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        return await client.offering_audit_history(access_token, entry_id)

    @staticmethod
    async def get_finance_entry(request, ctx, entry_id: str) -> dict[str, Any] | None:
        if await ChurchDataService.use_mock(request):
            return STORE.get_finance_entry(entry_id)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        try:
            source = await client.get_offering(access_token, entry_id)
        except BackendClientError as exc:
            if exc.status_code == 404:
                return None
            raise
        event_map, location_map = await _event_and_location_maps(request, ctx)
        return _normalize_offering(source, event_map=event_map, location_map=location_map)

    @staticmethod
    async def create_finance(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await ChurchDataService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        created = await client.create_offering(access_token, payload)
        ctx = type("Ctx", (), {"current_scope_path": "", "profile": None})()
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {row["event_id"]: row for row in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {row["location_id"]: row for row in locations}
        return _normalize_offering(created, event_map=event_map, location_map=location_map)

    @staticmethod
    async def list_records(
        request,
        ctx,
        *,
        search: str = "",
        status: str = "",
        location: str = "",
        gender: str = "",
        record_type: str = "",
    ) -> list[dict[str, Any]]:
        scope_path = await ChurchDataService._scope_path(request, ctx)
        if await ChurchDataService.use_mock(request):
            return STORE.list_records(
                scope_path,
                search=search,
                status=status,
                location=location,
                gender=gender,
                record_type=record_type,
            )
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {row["event_id"]: row for row in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {row["location_id"]: row for row in locations}
        async def load_records() -> list[dict[str, Any]]:
            source = await client.list_records(access_token, scope_path=scope_path)
            return [
                _normalize_record(row, event_map=event_map, location_map=location_map)
                for row in source
            ]

        rows = await request_cached(request, ("church-data", "records", scope_path), load_records)
        search_text = search.strip().lower()
        if search_text:
            rows = [
                row
                for row in rows
                if search_text in row["name"].lower()
                or search_text in row["phone"].lower()
                or search_text in row["service"].lower()
                or search_text in row["location"].lower()
            ]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if location:
            rows = [row for row in rows if row["location_id"] == location]
        if gender:
            rows = [row for row in rows if row["gender"] == gender]
        if record_type:
            rows = [row for row in rows if row["record_type"] == record_type]
        return sorted(rows, key=lambda row: (row["date"], row["name"]), reverse=True)

    @staticmethod
    async def get_record(request, ctx, record_id: str) -> dict[str, Any] | None:
        if await ChurchDataService.use_mock(request):
            return STORE.get_record(record_id)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        row = await client.get_record(access_token, record_id)
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {event["event_id"]: event for event in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {location["location_id"]: location for location in locations}
        return _normalize_record(row, event_map=event_map, location_map=location_map)

    @staticmethod
    async def create_record(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await ChurchDataService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        created = await client.create_record(access_token, payload)
        ctx = type("Ctx", (), {"current_scope_path": "", "profile": None})()
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {row["event_id"]: row for row in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {row["location_id"]: row for row in locations}
        return _normalize_record(created, event_map=event_map, location_map=location_map)

    @staticmethod
    async def list_attendance(
        request,
        ctx,
        *,
        status: str = "",
        location: str = "",
        unit: str = "",
        event_id: str = "",
    ) -> list[dict[str, Any]]:
        scope_path = await ChurchDataService._scope_path(request, ctx)
        if await ChurchDataService.use_mock(request):
            return STORE.list_attendance(
                scope_path,
                status=status,
                location=location,
                unit=unit,
                event_title=event_id,
            )
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {row["event_id"]: row for row in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {row["location_id"]: row for row in locations}
        async def load_attendance() -> list[dict[str, Any]]:
            source = await client.list_attendance(access_token, scope_path=scope_path)
            return [
                _normalize_attendance(row, event_map=event_map, location_map=location_map)
                for row in source
            ]

        rows = await request_cached(request, ("church-data", "attendance", scope_path), load_attendance)
        if status:
            rows = [row for row in rows if row["status"] == status]
        if location:
            rows = [row for row in rows if row["location_id"] == location]
        if unit:
            rows = [row for row in rows if row["unit"] == unit]
        if event_id:
            rows = [row for row in rows if row["event_id"] == event_id]
        return sorted(rows, key=lambda row: (row["date"], row["worker_name"]), reverse=True)

    @staticmethod
    async def get_attendance(request, ctx, attendance_id: str) -> dict[str, Any] | None:
        if not await ChurchDataService.live_enabled(request):
            return STORE.get_attendance_entry(attendance_id)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        row = await client.get_attendance(access_token, attendance_id)
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {event["event_id"]: event for event in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {location["location_id"]: location for location in locations}
        return _normalize_attendance(row, event_map=event_map, location_map=location_map)

    @staticmethod
    async def attendance_summary(request, ctx) -> dict[str, Any]:
        scope_path = await ChurchDataService._scope_path(request, ctx)
        if not await ChurchDataService.live_enabled(request):
            summary = STORE.attendance_summary(scope_path)
            summary["opportunities"] = int(summary.get("records") or 0)
            return summary
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        return await client.get_attendance_stats(access_token, scope_path=scope_path)

    @staticmethod
    async def _get_attendance_entry_legacy(request, ctx, attendance_id: str) -> dict[str, Any] | None:
        return await ChurchDataService._get_attendance_detail(request, ctx, attendance_id)

    @staticmethod
    async def _create_attendance_legacy(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        return await _create_attendance_public(request, payload)

async def _church_data_scope_path(request, ctx) -> str:
    return await maybe_await(PeopleService.effective_scope_path(request, ctx))


async def _list_events_public(request, ctx) -> list[dict[str, Any]]:
    scope_path = await _church_data_scope_path(request, ctx)
    if await ChurchDataService.use_mock(request):
        return [
            {"event_id": row["event_id"], "title": row["title"], "date": row.get("date", ""), "path": row.get("path", "")}
            for row in STORE.list_program_events(scope_path)
        ]
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    scope_path = await _church_data_scope_path(request, ctx)
    try:
        rows = await client.list_program_events(access_token, scope_path=scope_path)
    except (AttributeError, BackendClientError):
        return []
    return sorted([_normalize_event(row) for row in rows], key=_event_sort_key, reverse=True)


async def _event_and_location_maps(request, ctx) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    async def load():
        events = await maybe_await(ChurchDataService.list_events(request, ctx))
        locations = await maybe_await(PeopleService.list_locations(request, ctx))
        return {row["event_id"]: row for row in events}, {row["location_id"]: row for row in locations}
    return await request_cached(request, ("church_data", "event_location_maps"), load)


async def _list_count_submissions_public(request, ctx, *, location: str = "", event_id: str = "") -> list[dict[str, Any]]:
    scope_path = await _church_data_scope_path(request, ctx)
    if await ChurchDataService.use_mock(request):
        return STORE.list_counts(scope_path, location=location, event_title=event_id)

    async def load_counts():
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        event_map, location_map = await _event_and_location_maps(request, ctx)
        return [
            _normalize_count(row, event_map=event_map, location_map=location_map)
            for row in await fetch_all_pages(lambda skip, limit: client.list_counts(access_token, scope_path=scope_path, skip=skip, limit=limit), page_size=200)
        ]

    rows = await request_cached(request, ("church_data", "raw_counts", scope_path), load_counts)
    if location:
        rows = [row for row in rows if row["location_id"] == location]
    if event_id:
        rows = [row for row in rows if row["event_id"] == event_id]
    return sorted(rows, key=lambda row: (row["date"], row["event_title"]), reverse=True)


async def _count_summary_public(request, ctx) -> dict[str, Any]:
    scope_path = await _church_data_scope_path(request, ctx)
    if await ChurchDataService.use_mock(request):
        rows = STORE.list_counts(scope_path)
        return summarize_count_submissions(rows)
    rows = await _list_count_submissions_public(request, ctx)
    return summarize_count_submissions(rows)


async def _list_finance_public(request, ctx, *, fund_type: str = "", location: str = "", method: str = "") -> list[dict[str, Any]]:
    scope_path = await _church_data_scope_path(request, ctx)
    if await ChurchDataService.use_mock(request):
        return STORE.list_finance(scope_path, fund_type=fund_type, location=location, method=method)

    async def load_offerings():
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        event_map, location_map = await _event_and_location_maps(request, ctx)
        source_rows = []
        page_size = 500
        skip = 0
        while True:
            page = await client.list_offerings(access_token, scope_path=scope_path, skip=skip, limit=page_size)
            source_rows.extend(page)
            if len(page) < page_size:
                break
            skip += len(page)
        return [_normalize_offering(row, event_map=event_map, location_map=location_map) for row in source_rows]

    rows = await request_cached(request, ("church_data", "raw_offerings", scope_path), load_offerings)
    if fund_type:
        rows = [row for row in rows if row["fund_type"] == fund_type]
    if location:
        rows = [row for row in rows if row["location_id"] == location]
    if method:
        rows = [row for row in rows if row["method"] == method]
    return sorted(rows, key=lambda row: (row["date"], row["event_title"]), reverse=True)


async def _finance_summary_public(request, ctx) -> dict[str, Any]:
    scope_path = await _church_data_scope_path(request, ctx)
    if await ChurchDataService.use_mock(request):
        return STORE.finance_summary(scope_path)
    rows = await _list_finance_public(request, ctx)
    today = date.today()
    month_prefix = today.strftime("%Y-%m")
    year_prefix = str(today.year)
    approved = [row for row in rows if row.get("status") == "approved"]
    pending = [row for row in rows if row.get("status") in {"pending", "corrected"}]
    month_approved = [row for row in approved if row.get("entry_date", row.get("date", "")).startswith(month_prefix)]
    year_approved = [row for row in approved if row.get("entry_date", row.get("date", "")).startswith(year_prefix)]
    month_pending = [row for row in pending if row.get("entry_date", row.get("date", "")).startswith(month_prefix)]
    year_pending = [row for row in pending if row.get("entry_date", row.get("date", "")).startswith(year_prefix)]
    return {
        "month_total": sum(float(row["amount"]) for row in month_approved),
        "year_total": sum(float(row["amount"]) for row in year_approved),
        "month_pending_total": sum(float(row["amount"]) for row in month_pending),
        "year_pending_total": sum(float(row["amount"]) for row in year_pending),
        "pending_total": sum(float(row["amount"]) for row in pending),
        "average_entry": round(sum(float(row["amount"]) for row in approved) / len(approved), 2) if approved else 0,
        "entries": len(approved),
        "approved_count": len(approved),
        "pending_count": sum(row.get("status") == "pending" for row in rows),
        "corrected_count": sum(row.get("status") == "corrected" for row in rows),
        "rejected_count": sum(row.get("status") == "rejected" for row in rows),
        "other_count": sum(row.get("status") not in {"approved", "pending", "rejected"} for row in rows),
        "month_approved_count": len(month_approved),
    }



async def _create_finance_public(request, payload: dict[str, Any]) -> dict[str, Any] | None:
    if await ChurchDataService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    created = await client.create_offering(access_token, payload)
    ctx = type("Ctx", (), {"current_scope_path": "", "profile": None})()
    event_map, location_map = await _event_and_location_maps(request, ctx)
    return _normalize_offering(created, event_map=event_map, location_map=location_map)


async def _list_records_public(
    request,
    ctx,
    *,
    search: str = "",
    status: str = "",
    location: str = "",
    gender: str = "",
    record_type: str = "",
) -> list[dict[str, Any]]:
    scope_path = await _church_data_scope_path(request, ctx)
    if await ChurchDataService.use_mock(request):
        return STORE.list_records(scope_path, search=search, status=status, location=location, gender=gender, record_type=record_type)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    event_map, location_map = await _event_and_location_maps(request, ctx)
    rows = [
        _normalize_record(row, event_map=event_map, location_map=location_map)
        for row in await fetch_all_pages(lambda skip, limit: client.list_records(access_token, scope_path=scope_path, skip=skip, limit=limit), page_size=200)
    ]
    if record_type:
        rows = [row for row in rows if row["record_type"] == record_type]
    if status:
        rows = [row for row in rows if row["status"] == status]
    if location:
        rows = [row for row in rows if row["location_id"] == location]
    if gender:
        rows = [row for row in rows if row["gender"] == gender]
    if search:
        term = search.lower().strip()
        rows = [row for row in rows if term in row["name"].lower() or term in row["phone"].lower() or term in row["service"].lower()]
    return sorted(rows, key=lambda row: (row["date"], row["name"]), reverse=True)


async def _create_record_public(request, payload: dict[str, Any]) -> dict[str, Any] | None:
    if await ChurchDataService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    created = await client.create_record(access_token, payload)
    ctx = type("Ctx", (), {"current_scope_path": "", "profile": None})()
    event_map, location_map = await _event_and_location_maps(request, ctx)
    return _normalize_record(created, event_map=event_map, location_map=location_map)


async def _create_count_public(request, payload: dict[str, Any]) -> dict[str, Any] | None:
    if await ChurchDataService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    created = await client.create_count(access_token, payload)
    ctx = type("Ctx", (), {"current_scope_path": "", "profile": None})()
    event_map, location_map = await _event_and_location_maps(request, ctx)
    return _normalize_count(created, event_map=event_map, location_map=location_map)


async def _list_attendance_public(request, ctx, *, status: str = "", location: str = "", unit: str = "", event_id: str = "") -> list[dict[str, Any]]:
    scope_path = await _church_data_scope_path(request, ctx)
    if await ChurchDataService.use_mock(request):
        return STORE.list_attendance(scope_path, status=status, location=location, unit=unit, event_title=event_id)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    event_map, location_map = await _event_and_location_maps(request, ctx)
    rows = [
        _normalize_attendance(row, event_map=event_map, location_map=location_map)
        for row in await fetch_all_pages(lambda skip, limit: client.list_attendance(access_token, scope_path=scope_path, skip=skip, limit=limit), page_size=200)
    ]
    if status:
        rows = [row for row in rows if row["status"] == status]
    if location:
        rows = [row for row in rows if row["location_id"] == location]
    if unit:
        rows = [row for row in rows if row["unit"] == unit]
    if event_id:
        rows = [row for row in rows if row["event_id"] == event_id]
    return sorted(rows, key=lambda row: (row["date"], row["worker_name"]), reverse=True)


async def _attendance_summary_public(request, ctx) -> dict[str, Any]:
    scope_path = await _church_data_scope_path(request, ctx)
    if await ChurchDataService.use_mock(request):
        return STORE.attendance_summary(scope_path)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    return await client.get_attendance_stats(access_token, scope_path=scope_path)


async def _create_attendance_public(request, payload: dict[str, Any]) -> dict[str, Any] | None:
    if await ChurchDataService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    created = await client.create_attendance(access_token, payload)
    ctx = type("Ctx", (), {"current_scope_path": "", "profile": None})()
    event_map, location_map = await _event_and_location_maps(request, ctx)
    return _normalize_attendance(created, event_map=event_map, location_map=location_map)


async def _get_attendance_detail(request, ctx, attendance_id: str) -> dict[str, Any] | None:
    if not await ChurchDataService.live_enabled(request):
        return STORE.get_attendance_entry(attendance_id)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    row = await client.get_attendance(access_token, attendance_id)
    event_map, location_map = await _event_and_location_maps(request, ctx)
    return _normalize_attendance(row, event_map=event_map, location_map=location_map)


ChurchDataService._scope_path = staticmethod(_church_data_scope_path)
ChurchDataService.list_events = staticmethod(_list_events_public)
ChurchDataService.list_count_submissions = staticmethod(_list_count_submissions_public)
ChurchDataService.list_counts = staticmethod(_list_count_submissions_public)
ChurchDataService.count_summary = staticmethod(_count_summary_public)
ChurchDataService.list_finance = staticmethod(_list_finance_public)
ChurchDataService.finance_summary = staticmethod(_finance_summary_public)
ChurchDataService.create_finance = staticmethod(_create_finance_public)
ChurchDataService.list_records = staticmethod(_list_records_public)
ChurchDataService.create_record = staticmethod(_create_record_public)
ChurchDataService.get_record = staticmethod(ChurchDataService.get_record)
ChurchDataService.create_count = staticmethod(_create_count_public)
ChurchDataService.list_attendance = staticmethod(_list_attendance_public)
ChurchDataService.attendance_summary = staticmethod(_attendance_summary_public)
ChurchDataService.create_attendance = staticmethod(_create_attendance_public)
ChurchDataService.get_attendance_entry = staticmethod(_get_attendance_detail)


dual_mode_class(ChurchDataService)

__all__ = ["ChurchDataService", "PAYMENT_METHOD_LABELS"]
