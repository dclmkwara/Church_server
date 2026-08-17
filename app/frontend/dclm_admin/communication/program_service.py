from __future__ import annotations

from datetime import date
from typing import Any

from ..backend import BackendClientError, format_scope_display_id, split_scope_path
from ..backend.config import get_backend_config
from ..mock_data import STORE
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .church_data_service import ChurchDataService
from .people_service import PeopleService
from .request_cache import request_cached
from .ttl_cache import invalidate_ttl_prefix, ttl_cached


FALLBACK_PROGRAM_DOMAINS: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "Regular Services",
        "slug": "regular_services",
        "description": "Weekly and routine worship, study, workers, and leaders services.",
    },
    {
        "id": 2,
        "name": "Retreat",
        "slug": "retreat",
        "description": "Regional or occasional retreat-focused programs.",
    },
    {
        "id": 3,
        "name": "Open Crusade",
        "slug": "open_crusade",
        "description": "Monthly crusade and outreach program family.",
    },
    {
        "id": 4,
        "name": "Special Programs",
        "slug": "special_programs",
        "description": "Irregular major programs that do not fit routine service, retreat, or crusade cycles.",
    },
]


def _today_iso() -> str:
    return date.today().isoformat()


def _event_status(raw_date: str, published_at: str) -> str:
    if published_at:
        return "published"
    if raw_date and raw_date < _today_iso():
        return "completed"
    return "scheduled"


def _normalize_domain(row: dict[str, Any], event_rows: list[dict[str, Any]]) -> dict[str, Any]:
    domain_id = int(row.get("id") or 0)
    event_count = sum(1 for event in event_rows if int(event.get("domain_id") or 0) == domain_id)
    return {
        "domain_id": str(domain_id),
        "name": str(row.get("name") or "Unknown domain"),
        "slug": str(row.get("slug") or ""),
        "description": str(row.get("description") or ""),
        "event_count": event_count,
    }


def _normalize_type(row: dict[str, Any], domain_lookup: dict[int, str], event_rows: list[dict[str, Any]]) -> dict[str, Any]:
    type_id = int(row.get("id") or 0)
    domain_id = int(row.get("domain_id") or 0)
    event_count = sum(1 for event in event_rows if int(event.get("type_id") or 0) == type_id)
    return {
        "type_id": str(type_id),
        "name": str(row.get("name") or "Unknown type"),
        "slug": str(row.get("slug") or ""),
        "description": str(row.get("description") or ""),
        "domain_id": str(domain_id),
        "domain_name": domain_lookup.get(domain_id, f"Domain {domain_id}"),
        "event_count": event_count,
    }


def _normalize_event(row: dict[str, Any], domain_lookup: dict[int, str]) -> dict[str, Any]:
    program_type = row.get("program_type") or {}
    campaign = row.get("campaign") or {}
    domain_id = int(program_type.get("domain_id") or 0)
    raw_date = str(row.get("date") or "")
    path = str(row.get("path") or "")
    scope_bits = split_scope_path(path)
    return {
        "event_id": str(row.get("id") or ""),
        "title": str(row.get("title") or program_type.get("name") or "Program Event"),
        "program_type": str(program_type.get("name") or "Unknown Type"),
        "type_id": str(program_type.get("id") or ""),
        "domain_id": str(domain_id),
        "domain_name": domain_lookup.get(domain_id, "Unknown Domain"),
        "campaign_id": str(row.get("campaign_id") or ""),
        "campaign_title": str(campaign.get("title") or ""),
        "campaign_code": str(campaign.get("campaign_code") or ""),
        "location": str(scope_bits.get("location_id") or format_scope_display_id(path) or "Scoped event"),
        "location_id": str(scope_bits.get("location_id") or ""),
        "date": raw_date,
        "status": _event_status(raw_date, str(row.get("published_at") or "")),
        "path": path,
        "created_by": "Backend",
        "is_public": bool(row.get("is_public")),
        "event_mode": str(row.get("event_mode") or "regular"),
        "reporting_scope": str(row.get("reporting_scope") or "location"),
        "audience_segment": str(row.get("audience_segment") or ""),
    }


def _normalize_campaign(row: dict[str, Any], domain_lookup: dict[int, str]) -> dict[str, Any]:
    domain_id = int(row.get("domain_id") or 0)
    path = str(row.get("path") or "")
    scope_bits = split_scope_path(path)
    return {
        "campaign_id": str(row.get("id") or ""),
        "campaign_code": str(row.get("campaign_code") or ""),
        "title": str(row.get("title") or "Program Campaign"),
        "description": str(row.get("description") or ""),
        "domain_id": str(domain_id),
        "domain_name": domain_lookup.get(domain_id, "Unknown Domain"),
        "event_mode": str(row.get("event_mode") or "special"),
        "reporting_scope": str(row.get("reporting_scope") or "global"),
        "status": str(row.get("status") or "draft"),
        "alpha_location_id": str(row.get("alpha_location_id") or ""),
        "scope_id": format_scope_display_id(path) or "",
        "scope_name": str(scope_bits.get("location_id") or scope_bits.get("group_id") or scope_bits.get("region_id") or scope_bits.get("state_id") or ""),
        "start_date": str(row.get("start_date") or ""),
        "end_date": str(row.get("end_date") or ""),
        "flyer_url": str(row.get("flyer_url") or ""),
        "publicity_note": str(row.get("publicity_note") or ""),
    }


def _normalize_assignment(row: dict[str, Any], worker_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    worker_id = str(row.get("worker_id") or "")
    worker = worker_lookup.get(worker_id) or {}
    return {
        "assignment_id": str(row.get("id") or ""),
        "event_id": str(row.get("event_id") or ""),
        "worker_id": worker_id,
        "worker_name": str(worker.get("name") or worker_id or "Assigned worker"),
        "worker_public_code": str(worker.get("public_code") or ""),
        "assignment_label": str(row.get("assignment_label") or ""),
        "assignment_type": str(row.get("assignment_type") or "both"),
        "source_role": str(row.get("source_role") or "alpha"),
        "status": str(row.get("status") or "pending"),
        "note": str(row.get("note") or ""),
        "submission_completed": bool(row.get("submission_completed")),
        "submitted_at": str(row.get("submitted_at") or ""),
        "approved_at": str(row.get("approved_at") or ""),
        "created_at": str(row.get("created_at") or ""),
    }


def _fallback_domain_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in FALLBACK_PROGRAM_DOMAINS]


def _fallback_type_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for event in events:
        type_id = str(event.get("type_id") or "")
        if not type_id or type_id in seen:
            continue
        seen[type_id] = {
            "id": event.get("type_id") or "",
            "name": event.get("program_type") or "Unknown type",
            "slug": str(event.get("program_type") or "unknown_type").strip().lower().replace(" ", "_"),
            "description": "",
            "domain_id": event.get("domain_id") or "",
        }
    return list(seen.values())


class ProgramService:
    @staticmethod
    async def _mock_events(ctx) -> list[dict[str, Any]]:
        scope_path = getattr(ctx, "current_scope_path", "") or ""
        scope_id = format_scope_display_id(scope_path) or "DCM-234-KW-ILN-ILE-001"
        return [
            {
                "campaign_id": "cmp-hcf-0326",
                "campaign_code": "HCF-0326",
                "title": "March 2026 Fellowship Cycle",
                "description": "Program cycle for planning and reporting.",
                "domain_id": "dom-003",
                "domain_name": "Fellowship Meetings",
                "event_mode": "regular",
                "reporting_scope": "group",
                "status": "active",
                "alpha_location_id": "",
                "scope_id": scope_id,
                "scope_name": scope_id,
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
                "flyer_url": "",
                "publicity_note": "Mock reporting cycle.",
            }
        ]

    @staticmethod
    async def live_enabled(request) -> bool:
        return get_backend_config().enabled and bool(AuthService.get_access_token(request))

    @staticmethod
    async def use_mock(request) -> bool:
        if get_backend_config().enabled:
            if not AuthService.get_access_token(request):
                raise BackendClientError("Backend session required for programs.")
            return False
        return True

    @staticmethod
    async def effective_scope_path(request, ctx) -> str:
        identity = AuthService.get_identity(request)
        if identity and identity.scope_path:
            return identity.scope_path
        return ctx.current_scope_path

    @staticmethod
    async def _live_maps(request, ctx) -> tuple[list[dict[str, Any]], dict[int, str], list[dict[str, Any]]]:
        scope_path = await ProgramService.effective_scope_path(request, ctx)

        async def load_maps() -> tuple[list[dict[str, Any]], dict[int, str], list[dict[str, Any]]]:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            try:
                events_raw = await client.list_program_events(
                    access_token,
                    scope_path=scope_path,
                    limit=300,
                )
            except BackendClientError:
                events_raw = []
            try:
                domains_raw = await maybe_await(ttl_cached(
                    ("programs", "domains"),
                    60.0,
                    lambda: client.list_program_domains(access_token, limit=200),
                ))
            except BackendClientError:
                domains_raw = _fallback_domain_rows()
            domain_lookup = {int(row.get("id") or 0): str(row.get("name") or "") for row in domains_raw}
            events = [_normalize_event(row, domain_lookup) for row in events_raw]
            try:
                _ = await maybe_await(ttl_cached(
                    ("programs", "types", ""),
                    60.0,
                    lambda: client.list_program_types(access_token, limit=200),
                ))
            except BackendClientError:
                _ = _fallback_type_rows(events)
            return domains_raw, domain_lookup, events

        return await request_cached(request, ("programs", "live_maps", scope_path), load_maps)

    @staticmethod
    async def summary(request, ctx) -> dict[str, int]:
        if await ProgramService.use_mock(request):
            domains = await ProgramService.list_domains(request, ctx)
            types = await ProgramService.list_types(request, ctx)
            campaigns = await ProgramService.list_campaigns(request, ctx)
            events = await ProgramService.list_events(request, ctx)
            scheduled = sum(1 for e in events if e.get("status") in ("scheduled", "active", "published"))
            return {
                "domains": len(domains),
                "types": len(types),
                "campaigns": len(campaigns),
                "events": len(events),
                "scheduled": scheduled,
            }
        domains_raw, _domain_lookup, events = await ProgramService._live_maps(request, ctx)
        types = await ProgramService.list_types(request, ctx)
        campaigns = await ProgramService.list_campaigns(request, ctx)
        scheduled = sum(1 for e in events if e.get("status") in ("scheduled", "active", "published"))
        return {
            "domains": len(domains_raw),
            "types": len(types),
            "campaigns": len(campaigns),
            "events": len(events),
            "scheduled": scheduled,
        }

    @staticmethod
    async def list_domains(request, ctx) -> list[dict[str, Any]]:
        if await ProgramService.use_mock(request):
            return STORE.list_program_domains()
        domains_raw, _domain_lookup, events = await ProgramService._live_maps(request, ctx)
        return [_normalize_domain(row, events) for row in domains_raw]

    @staticmethod
    async def list_events(
        request,
        ctx,
        *,
        domain_slug: str = "",
        event_mode: str = "",
        status_value: str = "",
    ) -> list[dict[str, Any]]:
        if await ProgramService.use_mock(request):
            rows = await ProgramService._mock_campaigns(ctx)
            if domain_slug:
                rows = [row for row in rows if str(row["domain_name"]).lower().replace(" ", "_") == domain_slug]
            if event_mode:
                rows = [row for row in rows if row["event_mode"] == event_mode]
            if status_value:
                rows = [row for row in rows if row["status"] == status_value]
            return rows
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = await ProgramService.effective_scope_path(request, ctx)
        domains_raw, domain_lookup, _events = await ProgramService._live_maps(request, ctx)
        _ = domains_raw

        async def load_rows() -> list[dict[str, Any]]:
            campaigns_raw = await client.list_program_campaigns(
                access_token,
                scope_path=scope_path,
                program_domain=domain_slug or None,
                event_mode=event_mode or None,
                status_value=status_value or None,
                limit=200,
            )
            return [_normalize_campaign(row, domain_lookup) for row in campaigns_raw]

        return await request_cached(
            request,
            ("programs", "campaigns", scope_path, domain_slug, event_mode, status_value),
            load_rows,
        )

    @staticmethod
    async def list_types(request, ctx, *, domain_id: str = "") -> list[dict[str, Any]]:
        if await ProgramService.use_mock(request):
            return STORE.list_program_types(domain_id=domain_id)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = await ProgramService.effective_scope_path(request, ctx)
        domains_raw, domain_lookup, events = await ProgramService._live_maps(request, ctx)
        _ = domains_raw

        async def load_rows() -> list[dict[str, Any]]:
            try:
                types_raw = await maybe_await(ttl_cached(
                    ("programs", "types", domain_id or ""),
                    60.0,
                    lambda: client.list_program_types(access_token, domain_id=domain_id or None, limit=200),
                ))
            except BackendClientError:
                types_raw = _fallback_type_rows(events)
                if domain_id:
                    types_raw = [row for row in types_raw if str(row.get("domain_id") or "") == str(domain_id)]
            return [_normalize_type(row, domain_lookup, events) for row in types_raw]

        return await request_cached(request, ("programs", "types", scope_path, domain_id), load_rows)

    @staticmethod
    async def list_campaigns(
        request,
        ctx,
        *,
        search: str = "",
        domain_id: str = "",
        type_id: str = "",
        status: str = "",
        location: str = "",
    ) -> list[dict[str, Any]]:
        if await ProgramService.use_mock(request):
            return STORE.list_program_events(
                ctx.current_scope_path,
                search=search,
                domain_id=domain_id,
                type_id=type_id,
                status=status,
                location=location,
            )
        _domains_raw, _domain_lookup, events = await ProgramService._live_maps(request, ctx)
        rows = events
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["title"].lower()
                or term in row["program_type"].lower()
                or term in row["domain_name"].lower()
                or term in row["location"].lower()
            ]
        if domain_id:
            rows = [row for row in rows if row["domain_id"] == str(domain_id)]
        if type_id:
            rows = [row for row in rows if row["type_id"] == str(type_id)]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if location:
            rows = [row for row in rows if row["location"] == location or row["location_id"] == location]
        return rows

    @staticmethod
    async def domain_counts(request, ctx) -> dict[str, int]:
        if await ProgramService.use_mock(request):
            domains = STORE.list_program_domains()
            types = STORE.list_program_types()
            events = STORE.list_program_events(ctx.current_scope_path)
            campaigns = []
        else:
            domains = await ProgramService.list_domains(request, ctx)
            types = await ProgramService.list_types(request, ctx)
            events = await ProgramService.list_events(request, ctx)
            campaigns = await ProgramService.list_campaigns(request, ctx)
        return {
            "domains": len(domains),
            "types": len(types),
            "campaigns": len(campaigns),
            "events": len(events),
            "scheduled": sum(1 for row in events if row["status"] in {"scheduled", "published"}),
        }

    @staticmethod
    async def get_domain(request, ctx, domain_id: str) -> dict[str, Any] | None:
        return next((row for row in await ProgramService.list_domains(request, ctx) if row["domain_id"] == str(domain_id)), None)

    @staticmethod
    async def get_type(request, ctx, type_id: str) -> dict[str, Any] | None:
        return next((row for row in await ProgramService.list_types(request, ctx) if row["type_id"] == str(type_id)), None)

    @staticmethod
    async def get_event(request, ctx, event_id: str) -> dict[str, Any] | None:
        return next((row for row in await ProgramService.list_events(request, ctx) if row["event_id"] == str(event_id)), None)

    @staticmethod
    async def get_campaign(request, ctx, campaign_id: str) -> dict[str, Any] | None:
        return next((row for row in await ProgramService.list_campaigns(request, ctx) if row["campaign_id"] == str(campaign_id)), None)

    @staticmethod
    async def list_event_assignments(request, ctx, event_id: str, *, worker_lookup: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if await ProgramService.use_mock(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        if worker_lookup is None:
            worker_lookup = {row["worker_id"]: row for row in await PeopleService.list_workers(request, ctx)}
        rows = await request_cached(
            request,
            ("programs", "assignments", str(event_id)),
            lambda: client.list_event_assignments(access_token, event_id),
        )
        normalized = [_normalize_assignment(row, worker_lookup) for row in rows]
        return sorted(normalized, key=lambda row: (row["status"], row["worker_name"].lower()))

    @staticmethod
    async def create_event_assignment(request, ctx, event_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await ProgramService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        created = await client.create_event_assignment(
            access_token,
            event_id,
            {
                "worker_id": payload.get("worker_id") or "",
                "assignment_label": payload.get("assignment_label") or None,
                "assignment_type": payload.get("assignment_type") or "both",
                "source_role": payload.get("source_role") or "alpha",
                "note": payload.get("note") or None,
            },
        )
        worker_lookup = {row["worker_id"]: row for row in await PeopleService.list_workers(request, ctx)}
        return _normalize_assignment(created, worker_lookup)

    @staticmethod
    async def approve_event_assignment(request, ctx, assignment_id: str) -> dict[str, Any] | None:
        if await ProgramService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        updated = await client.approve_event_assignment(access_token, assignment_id)
        worker_lookup = {row["worker_id"]: row for row in await PeopleService.list_workers(request, ctx)}
        return _normalize_assignment(updated, worker_lookup)

    @staticmethod
    async def reject_event_assignment(request, ctx, assignment_id: str, note: str = "") -> dict[str, Any] | None:
        if await ProgramService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        updated = await client.reject_event_assignment(access_token, assignment_id, note=note or None)
        worker_lookup = {row["worker_id"]: row for row in await PeopleService.list_workers(request, ctx)}
        return _normalize_assignment(updated, worker_lookup)

    @staticmethod
    async def campaign_detail(request, ctx, campaign_id: str) -> dict[str, Any]:
        campaign = await ProgramService.get_campaign(request, ctx, campaign_id)
        if campaign is None:
            return {
                "events": [],
                "event_count": 0,
                "total_population": 0,
                "alpha_population": 0,
                "satellite_population": 0,
                "converts": 0,
                "newcomers": 0,
                "segment_breakdown": [],
                "assignments_total": 0,
                "assignments_approved": 0,
                "assignments_pending_approval": 0,
                "assignments_rejected": 0,
                "assignments_submitted": 0,
                "assignments_pending_submission": 0,
            }
        if await ProgramService.use_mock(request):
            event_rows = await ProgramService.list_events(request, ctx)
            count_rows = await ChurchDataService.list_counts(request, ctx)
            record_rows = await ChurchDataService.list_records(request, ctx)
            assignment_rows: list[dict[str, Any]] = []
        else:
            event_rows = [row for row in await ProgramService.list_events(request, ctx) if row["campaign_id"] == str(campaign_id)]
            event_ids = {row["event_id"] for row in event_rows}
            count_rows = [row for row in await ChurchDataService.list_counts(request, ctx) if row["event_id"] in event_ids]
            record_rows = [row for row in await ChurchDataService.list_records(request, ctx) if row["event_id"] in event_ids]
            worker_lookup = {row["worker_id"]: row for row in await PeopleService.list_workers(request, ctx)}
            assignment_rows = []
            for event in event_rows:
                assignment_rows.extend(await ProgramService.list_assignments(request, ctx, event["event_id"], worker_lookup=worker_lookup))
        segment_totals: dict[str, int] = {}
        summary_by_event: list[dict[str, Any]] = []
        for event in event_rows:
            event_counts = [row for row in count_rows if row["event_id"] == event["event_id"]]
            event_records = [
                row
                for row in record_rows
                if row.get("event_id") == event["event_id"] or row.get("service") == event["title"]
            ]
            event_assignments = [row for row in assignment_rows if row["event_id"] == event["event_id"]]
            population = sum(int(row["total"]) for row in event_counts)
            audience_segment = str(event.get("audience_segment") or "")
            if audience_segment:
                segment_totals[audience_segment] = segment_totals.get(audience_segment, 0) + population
            summary_by_event.append(
                {
                    "event_id": event["event_id"],
                    "title": event["title"],
                    "date": event["date"],
                    "location": event["location"],
                    "population": population,
                    "alpha_population": sum(int(row["total"]) for row in event_counts if row.get("source_role") == "alpha"),
                    "satellite_population": sum(int(row["total"]) for row in event_counts if row.get("source_role") == "satellite"),
                    "converts": sum(1 for row in event_records if row["record_type"] == "convert"),
                    "newcomers": sum(1 for row in event_records if row["record_type"] == "newcomer"),
                    "audience_segment": audience_segment,
                    "assignment_total": len(event_assignments),
                    "assignment_submitted": sum(1 for row in event_assignments if row["submission_completed"]),
                }
            )
        summary_by_event.sort(key=lambda row: (row["date"], row["title"]), reverse=True)
        assignments_total = len(assignment_rows)
        assignments_approved = sum(1 for row in assignment_rows if row["status"] == "approved")
        assignments_pending_approval = sum(1 for row in assignment_rows if row["status"] == "pending")
        assignments_rejected = sum(1 for row in assignment_rows if row["status"] == "rejected")
        assignments_submitted = sum(1 for row in assignment_rows if row["submission_completed"])
        return {
            "events": summary_by_event,
            "event_count": len(event_rows),
            "total_population": sum(int(row["total"]) for row in count_rows),
            "alpha_population": sum(int(row["total"]) for row in count_rows if row.get("source_role") == "alpha"),
            "satellite_population": sum(int(row["total"]) for row in count_rows if row.get("source_role") == "satellite"),
            "converts": sum(1 for row in record_rows if row["record_type"] == "convert"),
            "newcomers": sum(1 for row in record_rows if row["record_type"] == "newcomer"),
            "segment_breakdown": [
                {"segment": segment, "population": total}
                for segment, total in sorted(segment_totals.items())
            ],
            "assignments_total": assignments_total,
            "assignments_approved": assignments_approved,
            "assignments_pending_approval": assignments_pending_approval,
            "assignments_rejected": assignments_rejected,
            "assignments_submitted": assignments_submitted,
            "assignments_pending_submission": max(assignments_approved - assignments_submitted, 0),
        }

    @staticmethod
    async def create_domain(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await ProgramService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        created = await client.create_program_domain(
            access_token,
            {
                "name": payload.get("name") or "",
                "slug": str(payload.get("name") or "").strip().lower().replace(" ", "_"),
                "description": payload.get("description") or None,
            },
        )
        invalidate_ttl_prefix(("programs", "domains"))
        return {
            "domain_id": str(created.get("id") or ""),
            "name": str(created.get("name") or ""),
            "slug": str(created.get("slug") or ""),
            "description": str(created.get("description") or ""),
            "event_count": 0,
        }

    @staticmethod
    async def create_type(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await ProgramService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        created = await client.create_program_type(
            access_token,
            {
                "name": payload.get("name") or "",
                "slug": str(payload.get("name") or "").strip().lower().replace(" ", "_"),
                "domain_id": int(payload.get("domain_id") or 0),
                "description": payload.get("description") or None,
            },
        )
        invalidate_ttl_prefix(("programs", "types"))
        domains = await maybe_await(ttl_cached(
            ("programs", "domains"),
            60.0,
            lambda: client.list_program_domains(access_token, limit=200),
        ))
        domain_lookup = {int(row.get("id") or 0): str(row.get("name") or "") for row in domains}
        return {
            "type_id": str(created.get("id") or ""),
            "name": str(created.get("name") or ""),
            "slug": str(created.get("slug") or ""),
            "description": str(created.get("description") or ""),
            "domain_id": str(created.get("domain_id") or ""),
            "domain_name": domain_lookup.get(int(created.get("domain_id") or 0), ""),
            "event_count": 0,
        }

    @staticmethod
    async def create_event(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await ProgramService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        created = await client.create_program_event(
            access_token,
            {
                "program_type_id": int(payload.get("type_id") or 0),
                "campaign_id": payload.get("campaign_id") or None,
                "date": payload.get("date") or _today_iso(),
                "path": payload.get("path") or "",
                "title": payload.get("title") or None,
                "is_public": payload.get("status") == "published",
                "audience_segment": payload.get("audience_segment") or None,
            },
        )
        domains = await maybe_await(ttl_cached(
            ("programs", "domains"),
            60.0,
            lambda: client.list_program_domains(access_token, limit=200),
        ))
        domain_lookup = {int(row.get("id") or 0): str(row.get("name") or "") for row in domains}
        return _normalize_event(created, domain_lookup)

    @staticmethod
    async def create_campaign(request, payload: dict[str, Any]) -> dict[str, Any] | None:
        if await ProgramService.use_mock(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        created = await client.create_program_campaign(
            access_token,
            {
                "domain_id": int(payload.get("domain_id") or 0),
                "path": payload.get("path") or "",
                "campaign_code": payload.get("campaign_code") or "",
                "title": payload.get("title") or "",
                "description": payload.get("description") or None,
                "event_mode": payload.get("event_mode") or "special",
                "reporting_scope": payload.get("reporting_scope") or "global",
                "status": payload.get("status") or "draft",
                "alpha_location_id": payload.get("alpha_location_id") or None,
                "start_date": payload.get("start_date") or _today_iso(),
                "end_date": payload.get("end_date") or _today_iso(),
                "collection_window_start": payload.get("collection_window_start") or None,
                "collection_window_end": payload.get("collection_window_end") or None,
                "flyer_url": payload.get("flyer_url") or None,
                "publicity_note": payload.get("publicity_note") or None,
            },
        )
        domains = await maybe_await(ttl_cached(
            ("programs", "domains"),
            60.0,
            lambda: client.list_program_domains(access_token, limit=200),
        ))
        domain_lookup = {int(row.get("id") or 0): str(row.get("name") or "") for row in domains}
        return _normalize_campaign(created, domain_lookup)

async def _list_program_events_public(
    request,
    ctx,
    *,
    search: str = "",
    domain_id: str = "",
    type_id: str = "",
    status: str = "",
    location: str = "",
    domain_slug: str = "",
    event_mode: str = "",
    status_value: str = "",
) -> list[dict[str, Any]]:
    if await ProgramService.use_mock(request):
        return STORE.list_program_events(
            ctx.current_scope_path,
            search=search,
            domain_id=domain_id,
            type_id=type_id,
            status=status or status_value,
            location=location,
        )
    _domains_raw, domain_lookup, events = await ProgramService._live_maps(request, ctx)
    rows = events
    if search:
        term = search.lower().strip()
        rows = [
            row
            for row in rows
            if term in row["title"].lower()
            or term in row["program_type"].lower()
            or term in row["domain_name"].lower()
            or term in row["location"].lower()
        ]
    if domain_slug:
        rows = [row for row in rows if row.get("domain_name", "").lower().replace(" ", "_") == domain_slug]
    if domain_id:
        rows = [row for row in rows if row["domain_id"] == str(domain_id)]
    if type_id:
        rows = [row for row in rows if row["type_id"] == str(type_id)]
    if event_mode:
        rows = [row for row in rows if row["event_mode"] == event_mode]
    effective_status = status or status_value
    if effective_status:
        rows = [row for row in rows if row["status"] == effective_status]
    if location:
        rows = [row for row in rows if row["location"] == location or row["location_id"] == location]
    return rows


async def _list_program_campaigns_public(
    request,
    ctx,
    *,
    domain_slug: str = "",
    event_mode: str = "",
    status_value: str = "",
) -> list[dict[str, Any]]:
    if await ProgramService.use_mock(request):
        rows = await ProgramService._mock_campaigns(ctx)
        if domain_slug:
            rows = [row for row in rows if str(row["domain_name"]).lower().replace(" ", "_") == domain_slug]
        if event_mode:
            rows = [row for row in rows if row["event_mode"] == event_mode]
        if status_value:
            rows = [row for row in rows if row["status"] == status_value]
        return rows
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    scope_path = await ProgramService.effective_scope_path(request, ctx)
    domains_raw, domain_lookup, _events = await ProgramService._live_maps(request, ctx)
    _ = domains_raw
    try:
        campaigns_raw = await client.list_program_campaigns(
            access_token,
            scope_path=scope_path,
            program_domain=domain_slug or None,
            event_mode=event_mode or None,
            status_value=status_value or None,
            limit=200,
        )
    except AttributeError:
        return []
    return [_normalize_campaign(row, domain_lookup) for row in campaigns_raw]


async def _campaign_activity_public(request, ctx, campaign_id: str) -> dict[str, Any]:
    campaign = await maybe_await(ProgramService.get_campaign(request, ctx, campaign_id))
    if campaign is None:
        return {
            "events": [],
            "event_count": 0,
            "total_population": 0,
            "alpha_population": 0,
            "satellite_population": 0,
            "converts": 0,
            "newcomers": 0,
            "segment_breakdown": [],
            "assignments_total": 0,
            "assignments_approved": 0,
            "assignments_pending_approval": 0,
            "assignments_rejected": 0,
            "assignments_submitted": 0,
            "assignments_pending_submission": 0,
        }
    event_rows = [row for row in await maybe_await(ProgramService.list_events(request, ctx)) if row.get("campaign_id") == str(campaign_id)]
    event_ids = {row["event_id"] for row in event_rows}
    count_rows = [row for row in await maybe_await(ChurchDataService.list_counts(request, ctx)) if row.get("event_id") in event_ids]
    record_rows = [row for row in await maybe_await(ChurchDataService.list_records(request, ctx)) if row.get("event_id") in event_ids]
    worker_lookup = {row["worker_id"]: row for row in await maybe_await(PeopleService.list_workers(request, ctx))}
    assignment_rows: list[dict[str, Any]] = []
    for event in event_rows:
        assignment_rows.extend(await maybe_await(ProgramService.list_assignments(request, ctx, event["event_id"], worker_lookup=worker_lookup)))

    segment_totals: dict[str, int] = {}
    summary_by_event: list[dict[str, Any]] = []
    for event in event_rows:
        event_counts = [row for row in count_rows if row["event_id"] == event["event_id"]]
        event_records = [row for row in record_rows if row.get("event_id") == event["event_id"] or row.get("service") == event["title"]]
        event_assignments = [row for row in assignment_rows if row["event_id"] == event["event_id"]]
        population = sum(int(row["total"]) for row in event_counts)
        audience_segment = str(event.get("audience_segment") or "")
        if audience_segment:
            segment_totals[audience_segment] = segment_totals.get(audience_segment, 0) + population
        summary_by_event.append(
            {
                "event_id": event["event_id"],
                "title": event["title"],
                "date": event["date"],
                "location": event["location"],
                "population": population,
                "alpha_population": sum(int(row["total"]) for row in event_counts if row.get("source_role") == "alpha"),
                "satellite_population": sum(int(row["total"]) for row in event_counts if row.get("source_role") == "satellite"),
                "converts": sum(1 for row in event_records if row["record_type"] == "convert"),
                "newcomers": sum(1 for row in event_records if row["record_type"] == "newcomer"),
                "audience_segment": audience_segment,
                "assignment_total": len(event_assignments),
                "assignment_submitted": sum(1 for row in event_assignments if row["submission_completed"]),
            }
        )
    summary_by_event.sort(key=lambda row: (row["date"], row["title"]), reverse=True)
    assignments_total = len(assignment_rows)
    assignments_approved = sum(1 for row in assignment_rows if row["status"] == "approved")
    assignments_submitted = sum(1 for row in assignment_rows if row["submission_completed"])
    return {
        "events": summary_by_event,
        "event_count": len(event_rows),
        "total_population": sum(int(row["total"]) for row in count_rows),
        "alpha_population": sum(int(row["total"]) for row in count_rows if row.get("source_role") == "alpha"),
        "satellite_population": sum(int(row["total"]) for row in count_rows if row.get("source_role") == "satellite"),
        "converts": sum(1 for row in record_rows if row["record_type"] == "convert"),
        "newcomers": sum(1 for row in record_rows if row["record_type"] == "newcomer"),
        "segment_breakdown": [{"segment": segment, "population": total} for segment, total in sorted(segment_totals.items())],
        "assignments_total": assignments_total,
        "assignments_approved": assignments_approved,
        "assignments_pending_approval": sum(1 for row in assignment_rows if row["status"] == "pending"),
        "assignments_rejected": sum(1 for row in assignment_rows if row["status"] == "rejected"),
        "assignments_submitted": assignments_submitted,
        "assignments_pending_submission": max(assignments_approved - assignments_submitted, 0),
    }


ProgramService.list_events = staticmethod(_list_program_events_public)
ProgramService.list_campaigns = staticmethod(_list_program_campaigns_public)
ProgramService.list_assignments = staticmethod(ProgramService.list_event_assignments)
ProgramService.campaign_activity = staticmethod(_campaign_activity_public)
ProgramService._mock_campaigns = staticmethod(ProgramService._mock_events)

dual_mode_class(ProgramService)

__all__ = ["ProgramService"]
