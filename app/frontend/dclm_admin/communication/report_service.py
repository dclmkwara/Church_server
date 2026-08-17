from __future__ import annotations

import asyncio
import csv
import json
from datetime import UTC, datetime
from io import BytesIO, StringIO
from typing import Any

from openpyxl import Workbook

from ..backend import BackendClientError
from ..backend.config import get_backend_config
from ..mock_data import STORE
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .church_data_service import ChurchDataService
from .people_service import PeopleService
from .request_cache import request_cached
from .ttl_cache import ttl_cached
from .workflow_service import WorkflowService


def _scope_path(request, ctx) -> str:
    identity = AuthService.get_identity(request)
    if identity and identity.scope_path:
        return identity.scope_path
    return str(getattr(ctx, "current_scope_path", "") or "")


def _parse_date(value: Any) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    return raw.split("T", 1)[0]


def _month_label(value: Any) -> str:
    raw = str(value or "")
    if not raw:
        return "Unknown month"
    cleaned = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
        return parsed.strftime("%b %Y")
    except ValueError:
        return raw[:7]


def _summary_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("date") or ""), str(row.get("location") or ""))


def _normalize_summary_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": _parse_date(row.get("day")),
        "location": str(row.get("location_name") or row.get("location_id") or "Unknown location"),
        "event_title": "Count summary",
        "total": int(row.get("total_attendance") or 0),
        "submitted_by": f"{int(row.get('record_count') or 0)} record(s)",
        "men": int(row.get("total_men") or 0),
        "women": int(row.get("total_women") or 0),
        "youth_male": int(row.get("total_youth_male") or 0),
        "youth_female": int(row.get("total_youth_female") or 0),
        "boys": int(row.get("total_boys") or 0),
        "girls": int(row.get("total_girls") or 0),
        "record_count": int(row.get("record_count") or 0),
    }


def _normalize_financial_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": _month_label(row.get("month")),
        "location": str(row.get("location_name") or row.get("location_id") or "Unknown location"),
        "fund_type": "offering_and_tithe",
        "amount": float(row.get("total_amount") or 0),
        "method": "Mixed",
        "submitted_by": f"{int(row.get('transaction_count') or 0)} transaction(s)",
        "transaction_count": int(row.get("transaction_count") or 0),
    }


def _normalize_attendance_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": _parse_date(row.get("week")),
        "worker_name": str(row.get("location_name") or row.get("location_id") or "Unknown location"),
        "unit": "Scope summary",
        "event_title": "Attendance trend",
        "location": str(row.get("location_name") or row.get("location_id") or "Unknown location"),
        "status": str(row.get("status") or "present"),
        "worker_count": int(row.get("worker_count") or 0),
    }


def _normalize_series(payload: dict[str, Any]) -> list[tuple[str, int]]:
    rows = []
    for row in payload.get("data") or []:
        label = _parse_date(row.get("date")) or str(row.get("date") or "")
        value = row.get("value") or 0
        rows.append((label, int(float(value))))
    return rows


def _breakdown_level(scope_kind: str) -> str:
    mapping = {
        "global": "state",
        "continent": "state",
        "nation": "state",
        "state": "region",
        "region": "group",
        "group": "location",
        "location": "location",
    }
    return mapping.get(scope_kind, "location")


def _normalize_breakdown_rows(counts: dict[str, Any], finance: dict[str, Any], attendance: dict[str, Any]) -> list[dict[str, Any]]:
    bucket: dict[str, dict[str, Any]] = {}
    for row in counts.get("breakdown") or []:
        path = str(row.get("path") or "")
        bucket[path] = {
            "label": path,
            "counts_total": int(row.get("total") or 0),
            "finance_total": 0.0,
            "attendance_total": 0,
        }
    for row in finance.get("breakdown") or []:
        path = str(row.get("path") or "")
        bucket.setdefault(path, {"label": path, "counts_total": 0, "finance_total": 0.0, "attendance_total": 0})
        bucket[path]["finance_total"] = float(row.get("total") or 0)
    for row in attendance.get("breakdown") or []:
        path = str(row.get("path") or "")
        bucket.setdefault(path, {"label": path, "counts_total": 0, "finance_total": 0.0, "attendance_total": 0})
        bucket[path]["attendance_total"] = int(row.get("total") or 0)
    return list(bucket.values())


def _safe_sheet_name(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch not in r'[]:*?/\\')
    return (cleaned or "Sheet")[:31]


def _serialize_cell(value: Any) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, (list, dict, tuple, set)):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


def _scope_export_filename(ctx, suffix: str) -> str:
    scope_kind = str(getattr(ctx, "current_scope_kind", "scope") or "scope").replace("_", "-")
    scope_label = str(getattr(ctx, "current_scope_label", "export") or "export")
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in scope_label).strip("-")
    normalized = "-".join(part for part in normalized.split("-") if part) or "scope"
    timestamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"dclm-{scope_kind}-{normalized}-{timestamp}.{suffix}"


async def _build_operational_export_rows(request, ctx) -> list[tuple[str, list[dict[str, Any]]]]:
    from .organization_service import OrganizationService
    from .program_service import ProgramService

    datasets = await asyncio.gather(
        maybe_await(PeopleService.list_workers(request, ctx)),
        maybe_await(PeopleService.list_users(request, ctx)),
        maybe_await(PeopleService.list_members(request, ctx)),
        maybe_await(PeopleService.list_official_appointments(request, ctx)),
        maybe_await(OrganizationService.list_location_profiles(request, ctx)),
        maybe_await(PeopleService.list_fellowships(request)),
        maybe_await(ProgramService.list_campaigns(request, ctx)),
        maybe_await(ProgramService.list_events(request, ctx)),
        maybe_await(ChurchDataService.list_counts(request, ctx)),
        maybe_await(ChurchDataService.list_finance(request, ctx)),
        maybe_await(ChurchDataService.list_records(request, ctx)),
        maybe_await(ChurchDataService.list_attendance(request, ctx)),
    )
    named_datasets: list[tuple[str, list[dict[str, Any]]]] = [
        ("Workers", datasets[0]),
        ("Users", datasets[1]),
        ("Members", datasets[2]),
        ("Officials", datasets[3]),
        ("Locations", datasets[4]),
        ("Fellowships", datasets[5]),
        ("Campaigns", datasets[6]),
        ("Events", datasets[7]),
        ("Counts", datasets[8]),
        ("Finance", datasets[9]),
        ("Records", datasets[10]),
        ("Attendance", datasets[11]),
    ]
    return [(name, rows) for name, rows in named_datasets if rows]


async def _export_operational_csv(request, ctx) -> tuple[bytes, dict[str, str]]:
    datasets = await _build_operational_export_rows(request, ctx)
    flat_rows: list[dict[str, Any]] = []
    fieldnames = ["dataset"]
    seen_fields = {"dataset"}
    for dataset_name, rows in datasets:
        for row in rows:
            payload = {"dataset": dataset_name}
            for key, value in row.items():
                payload[str(key)] = _serialize_cell(value)
                if key not in seen_fields:
                    seen_fields.add(str(key))
                    fieldnames.append(str(key))
            flat_rows.append(payload)

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in flat_rows:
        writer.writerow(row)

    filename = _scope_export_filename(ctx, "csv")
    return (
        buffer.getvalue().encode("utf-8"),
        {
            "content-type": "text/csv; charset=utf-8",
            "content-disposition": f'attachment; filename="{filename}"',
        },
    )


async def _export_operational_excel(request, ctx) -> tuple[bytes, dict[str, str]]:
    datasets = await _build_operational_export_rows(request, ctx)
    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    for dataset_name, rows in datasets:
        sheet = workbook.create_sheet(title=_safe_sheet_name(dataset_name))
        fieldnames: list[str] = []
        for row in rows:
            for key in row.keys():
                key_text = str(key)
                if key_text not in fieldnames:
                    fieldnames.append(key_text)
        if not fieldnames:
            fieldnames = ["value"]
        sheet.append(fieldnames)
        for row in rows:
            sheet.append([_serialize_cell(row.get(field)) for field in fieldnames])

    output = BytesIO()
    workbook.save(output)
    filename = _scope_export_filename(ctx, "xlsx")
    return (
        output.getvalue(),
        {
            "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "content-disposition": f'attachment; filename="{filename}"',
        },
    )


class ReportService:
    @staticmethod
    async def _cached_payload(request, key: tuple[Any, ...], loader):
        return await request_cached(request, key, loader)

    @staticmethod
    async def export_report_csv(request) -> bool:
        return get_backend_config().enabled and bool(AuthService.get_access_token(request))

    @staticmethod
    async def live_enabled(request) -> bool:
        if get_backend_config().enabled:
            if not AuthService.get_access_token(request):
                raise BackendClientError("Backend session required for reports.")
            return False
        return True

    @staticmethod
    async def use_mock(request, ctx) -> dict[str, Any]:
        if await ReportService.use_mock(request):
            summary = STORE.dashboard_summary(ctx.current_scope_path, ctx.level)
            counts_summary = STORE.counts_summary(ctx.current_scope_path)
            return {
                "workers_total": summary["workers_total"],
                "pending_items": summary["pending_items"],
                "latest_total": counts_summary["latest_total"],
                "locations_reporting": counts_summary["locations_reporting"],
            }
        counts_summary = await ChurchDataService.count_summary(request, ctx)
        return {
            "workers_total": len(await PeopleService.list_workers(request, ctx)),
            "pending_items": await WorkflowService.pending_item_count(request, ctx),
            "latest_total": counts_summary["latest_total"],
            "locations_reporting": counts_summary["locations_reporting"],
        }

    @staticmethod
    async def export_report_excel(request, ctx) -> list[dict[str, Any]]:
        if await ReportService.use_mock(request):
            return STORE.list_counts(ctx.current_scope_path)[:8]
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        try:
            payload = await ReportService._cached_payload(
                request,
                ("reports", "summary", _scope_path(request, ctx)),
                lambda: ttl_cached(
                    ("reports", "summary", _scope_path(request, ctx)),
                    45.0,
                    lambda: client.get_report_summary(access_token, scope_path=_scope_path(request, ctx)),
                ),
            )
        except BackendClientError:
            return []
        rows = [_normalize_summary_row(row) for row in payload]
        return sorted(rows, key=_summary_sort_key, reverse=True)[:8]

    @staticmethod
    async def get_report_summary(request, ctx) -> dict[str, Any]:
        return await ChurchDataService.finance_summary(request, ctx) if await ReportService.live_enabled(request) else STORE.finance_summary(ctx.current_scope_path)

    @staticmethod
    async def get_financial_summary(request, ctx) -> list[dict[str, Any]]:
        if await ReportService.use_mock(request):
            return STORE.list_finance(ctx.current_scope_path)[:8]
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        try:
            payload = await ReportService._cached_payload(
                request,
                ("reports", "financial", _scope_path(request, ctx)),
                lambda: ttl_cached(
                    ("reports", "financial", _scope_path(request, ctx)),
                    45.0,
                    lambda: client.get_report_financial(access_token, scope_path=_scope_path(request, ctx)),
                ),
            )
        except BackendClientError:
            return []
        rows = [_normalize_financial_row(row) for row in payload]
        return sorted(rows, key=_summary_sort_key, reverse=True)[:8]

    @staticmethod
    async def get_report_attendance(request, ctx) -> dict[str, Any]:
        return await ChurchDataService.attendance_summary(request, ctx) if await ReportService.live_enabled(request) else STORE.attendance_summary(ctx.current_scope_path)

    @staticmethod
    async def get_attendance_summary(request, ctx) -> list[dict[str, Any]]:
        if await ReportService.use_mock(request):
            return STORE.list_attendance(ctx.current_scope_path)[:8]
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        try:
            payload = await client.get_report_attendance(access_token, scope_path=_scope_path(request, ctx))
        except BackendClientError:
            return []
        rows = [_normalize_attendance_row(row) for row in payload]
        return sorted(rows, key=lambda row: (row["date"], row["location"], row["status"]), reverse=True)[:8]

    @staticmethod
    async def get_report_timeseries(request, ctx) -> list[tuple[str, int]]:
        if await ReportService.use_mock(request):
            bucket: dict[str, int] = {}
            for row in STORE.list_counts(ctx.current_scope_path):
                bucket[row["date"]] = bucket.get(row["date"], 0) + row["total"]
            return sorted(bucket.items())
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        try:
            payload = await ReportService._cached_payload(
                request,
                ("reports", "timeseries", "counts", _scope_path(request, ctx)),
                lambda: ttl_cached(
                    ("reports", "timeseries", "counts", _scope_path(request, ctx)),
                    45.0,
                    lambda: client.get_report_timeseries(access_token, metric="counts", scope_path=_scope_path(request, ctx)),
                ),
            )
        except BackendClientError:
            return []
        return _normalize_series(payload)

    @staticmethod
    async def get_report_breakdown(request, ctx) -> list[tuple[str, int]]:
        if await ReportService.use_mock(request):
            bucket: dict[str, int] = {}
            for row in STORE.list_finance(ctx.current_scope_path):
                bucket[row["date"]] = bucket.get(row["date"], 0) + int(row["amount"])
            return sorted(bucket.items())
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        try:
            payload = await ReportService._cached_payload(
                request,
                ("reports", "timeseries", "offerings", _scope_path(request, ctx)),
                lambda: ttl_cached(
                    ("reports", "timeseries", "offerings", _scope_path(request, ctx)),
                    45.0,
                    lambda: client.get_report_timeseries(access_token, metric="offerings", scope_path=_scope_path(request, ctx)),
                ),
            )
        except BackendClientError:
            return []
        return _normalize_series(payload)

    @staticmethod
    async def get_report_anomalies(request, ctx) -> list[tuple[str, int]]:
        if await ReportService.use_mock(request):
            bucket: dict[str, int] = {}
            for row in STORE.list_attendance(ctx.current_scope_path):
                bucket[row["date"]] = bucket.get(row["date"], 0) + 1
            return sorted(bucket.items())
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        try:
            payload = await ReportService._cached_payload(
                request,
                ("reports", "timeseries", "attendance", _scope_path(request, ctx)),
                lambda: ttl_cached(
                    ("reports", "timeseries", "attendance", _scope_path(request, ctx)),
                    45.0,
                    lambda: client.get_report_timeseries(access_token, metric="attendance", scope_path=_scope_path(request, ctx)),
                ),
            )
        except BackendClientError:
            return []
        return _normalize_series(payload)

    @staticmethod
    async def get_report_growth(request, ctx) -> list[dict[str, Any]]:
        if await ReportService.use_mock(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        level = _breakdown_level(ctx.current_scope_kind)
        try:
            counts = await ReportService._cached_payload(
                request,
                ("reports", "breakdown", "counts", level),
                lambda: ttl_cached(
                    ("reports", "breakdown", "counts", level),
                    45.0,
                    lambda: client.get_report_breakdown(access_token, metric="counts", level=level),
                ),
            )
            finance = await ReportService._cached_payload(
                request,
                ("reports", "breakdown", "offerings", level),
                lambda: ttl_cached(
                    ("reports", "breakdown", "offerings", level),
                    45.0,
                    lambda: client.get_report_breakdown(access_token, metric="offerings", level=level),
                ),
            )
            attendance = await ReportService._cached_payload(
                request,
                ("reports", "breakdown", "attendance", level),
                lambda: ttl_cached(
                    ("reports", "breakdown", "attendance", level),
                    45.0,
                    lambda: client.get_report_breakdown(access_token, metric="attendance", level=level),
                ),
            )
        except BackendClientError:
            return []
        return _normalize_breakdown_rows(counts, finance, attendance)

    @staticmethod
    async def get_population_statistics(request, ctx) -> list[dict[str, Any]]:
        if await ReportService.use_mock(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        try:
            payload = await ReportService._cached_payload(
                request,
                ("reports", "growth", "counts"),
                lambda: ttl_cached(
                    ("reports", "growth", "counts"),
                    45.0,
                    lambda: client.get_report_growth(access_token, metric="counts"),
                ),
            )
        except BackendClientError:
            return []
        return [
            {
                "period": str(row.get("period") or ""),
                "value": int(row.get("value") or 0),
                "growth": float(row.get("growth_rate") or 0),
            }
            for row in payload.get("data") or []
        ]

    @staticmethod
    async def export_report_csv(request, ctx) -> list[dict[str, Any]]:
        if not await ReportService.live_enabled(request):
            return []
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        try:
            payload = await ReportService._cached_payload(
                request,
                ("reports", "anomalies", "counts"),
                lambda: ttl_cached(
                    ("reports", "anomalies", "counts"),
                    45.0,
                    lambda: client.get_report_anomalies(access_token, metric="counts"),
                ),
            )
        except BackendClientError:
            return []
        return [
            {
                "title": f"Attendance unusual at {row.get('location') or 'Unknown location'}",
                "detail": f"{row.get('date') or 'Unknown date'} recorded {row.get('value') or 0}, outside the recent average.",
                "status": "warning",
            }
            for row in payload.get("anomalies") or []
        ]

    @staticmethod
    async def export_report_excel(request) -> dict[str, Any] | None:
        if not await ReportService.live_enabled(request):
            return None
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        return await client.refresh_reports(access_token)

    @staticmethod
    async def export_report_pdf(request, ctx, *, report_type: str, export_format: str) -> tuple[bytes, dict[str, str]] | None:
        if not await ReportService.live_enabled(request):
            return None
        if report_type == "operational_scope":
            if export_format == "csv":
                return await _export_operational_csv(request, ctx)
            if export_format == "excel":
                return await _export_operational_excel(request, ctx)
            raise ValueError("Operational scope export supports CSV and Excel only")
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        scope_path = _scope_path(request, ctx)
        if export_format == "csv":
            return await client.export_report_csv(access_token, report_type=report_type, scope_path=scope_path)
        if export_format == "excel":
            return await client.export_report_excel(access_token, report_type=report_type)
        if export_format == "pdf":
            return await client.export_report_pdf(access_token, report_type=report_type)
        raise ValueError("Unsupported export format")

async def _report_use_mock(request) -> bool:
    if get_backend_config().enabled:
        if not AuthService.get_access_token(request):
            raise BackendClientError("Backend session required for reports.")
        return False
    return True


async def _report_live_enabled(request) -> bool:
    return get_backend_config().enabled and bool(AuthService.get_access_token(request))


async def _summary_metrics_public(request, ctx) -> dict[str, Any]:
    if await _report_use_mock(request):
        summary = STORE.dashboard_summary(ctx.current_scope_path, ctx.level)
        counts_summary = STORE.counts_summary(ctx.current_scope_path)
        return {
            "workers_total": summary["workers_total"],
            "pending_items": summary["pending_items"],
            "latest_total": counts_summary["latest_total"],
            "locations_reporting": counts_summary["locations_reporting"],
        }
    counts_summary = await ChurchDataService.count_summary(request, ctx)
    return {
        "workers_total": len(await PeopleService.list_workers(request, ctx)),
        "pending_items": await WorkflowService.pending_item_count(request, ctx),
        "latest_total": counts_summary["latest_total"],
        "locations_reporting": counts_summary["locations_reporting"],
    }


async def _summary_rows_public(request, ctx) -> list[dict[str, Any]]:
    if await _report_use_mock(request):
        return STORE.list_counts(ctx.current_scope_path)[:8]
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    rows = await client.get_report_summary(access_token, scope_path=_scope_path(request, ctx))
    return sorted([_normalize_summary_row(row) for row in rows], key=_summary_sort_key, reverse=True)


async def _growth_rows_public(request, ctx) -> list[dict[str, Any]]:
    if await _report_use_mock(request):
        return []
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    payload = await client.get_report_growth(access_token, metric="counts")
    return [
        {"period": str(row.get("period") or ""), "value": int(row.get("value") or 0), "growth": float(row.get("growth_rate") or 0)}
        for row in payload.get("data") or []
    ]


ReportService.live_enabled = staticmethod(_report_live_enabled)
ReportService.use_mock = staticmethod(_report_use_mock)
ReportService.summary_metrics = staticmethod(_summary_metrics_public)
ReportService.summary_rows = staticmethod(_summary_rows_public)
ReportService.growth_rows = staticmethod(_growth_rows_public)
ReportService.financial_summary = staticmethod(ReportService.get_report_summary)
ReportService.financial_rows = staticmethod(ReportService.get_financial_summary)
ReportService.attendance_summary = staticmethod(ReportService.get_report_attendance)
ReportService.attendance_rows = staticmethod(ReportService.get_attendance_summary)
ReportService.counts_series = staticmethod(ReportService.get_report_timeseries)
ReportService.finance_series = staticmethod(ReportService.get_report_breakdown)
ReportService.attendance_series = staticmethod(ReportService.get_report_anomalies)
ReportService.breakdown_rows = staticmethod(ReportService.get_report_growth)
ReportService.anomaly_rows = staticmethod(ReportService.export_report_csv)
ReportService.refresh = staticmethod(ReportService.export_report_excel)
ReportService.export = staticmethod(ReportService.export_report_pdf)
ReportService.get_report_growth = staticmethod(_growth_rows_public)

dual_mode_class(ReportService)

__all__ = ["ReportService"]
