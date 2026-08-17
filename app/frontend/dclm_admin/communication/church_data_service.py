from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..backend import BackendClientError
from ..backend.config import get_backend_config
from ..mock_data import STORE
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .people_service import PeopleService
from .request_cache import request_cached


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
        "event_id": str(row.get("event_id") or ""),
        "event_title": event["title"] if event else str(row.get("event_id") or "Unknown event"),
        "date": str((event or {}).get("date") or str(row.get("created_at") or "")[:10]),
        "location": (location or {}).get("location_name") or str(row.get("location_id") or ""),
        "location_id": str(row.get("location_id") or ""),
        "adult_male": int(row.get("adult_male") or 0),
        "adult_female": int(row.get("adult_female") or 0),
        "youth_male": int(row.get("youth_male") or 0),
        "youth_female": int(row.get("youth_female") or 0),
        "boys": int(row.get("boys") or 0),
        "girls": int(row.get("girls") or 0),
        "total": int(row.get("total") or 0),
        "submitted_by": str(row.get("entered_by_id") or "Recorded in backend"),
        "note": str(row.get("note") or ""),
        "assignment_id": str(row.get("assignment_id") or ""),
        "source_role": str(row.get("source_role") or "regular"),
        "campaign_code": str(row.get("campaign_code") or ""),
        "submission_channel": str(row.get("submission_channel") or ""),
    }


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
    async def list_counts(request, ctx) -> list[dict[str, Any]]:
        if await ChurchDataService.use_mock(request):
            return [
                {"event_id": row["event_id"], "title": row["title"], "date": row.get("date", ""), "path": row.get("path", "")}
                for row in STORE.list_program_events(ctx.current_scope_path)
            ]
        scope_path = await ChurchDataService._scope_path(request, ctx)

        async def load_rows() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            try:
                return [_normalize_event(row) for row in await client.list_program_events(access_token, scope_path=scope_path)]
            except BackendClientError:
                return []

        rows = await request_cached(request, ("church-data", "events", scope_path), load_rows)
        return sorted(rows, key=_event_sort_key, reverse=True)

    @staticmethod
    async def list_offerings(request, ctx, *, location: str = "", event_id: str = "") -> list[dict[str, Any]]:
        if await ChurchDataService.use_mock(request):
            return STORE.list_counts(ctx.current_scope_path, location=location, event_title=event_id)
        scope_path = await ChurchDataService._scope_path(request, ctx)
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {row["event_id"]: row for row in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {row["location_id"]: row for row in locations}

        async def load_rows() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            return [
                _normalize_count(row, event_map=event_map, location_map=location_map)
                for row in await client.list_counts(access_token, scope_path=scope_path)
            ]

        rows = await request_cached(request, ("church-data", "counts", scope_path), load_rows)
        if location:
            rows = [row for row in rows if row["location_id"] == location]
        if event_id:
            rows = [row for row in rows if row["event_id"] == event_id]
        return sorted(rows, key=lambda row: (row["date"], row["event_title"]), reverse=True)

    @staticmethod
    async def list_attendance(request, ctx) -> dict[str, Any]:
        if await ChurchDataService.use_mock(request):
            return STORE.counts_summary(ctx.current_scope_path)
        rows = await ChurchDataService.list_counts(request, ctx)
        totals = [row["total"] for row in rows]
        latest_total = totals[0] if totals else 0
        monthly_total = sum(totals)
        locations_reporting = len({row["location_id"] for row in rows})
        average_total = round(monthly_total / len(rows)) if rows else 0
        return {
            "latest_total": latest_total,
            "monthly_total": monthly_total,
            "locations_reporting": locations_reporting,
            "average_total": average_total,
        }

    @staticmethod
    async def list_records(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await ChurchDataService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        created = await client.create_count(access_token, payload)
        ctx = type("Ctx", (), {"current_scope_path": "", "profile": None})()
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {row["event_id"]: row for row in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {row["location_id"]: row for row in locations}
        return _normalize_count(created, event_map=event_map, location_map=location_map)

    @staticmethod
    async def list_announcements(request, ctx, *, fund_type: str = "", location: str = "", method: str = "") -> list[dict[str, Any]]:
        if await ChurchDataService.use_mock(request):
            return STORE.list_finance(ctx.current_scope_path, fund_type=fund_type, location=location, method=method)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = await ChurchDataService._scope_path(request, ctx)
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {row["event_id"]: row for row in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {row["location_id"]: row for row in locations}
        async def load_finance() -> list[dict[str, Any]]:
            source = await client.list_offerings(access_token, scope_path=scope_path)
            return [
                _normalize_offering(row, event_map=event_map, location_map=location_map)
                for row in source
            ]

        rows = await request_cached(request, ("church-data", "finance", scope_path), load_finance)
        if fund_type:
            rows = [row for row in rows if row["fund_type"] == fund_type]
        if location:
            rows = [row for row in rows if row["location_id"] == location]
        if method:
            rows = [row for row in rows if row["method"] == method]
        return sorted(rows, key=lambda row: (row["date"], row["event_title"]), reverse=True)

    @staticmethod
    async def list_newcomers(request, ctx) -> dict[str, Any]:
        if await ChurchDataService.use_mock(request):
            return STORE.finance_summary(ctx.current_scope_path)
        rows = await ChurchDataService.list_finance(request, ctx)
        total = sum(float(row["amount"]) for row in rows)
        average = round(total / len(rows), 2) if rows else 0
        return {
            "month_total": total,
            "year_total": total,
            "average_entry": average,
            "entries": len(rows),
        }

    @staticmethod
    async def update_announcement(request, payload: dict[str, Any]) -> dict[str, Any] | None:
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
    async def create_count(
        request,
        ctx,
        *,
        search: str = "",
        status: str = "",
        location: str = "",
        gender: str = "",
        record_type: str = "",
    ) -> list[dict[str, Any]]:
        if await ChurchDataService.use_mock(request):
            return STORE.list_records(
                ctx.current_scope_path,
                search=search,
                status=status,
                location=location,
                gender=gender,
                record_type=record_type,
            )
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = await ChurchDataService._scope_path(request, ctx)
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
    async def create_offering(request, ctx, record_id: str) -> dict[str, Any] | None:
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
    async def create_attendance(request, payload: dict[str, Any]) -> dict[str, Any] | None:
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
    async def create_announcement(
        request,
        ctx,
        *,
        status: str = "",
        location: str = "",
        unit: str = "",
        event_id: str = "",
    ) -> list[dict[str, Any]]:
        if await ChurchDataService.use_mock(request):
            return STORE.list_attendance(
                ctx.current_scope_path,
                status=status,
                location=location,
                unit=unit,
                event_title=event_id,
            )
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = await ChurchDataService._scope_path(request, ctx)
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
    async def create_record(request, ctx, attendance_id: str) -> dict[str, Any] | None:
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
    async def update_announcement(request, ctx) -> dict[str, Any]:
        if not await ChurchDataService.live_enabled(request):
            return STORE.attendance_summary(ctx.current_scope_path)
        expected = len(await PeopleService.list_workers(request, ctx))
        rows = await ChurchDataService.list_attendance(request, ctx)
        present = sum(1 for row in rows if row["status"] == "present")
        absent = sum(1 for row in rows if row["status"] == "absent")
        late = sum(1 for row in rows if row["status"] == "late")
        excused = sum(1 for row in rows if row["status"] == "excused")
        rate = round((present / expected) * 100) if expected else 0
        return {
            "expected": expected,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "rate": rate,
        }

    @staticmethod
    async def publish_announcement(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not await ChurchDataService.live_enabled(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        created = await client.create_attendance(access_token, payload)
        ctx = type("Ctx", (), {"current_scope_path": "", "profile": None})()
        events = await ChurchDataService.list_events(request, ctx)
        event_map = {row["event_id"]: row for row in events}
        locations = await PeopleService.list_locations(request, ctx)
        location_map = {row["location_id"]: row for row in locations}
        return _normalize_attendance(created, event_map=event_map, location_map=location_map)

async def _church_data_scope_path(request, ctx) -> str:
    return await maybe_await(PeopleService.effective_scope_path(request, ctx))


async def _list_events_public(request, ctx) -> list[dict[str, Any]]:
    if await ChurchDataService.use_mock(request):
        return [
            {"event_id": row["event_id"], "title": row["title"], "date": row.get("date", ""), "path": row.get("path", "")}
            for row in STORE.list_program_events(ctx.current_scope_path)
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


async def _list_counts_public(request, ctx, *, location: str = "", event_id: str = "") -> list[dict[str, Any]]:
    if await ChurchDataService.use_mock(request):
        return STORE.list_counts(ctx.current_scope_path, location=location, event_title=event_id)
    scope_path = await _church_data_scope_path(request, ctx)

    async def load_counts():
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        event_map, location_map = await _event_and_location_maps(request, ctx)
        return [
            _normalize_count(row, event_map=event_map, location_map=location_map)
            for row in await client.list_counts(access_token, scope_path=scope_path)
        ]

    rows = await request_cached(request, ("church_data", "raw_counts", scope_path), load_counts)
    if location:
        rows = [row for row in rows if row["location_id"] == location]
    if event_id:
        rows = [row for row in rows if row["event_id"] == event_id]
    return sorted(rows, key=lambda row: (row["date"], row["event_title"]), reverse=True)


async def _count_summary_public(request, ctx) -> dict[str, Any]:
    if await ChurchDataService.use_mock(request):
        return STORE.counts_summary(ctx.current_scope_path)
    rows = await _list_counts_public(request, ctx)
    totals = [row["total"] for row in rows]
    return {
        "latest_total": totals[0] if totals else 0,
        "monthly_total": sum(totals),
        "locations_reporting": len({row["location_id"] for row in rows}),
        "average_total": round(sum(totals) / len(rows)) if rows else 0,
    }


async def _list_finance_public(request, ctx, *, fund_type: str = "", location: str = "", method: str = "") -> list[dict[str, Any]]:
    if await ChurchDataService.use_mock(request):
        return STORE.list_finance(ctx.current_scope_path, fund_type=fund_type, location=location, method=method)
    scope_path = await _church_data_scope_path(request, ctx)

    async def load_offerings():
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        event_map, location_map = await _event_and_location_maps(request, ctx)
        return [
            _normalize_offering(row, event_map=event_map, location_map=location_map)
            for row in await client.list_offerings(access_token, scope_path=scope_path)
        ]

    rows = await request_cached(request, ("church_data", "raw_offerings", scope_path), load_offerings)
    if fund_type:
        rows = [row for row in rows if row["fund_type"] == fund_type]
    if location:
        rows = [row for row in rows if row["location_id"] == location]
    if method:
        rows = [row for row in rows if row["method"] == method]
    return sorted(rows, key=lambda row: (row["date"], row["event_title"]), reverse=True)


async def _finance_summary_public(request, ctx) -> dict[str, Any]:
    if await ChurchDataService.use_mock(request):
        return STORE.finance_summary(ctx.current_scope_path)
    rows = await _list_finance_public(request, ctx)
    total = sum(float(row["amount"]) for row in rows)
    return {"month_total": total, "year_total": total, "average_entry": round(total / len(rows), 2) if rows else 0, "entries": len(rows)}



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
    if await ChurchDataService.use_mock(request):
        return STORE.list_records(ctx.current_scope_path, search=search, status=status, location=location, gender=gender, record_type=record_type)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    scope_path = await _church_data_scope_path(request, ctx)
    event_map, location_map = await _event_and_location_maps(request, ctx)
    rows = [
        _normalize_record(row, event_map=event_map, location_map=location_map)
        for row in await client.list_records(access_token, scope_path=scope_path)
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


async def _list_attendance_public(request, ctx, *, status: str = "", location: str = "", unit: str = "", event_id: str = "") -> list[dict[str, Any]]:
    if await ChurchDataService.use_mock(request):
        return STORE.list_attendance(ctx.current_scope_path, status=status, location=location, unit=unit, event_title=event_id)
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    scope_path = await _church_data_scope_path(request, ctx)
    event_map, location_map = await _event_and_location_maps(request, ctx)
    rows = [
        _normalize_attendance(row, event_map=event_map, location_map=location_map)
        for row in await client.list_attendance(access_token, scope_path=scope_path)
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
    if await ChurchDataService.use_mock(request):
        return STORE.attendance_summary(ctx.current_scope_path)
    expected = len(await PeopleService.list_workers(request, ctx))
    rows = await _list_attendance_public(request, ctx)
    present = sum(1 for row in rows if row["status"] == "present")
    absent = sum(1 for row in rows if row["status"] == "absent")
    late = sum(1 for row in rows if row["status"] == "late")
    excused = sum(1 for row in rows if row["status"] == "excused")
    return {"expected": expected, "present": present, "absent": absent, "late": late, "excused": excused, "rate": round((present / expected) * 100) if expected else 0}


async def _create_attendance_public(request, payload: dict[str, Any]) -> dict[str, Any] | None:
    if await ChurchDataService.use_mock(request):
        return None
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    created = await client.create_attendance(access_token, payload)
    ctx = type("Ctx", (), {"current_scope_path": "", "profile": None})()
    event_map, location_map = await _event_and_location_maps(request, ctx)
    return _normalize_attendance(created, event_map=event_map, location_map=location_map)


ChurchDataService._scope_path = staticmethod(_church_data_scope_path)
ChurchDataService.list_events = staticmethod(_list_events_public)
ChurchDataService.list_counts = staticmethod(_list_counts_public)
ChurchDataService.count_summary = staticmethod(_count_summary_public)
ChurchDataService.list_finance = staticmethod(_list_finance_public)
ChurchDataService.finance_summary = staticmethod(_finance_summary_public)
ChurchDataService.create_finance = staticmethod(_create_finance_public)
ChurchDataService.list_records = staticmethod(_list_records_public)
ChurchDataService.create_record = staticmethod(_create_record_public)
ChurchDataService.list_attendance = staticmethod(_list_attendance_public)
ChurchDataService.attendance_summary = staticmethod(_attendance_summary_public)
ChurchDataService.create_attendance = staticmethod(_create_attendance_public)


dual_mode_class(ChurchDataService)

__all__ = ["ChurchDataService", "PAYMENT_METHOD_LABELS"]
