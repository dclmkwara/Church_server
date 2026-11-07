"""Scope-safe grouped reads for dated program occurrences."""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.filters import scope_filter, scope_or_ancestor_filter
from app.models.counts import Count
from app.models.location import Location
from app.models.programs import ProgramDomain, ProgramEvent, ProgramType
from app.models.records import Record


async def get_program_occurrences(
    db: AsyncSession,
    *,
    scope_path: str,
    domain: str | None = None,
    program_type: str | None = None,
    program_level: str | None = None,
    event_id: UUID | None = None,
    campaign_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    include_pending: bool = False,
) -> dict[str, Any]:
    query = (
        select(ProgramEvent, ProgramType, ProgramDomain)
        .options(selectinload(ProgramEvent.campaign))
        .join(ProgramType, ProgramType.id == ProgramEvent.program_type_id)
        .join(ProgramDomain, ProgramDomain.id == ProgramType.domain_id)
        .where(
            ProgramEvent.is_deleted.is_(False), ProgramType.is_deleted.is_(False),
            ProgramDomain.is_deleted.is_(False), scope_or_ancestor_filter(ProgramEvent.path, scope_path),
        )
    )
    if domain:
        query = query.where(or_(ProgramDomain.slug == domain, ProgramDomain.name.ilike(domain)))
    if program_type:
        query = query.where(or_(ProgramType.slug == program_type, ProgramType.name.ilike(program_type)))
    if event_id:
        query = query.where(ProgramEvent.id == event_id)
    if campaign_id:
        query = query.where(ProgramEvent.campaign_id == campaign_id)
    if date_from:
        query = query.where(ProgramEvent.date >= date_from)
    if date_to:
        query = query.where(ProgramEvent.date <= date_to)
    if program_level:
        query = query.where(func.lower(ProgramEvent.reporting_scope) == program_level.lower())

    event_rows = (await db.execute(query.order_by(ProgramEvent.date, ProgramType.name))).all()
    event_ids = [row[0].id for row in event_rows]
    counts_by_event: dict[str, dict[str, Any]] = {}
    records_by_event: dict[str, dict[str, Any]] = {}
    detail_by_event: dict[str, list[dict[str, Any]]] = {}
    if event_ids:
        counted_statuses = ["approved"] + (["pending"] if include_pending else [])
        count_query = (
            select(
                Count.event_id, Count.source_role,
                func.sum(case((Count.status == "approved", Count.total), else_=0)).label("approved_total"),
                func.sum(case((Count.status == "pending", Count.total), else_=0)).label("pending_total"),
                func.sum(case((Count.status.in_(["rejected", "returned"]), 1), else_=0)).label("returned_rows"),
                func.sum(case((Count.status == "approved", 1), else_=0)).label("approved_rows"),
                func.sum(case((Count.status == "pending", 1), else_=0)).label("pending_rows"),
                func.sum(case((Count.status.in_(counted_statuses), Count.total), else_=0)).label("counted_total"),
                func.count(Count.id).label("row_count"),
            )
            .where(Count.event_id.in_(event_ids), Count.is_deleted.is_(False), scope_filter(Count.path, scope_path))
            .group_by(Count.event_id, Count.source_role)
        )
        for row in (await db.execute(count_query)).all():
            event_key = str(row.event_id)
            item = counts_by_event.setdefault(event_key, {"sources": {}, "approved_population": 0, "pending_population": 0, "counted_population": 0, "returned_rows": 0, "approved_rows": 0, "pending_rows": 0, "row_count": 0})
            role = row.source_role or "regular"
            item["sources"][role] = int(row.counted_total or 0)
            for key, column in (("approved_population", "approved_total"), ("pending_population", "pending_total"), ("counted_population", "counted_total"), ("returned_rows", "returned_rows"), ("approved_rows", "approved_rows"), ("pending_rows", "pending_rows"), ("row_count", "row_count")):
                item[key] += int(getattr(row, column, 0) or 0)

        detail_query = (
            select(
                Count.event_id, Count.location_id, Location.location_name, Location.path,
                Count.source_role,
                func.sum(case((Count.status == "approved", Count.total), else_=0)).label("approved_total"),
                func.sum(case((Count.status == "pending", Count.total), else_=0)).label("pending_total"),
                func.count(Count.id).label("row_count"),
            )
            .join(Location, Location.location_id == Count.location_id)
            .where(Count.event_id.in_(event_ids), Count.is_deleted.is_(False), scope_filter(Count.path, scope_path))
            .group_by(Count.event_id, Count.location_id, Location.location_name, Location.path, Count.source_role)
        )
        for row in (await db.execute(detail_query)).all():
            detail_by_event.setdefault(str(row.event_id), []).append({
                "location_id": str(row.location_id), "location": row.location_name,
                "location_path": str(row.path), "source_role": row.source_role or "regular",
                "approved_population": int(row.approved_total or 0),
                "pending_population": int(row.pending_total or 0), "count_rows": int(row.row_count or 0),
            })

        record_query = (
            select(Record.event_id, Record.record_type, Record.source_role, func.count(Record.id).label("total"))
            .where(Record.event_id.in_(event_ids), Record.is_deleted.is_(False), Record.status == "approved", scope_filter(Record.path, scope_path))
            .group_by(Record.event_id, Record.record_type, Record.source_role)
        )
        for row in (await db.execute(record_query)).all():
            record_group = records_by_event.setdefault(str(row.event_id), {})
            record_group[str(row.record_type)] = record_group.get(str(row.record_type), 0) + int(row.total or 0)
            record_sources = record_group.setdefault("sources", {})
            role = row.source_role or "regular"
            record_sources[role] = record_sources.get(role, 0) + int(row.total or 0)

    occurrences = []
    empty_counts = {"sources": {}, "approved_population": 0, "pending_population": 0, "counted_population": 0, "returned_rows": 0, "approved_rows": 0, "pending_rows": 0, "row_count": 0}
    for event, ptype, pdomain in event_rows:
        key = str(event.id)
        totals = counts_by_event.get(key, empty_counts)
        records = records_by_event.get(key, {})
        campaign = event.campaign
        day_number = (
            (event.date - campaign.start_date).days + 1
            if campaign and campaign.event_mode in {"retreat", "crusade"}
            else None
        )
        occurrences.append({
            "event_id": key, "campaign_id": str(event.campaign_id) if event.campaign_id else None,
            "campaign_title": campaign.title if campaign else None,
            "campaign_mode": event.event_mode,
            "campaign_start_date": campaign.start_date.isoformat() if campaign else None,
            "date": event.date.isoformat(), "day_number": day_number,
            "title": event.title or ptype.name, "domain": pdomain.name, "domain_slug": pdomain.slug,
            "program_type": ptype.name, "program_type_slug": ptype.slug,
            "program_level": event.reporting_scope, "scope_path": str(event.path),
            "alpha_location_id": str(event.alpha_location_id) if event.alpha_location_id else None,
            "is_alpha_event": bool(event.is_alpha_event), "approval_status": event.approval_status,
            "counted_population": totals["counted_population"], "approved_population": totals["approved_population"],
            "pending_population": totals["pending_population"], "returned_rows": totals["returned_rows"],
            "count_rows": totals["row_count"], "sources": totals["sources"],
            "location_reports": detail_by_event.get(key, []),
            "converts": records.get("convert", 0), "newcomers": records.get("newcomer", 0),
            "record_sources": records.get("sources", {}),
            "record_state": "reported" if records.get("convert", 0) or records.get("newcomer", 0) else "no_report",
            "report_state": "counted" if totals["approved_rows"] or include_pending and totals["pending_rows"] else "pending" if totals["pending_rows"] else "returned" if totals["returned_rows"] else "no_report",
        })
    return {"scope_path": scope_path, "include_pending": include_pending, "occurrences": occurrences}
