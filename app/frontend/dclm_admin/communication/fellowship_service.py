from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ..backend import BackendClientError
from ..backend.config import get_backend_config
from .request_cache import request_cached
from .ttl_cache import ttl_cached
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .people_service import PeopleService


def _safe_date(value: Any) -> str:
    raw = str(value or "")
    return raw[:10] if raw else ""


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_fellowship(row: dict[str, Any], *, details: dict[str, Any], members: list[dict[str, Any]], attendance: list[dict[str, Any]], offerings: list[dict[str, Any]], prayers: list[dict[str, Any]]) -> dict[str, Any]:
    latest_attendance = attendance[0]["total"] if attendance else 0
    latest_offering = offerings[0]["amount"] if offerings else 0
    return {
        "fellowship_id": str(row.get("fellowship_id") or ""),
        "name": str(row.get("fellowship_name") or "Fellowship"),
        "location": str(row.get("location_name") or details.get("location_name") or row.get("location_id") or ""),
        "meeting_day": "House Fellowship",
        "meeting_time": "Evening",
        "status": "active",
        "leader_name": str(row.get("leader_in_charge") or "Not assigned"),
        "assistant_name": "Not assigned",
        "member_count": len(members),
        "last_attendance": latest_attendance,
        "last_offering": latest_offering,
        "open_prayers": sum(1 for prayer in prayers if prayer["status"] == "pending"),
        "description": str(row.get("associate_church") or row.get("fellowship_address") or "Local fellowship gathering."),
        "path": str(row.get("path") or ""),
        "next_meeting": "Next scheduled fellowship meeting",
        "formatted_id": str(row.get("formatted_id") or ""),
    }


def _normalize_member(row: dict[str, Any]) -> dict[str, Any]:
    created = str(row.get("created_at") or "")
    return {
        "member_id": str(row.get("id") or ""),
        "name": str(row.get("name") or "Member"),
        "phone": str(row.get("phone") or ""),
        "gender": str(row.get("gender") or ""),
        "marital_status": str(row.get("role") or "Member"),
        "status": "active" if bool(row.get("is_active", True)) else "inactive",
        "date_joined": created[:10] if created else "",
    }


def _normalize_attendance(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "attendance_id": str(row.get("id") or ""),
        "date": _safe_date(row.get("date")),
        "men": int(row.get("men") or 0),
        "women": int(row.get("women") or 0),
        "youths": int(row.get("youths") or 0),
        "children": int(row.get("children") or 0),
        "total": int(row.get("total") or 0),
        "submitted_by": str(row.get("entered_by_id") or "Backend user"),
        "topic": str(row.get("topic") or ""),
        "notes": str(row.get("note") or ""),
    }


def _normalize_offering(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "offering_id": str(row.get("id") or ""),
        "date": _safe_date(row.get("date")),
        "amount": _money(row.get("amount")),
        "method": "Cash",
        "submitted_by": str(row.get("entered_by_id") or "Backend user"),
        "notes": str(row.get("note") or ""),
    }


def _normalize_testimony(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "testimony_id": str(row.get("id") or ""),
        "member_name": str(row.get("testifier_name") or "Member"),
        "date": _safe_date(row.get("date")),
        "summary": str(row.get("content") or ""),
        "status": "active",
    }


def _normalize_prayer(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "prayer_id": str(row.get("id") or ""),
        "requester_name": str(row.get("requestor_name") or "Member"),
        "date": _safe_date(row.get("date")),
        "summary": str(row.get("content") or ""),
        "status": str(row.get("status") or "pending"),
    }


def _normalize_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary_id": str(row.get("id") or ""),
        "week_of": f"{row.get('month') or 0:02d}/{row.get('year') or ''}",
        "average_attendance": int(row.get("avg_attendance") or 0),
        "homes_visited": 0,
        "newcomers": 0,
        "converts": 0,
        "submitted_by": str(row.get("entered_by_id") or "Backend user"),
        "remarks": f"{int(row.get('total_meetings') or 0)} meeting(s) recorded.",
    }


class FellowshipService:
    @staticmethod
    async def live_enabled(request) -> bool:
        return get_backend_config().enabled and bool(AuthService.get_access_token(request))

    @staticmethod
    async def use_mock(request) -> str:
        token = AuthService.get_access_token(request)
        if not token:
            raise BackendClientError("Backend authentication is required for fellowship.")
        return token

    @staticmethod
    async def _cache_key(location_id: str) -> tuple[str, str]:
        return ("fellowship", "location", location_id)

    @staticmethod
    async def list_fellowships(request, ctx, *, search: str = "", location: str = "", status: str = "") -> list[dict[str, Any]]:
        client = async_client(get_api_client())
        access_token = await FellowshipService._token(request)

        async def load_rows() -> list[dict[str, Any]]:
            try:
                rows = await maybe_await(ttl_cached(
                    ("fellowship", "rows", location or ""),
                    60.0,
                    lambda: client.list_fellowships(access_token, location_id=location or None, limit=500),
                ))
            except BackendClientError:
                return []
            normalized = []
            for row in rows:
                fellowship_id = str(row.get("fellowship_id") or "")
                location_id = str(row.get("location_id") or "")
                details = await request_cached(
                    request,
                    await FellowshipService._details_key(location_id),
                    lambda: PeopleService.get_location_details(request, location_id) or {},
                )
                members = await FellowshipService.list_members(request, fellowship_id)
                attendance = await FellowshipService.list_attendance(request, fellowship_id)
                offerings = await FellowshipService.list_offerings(request, fellowship_id)
                prayers = await FellowshipService.list_prayers(request, fellowship_id)
                normalized.append(
                    _normalize_fellowship(
                        row,
                        details=details,
                        members=members,
                        attendance=attendance,
                        offerings=offerings,
                        prayers=prayers,
                    )
                )
            return normalized

        normalized = await request_cached(request, ("fellowship", "list", location or ""), load_rows)
        if search:
            term = search.lower().strip()
            normalized = [
                row
                for row in normalized
                if term in row["name"].lower()
                or term in row["leader_name"].lower()
                or term in row["location"].lower()
                or term in row["formatted_id"].lower()
            ]
        if status:
            normalized = [row for row in normalized if row["status"] == status]
        return sorted(normalized, key=lambda row: (row["location"].lower(), row["name"].lower()))

    @staticmethod
    async def fellowship_stats(request, ctx) -> dict[str, int]:
        rows = await FellowshipService.list_fellowships(request, ctx)
        attendance = [row["last_attendance"] for row in rows if row["last_attendance"]]
        return {
            "total": len(rows),
            "members": sum(row["member_count"] for row in rows),
            "average_attendance": round(sum(attendance) / len(attendance)) if attendance else 0,
            "open_prayers": sum(row["open_prayers"] for row in rows),
        }

    @staticmethod
    async def get_fellowship(request, fellowship_id: str) -> dict[str, Any] | None:
        client = async_client(get_api_client())
        access_token = await FellowshipService._token(request)

        async def load_row() -> dict[str, Any] | None:
            try:
                row = await maybe_await(ttl_cached(
                    ("fellowship", "detail", fellowship_id),
                    60.0,
                    lambda: client.get_fellowship(access_token, fellowship_id),
                ))
            except BackendClientError:
                return None
            location_id = str(row.get("location_id") or "")
            details = await request_cached(
                request,
                await FellowshipService._details_key(location_id),
                lambda: PeopleService.get_location_details(request, location_id) or {},
            )
            members = await FellowshipService.list_members(request, fellowship_id)
            attendance = await FellowshipService.list_attendance(request, fellowship_id)
            offerings = await FellowshipService.list_offerings(request, fellowship_id)
            prayers = await FellowshipService.list_prayers(request, fellowship_id)
            return _normalize_fellowship(row, details=details, members=members, attendance=attendance, offerings=offerings, prayers=prayers)

        return await request_cached(request, ("fellowship", "detail", fellowship_id), load_row)

    @staticmethod
    async def list_members(request, fellowship_id: str) -> list[dict[str, Any]]:
        client = async_client(get_api_client())
        access_token = await FellowshipService._token(request)

        async def load_rows() -> list[dict[str, Any]]:
            try:
                rows = await maybe_await(ttl_cached(
                    ("fellowship", "members", fellowship_id),
                    60.0,
                    lambda: client.list_fellowship_members(access_token, fellowship_id=fellowship_id, limit=200),
                ))
            except BackendClientError:
                return []
            return sorted((_normalize_member(row) for row in rows), key=lambda row: row["name"].lower())

        return await request_cached(request, ("fellowship", "members", fellowship_id), load_rows)

    @staticmethod
    async def list_attendance(request, fellowship_id: str) -> list[dict[str, Any]]:
        client = async_client(get_api_client())
        access_token = await FellowshipService._token(request)

        async def load_rows() -> list[dict[str, Any]]:
            try:
                rows = await maybe_await(ttl_cached(
                    ("fellowship", "attendance", fellowship_id),
                    60.0,
                    lambda: client.list_fellowship_attendance(access_token, fellowship_id=fellowship_id, limit=200),
                ))
            except BackendClientError:
                return []
            return sorted((_normalize_attendance(row) for row in rows), key=lambda row: row["date"], reverse=True)

        return await request_cached(request, ("fellowship", "attendance", fellowship_id), load_rows)

    @staticmethod
    async def list_offerings(request, fellowship_id: str) -> list[dict[str, Any]]:
        client = async_client(get_api_client())
        access_token = await FellowshipService._token(request)

        async def load_rows() -> list[dict[str, Any]]:
            try:
                rows = await maybe_await(ttl_cached(
                    ("fellowship", "offerings", fellowship_id),
                    60.0,
                    lambda: client.list_fellowship_offerings(access_token, fellowship_id=fellowship_id, limit=200),
                ))
            except BackendClientError:
                return []
            return sorted((_normalize_offering(row) for row in rows), key=lambda row: row["date"], reverse=True)

        return await request_cached(request, ("fellowship", "offerings", fellowship_id), load_rows)

    @staticmethod
    async def list_testimonies(request, fellowship_id: str) -> list[dict[str, Any]]:
        client = async_client(get_api_client())
        access_token = await FellowshipService._token(request)

        async def load_rows() -> list[dict[str, Any]]:
            try:
                rows = await maybe_await(ttl_cached(
                    ("fellowship", "testimonies", fellowship_id),
                    60.0,
                    lambda: client.list_fellowship_testimonies(access_token, fellowship_id=fellowship_id, limit=200),
                ))
            except BackendClientError:
                return []
            return sorted((_normalize_testimony(row) for row in rows), key=lambda row: row["date"], reverse=True)

        return await request_cached(request, ("fellowship", "testimonies", fellowship_id), load_rows)

    @staticmethod
    async def list_prayers(request, fellowship_id: str) -> list[dict[str, Any]]:
        client = async_client(get_api_client())
        access_token = await FellowshipService._token(request)

        async def load_rows() -> list[dict[str, Any]]:
            try:
                rows = await maybe_await(ttl_cached(
                    ("fellowship", "prayers", fellowship_id),
                    60.0,
                    lambda: client.list_fellowship_prayers(access_token, fellowship_id=fellowship_id, limit=200),
                ))
            except BackendClientError:
                return []
            return sorted((_normalize_prayer(row) for row in rows), key=lambda row: row["date"], reverse=True)

        return await request_cached(request, ("fellowship", "prayers", fellowship_id), load_rows)

    @staticmethod
    async def list_summaries(request, fellowship_id: str) -> list[dict[str, Any]]:
        client = async_client(get_api_client())
        access_token = await FellowshipService._token(request)

        async def load_rows() -> list[dict[str, Any]]:
            try:
                rows = await maybe_await(ttl_cached(
                    ("fellowship", "summaries", fellowship_id),
                    60.0,
                    lambda: client.list_fellowship_summaries(access_token, fellowship_id=fellowship_id, limit=200),
                ))
            except BackendClientError:
                return []
            return sorted((_normalize_summary(row) for row in rows), key=lambda row: row["week_of"], reverse=True)

        return await request_cached(request, ("fellowship", "summaries", fellowship_id), load_rows)

    @staticmethod
    async def fellowship_full_detail(request, fellowship_id: str) -> dict[str, Any]:
        members = await FellowshipService.list_members(request, fellowship_id)
        attendance = await FellowshipService.list_attendance(request, fellowship_id)
        offerings = await FellowshipService.list_offerings(request, fellowship_id)
        prayers = await FellowshipService.list_prayers(request, fellowship_id)
        summaries = await FellowshipService.list_summaries(request, fellowship_id)
        return {
            "member_count": len(members),
            "last_attendance": attendance[0]["total"] if attendance else 0,
            "last_offering": offerings[0]["amount"] if offerings else 0,
            "open_prayers": sum(1 for prayer in prayers if prayer["status"] == "pending"),
            "latest_summary": summaries[0] if summaries else None,
        }

    @staticmethod
    async def add_member(request, fellowship_id: str, payload: dict[str, str]) -> dict[str, Any]:
        client = async_client(get_api_client())
        row = await client.create_fellowship_member(
            await FellowshipService._token(request),
            {
                "fellowship_id": fellowship_id,
                "name": payload.get("name") or "Member",
                "phone": payload.get("phone") or None,
                "gender": payload.get("gender") or None,
                "address": payload.get("address") or None,
                "role": "member",
            },
        )
        return _normalize_member(row)

    @staticmethod
    async def add_offering(request, fellowship_id: str, payload: dict[str, str]) -> dict[str, Any]:
        client = async_client(get_api_client())
        row = await client.create_fellowship_offering(
            await FellowshipService._token(request),
            {
                "fellowship_id": fellowship_id,
                "date": f"{payload.get('date') or date.today().isoformat()}T00:00:00",
                "amount": str(Decimal(payload.get("amount") or "0")),
                "note": payload.get("notes") or None,
            },
        )
        return _normalize_offering(row)

    @staticmethod
    async def add_testimony(request, fellowship_id: str, payload: dict[str, str]) -> dict[str, Any]:
        client = async_client(get_api_client())
        row = await client.create_fellowship_testimony(
            await FellowshipService._token(request),
            {
                "fellowship_id": fellowship_id,
                "date": f"{payload.get('date') or date.today().isoformat()}T00:00:00",
                "testifier_name": payload.get("member_name") or None,
                "content": payload.get("summary") or "",
                "note": None,
            },
        )
        return _normalize_testimony(row)

    @staticmethod
    async def add_prayer(request, fellowship_id: str, payload: dict[str, str]) -> dict[str, Any]:
        client = async_client(get_api_client())
        row = await client.create_fellowship_prayer(
            await FellowshipService._token(request),
            {
                "fellowship_id": fellowship_id,
                "date": f"{payload.get('date') or date.today().isoformat()}T00:00:00",
                "requestor_name": payload.get("requester_name") or None,
                "content": payload.get("summary") or "",
                "status": "pending",
            },
        )
        return _normalize_prayer(row)


FellowshipService.fellowship_summary = staticmethod(FellowshipService.fellowship_stats)
FellowshipService.fellowship_detail_summary = staticmethod(FellowshipService.fellowship_full_detail)
FellowshipService.create_member = staticmethod(FellowshipService.add_member)
FellowshipService.create_offering = staticmethod(FellowshipService.add_offering)
FellowshipService.create_testimony = staticmethod(FellowshipService.add_testimony)
FellowshipService.create_prayer = staticmethod(FellowshipService.add_prayer)

dual_mode_class(FellowshipService)

__all__ = ["FellowshipService"]
