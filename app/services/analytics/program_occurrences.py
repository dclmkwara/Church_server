"""Scope-safe grouped reads for dated program occurrences."""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.filters import scope_filter, scope_or_ancestor_filter
from app.models.counts import Count, CountGroup
from app.models.location import Group, Location, Region, State
from app.models.programs import ProgramDomain, ProgramEvent, ProgramType
from app.models.records import Record
from app.services.analytics.program_config import reporting_now
from app.services.analytics.sunday_worship import receipt_state


async def get_program_occurrences(
    db: AsyncSession,
    *,
    scope_path: str,
    domain: str | None = None,
    program_type: str | None = None,
    program_level: str | None = None,
    event_id: UUID | None = None,
    campaign_id: UUID | None = None,
    compare_campaign_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    include_pending: bool = False,
) -> dict[str, Any]:
    scope_depth = len(scope_path.split("."))
    can_view_alpha = scope_depth == 3
    query = (
        select(ProgramEvent, ProgramType, ProgramDomain)
        .options(selectinload(ProgramEvent.campaign))
        .join(ProgramType, ProgramType.id == ProgramEvent.program_type_id)
        .join(ProgramDomain, ProgramDomain.id == ProgramType.domain_id)
        .where(
            ProgramEvent.is_deleted.is_(False), ProgramEvent.approval_status == "approved", ProgramType.is_deleted.is_(False),
            ProgramDomain.is_deleted.is_(False),
            # Include events scoped beneath the selected jurisdiction and
            # combined events held by an ancestor jurisdiction.
            or_(scope_filter(ProgramEvent.path, scope_path), scope_or_ancestor_filter(ProgramEvent.path, scope_path)),
        )
    )
    if domain:
        query = query.where(or_(ProgramDomain.slug == domain, ProgramDomain.name.ilike(domain)))
    if program_type:
        query = query.where(or_(ProgramType.slug == program_type, ProgramType.name.ilike(program_type)))
    if event_id:
        query = query.where(ProgramEvent.id == event_id)
    if campaign_id:
        query = query.where(ProgramEvent.campaign_id.in_([v for v in (campaign_id, compare_campaign_id) if v]))
    elif compare_campaign_id:
        query = query.where(ProgramEvent.campaign_id == compare_campaign_id)
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
        count_query = (
            select(Count, Location.location_name, Location.path, CountGroup.state, CountGroup.service_id)
            .join(Location, Location.location_id == Count.location_id)
            .outerjoin(CountGroup, CountGroup.id == Count.count_group_id)
            .where(Count.event_id.in_(event_ids), Count.is_deleted.is_(False), scope_filter(Count.path, scope_path))
        )
        raw_rows = list((await db.execute(count_query)).all())
        logical_groups: dict[tuple[Any, ...], list[tuple[Any, str, str, str | None, str | None]]] = {}
        for raw_row in raw_rows:
            # Four-column rows occur in legacy test adapters; live SQL returns
            # the joined group state and service identifier as columns 4 and 5.
            count, location_name, location_path = raw_row[:3]
            group_state = raw_row[3] if len(raw_row) > 3 else None
            service_id = raw_row[4] if len(raw_row) > 4 else None
            if count.count_mode:
                group_key = ("split", str(count.count_group_id or ""), str(count.location_id), count.program_type_id, count.date.date())
                if not count.count_group_id:
                    group_key += (str(count.event_id),)
            else:
                # Legacy rows retain their historical additive behavior.
                group_key = ("legacy", str(count.id))
            logical_groups.setdefault(group_key, []).append((count, location_name, str(location_path), group_state, service_id))

        for group_rows in logical_groups.values():
            first, location_name, location_path, group_state, service_id = group_rows[0]
            modes = {str(item[0].count_mode or "").lower() for item in group_rows if item[0].count_mode}
            statuses = {str(item[0].status or "pending").lower() for item in group_rows}
            single_count = sum(1 for item in group_rows if item[0].count_mode == "single")
            conflict = bool(modes) and (
                len(modes) > 1 or ("single" in modes and single_count != 1)
                or len(statuses) > 1 or group_state == "conflict"
            )
            status = next(iter(statuses)) if len(statuses) == 1 else "conflict"
            event_key = str(first.event_id)
            role = first.source_role or "regular"
            total = sum(int(item[0].total or 0) for item in group_rows)
            # Count rows are counted as one reporter group; raw row count remains
            # available for the Location and Group detail view.
            item = counts_by_event.setdefault(event_key, {"sources": {}, "approved_population": 0, "pending_population": 0, "counted_population": 0, "service_totals": {}, "returned_rows": 0, "approved_rows": 0, "pending_rows": 0, "row_count": 0, "conflict_rows": 0})
            detail = {
                "location_id": str(first.location_id), "location": location_name,
                "location_path": location_path, "program_scope_path": str(first.program_scope_path or first.path),
                "source_role": role, "service_id": str(service_id or "legacy"), "approved_population": 0, "pending_population": 0,
                "count_rows": len(group_rows), "approved_rows": 0, "pending_rows": 0,
                "returned_rows": 0, "conflict_rows": 0,
            }
            if conflict:
                item["conflict_rows"] += 1
                detail["conflict_rows"] = 1
            elif status == "approved":
                item["approved_population"] += total
                item["counted_population"] += total
                item["approved_rows"] += 1
                item["sources"][role] = item["sources"].get(role, 0) + total
                item["service_totals"][str(service_id or "legacy")] = item["service_totals"].get(str(service_id or "legacy"), 0) + total
                detail["approved_population"] = total
                detail["approved_rows"] = 1
            elif status == "pending":
                item["pending_population"] += total
                if include_pending:
                    item["counted_population"] += total
                    item["sources"][role] = item["sources"].get(role, 0) + total
                    item["service_totals"][str(service_id or "legacy")] = item["service_totals"].get(str(service_id or "legacy"), 0) + total
                item["pending_rows"] += 1
                detail["pending_population"] = total
                detail["pending_rows"] = 1
            elif status in {"rejected", "returned"}:
                item["returned_rows"] += 1
                detail["returned_rows"] = 1
            item["row_count"] += len(group_rows)
            detail_by_event.setdefault(event_key, []).append(detail)

        counted_record_statuses = ["approved"] + (["pending"] if include_pending else [])
        record_scope_clauses = [Record.event_id.in_(event_ids), Record.is_deleted.is_(False),
                                Record.status.in_(counted_record_statuses), scope_filter(Record.path, scope_path)]
        if not can_view_alpha:
            record_scope_clauses.append(Record.source_role != "alpha")
        record_query = select(
            Record.event_id, Record.location_id, Location.location_name, Location.path,
            Record.record_type, Record.source_role, Record.status,
            func.count(Record.id).label("total"),
        ).outerjoin(Location, Location.location_id == Record.location_id).where(*record_scope_clauses).group_by(
            Record.event_id, Record.location_id, Location.location_name, Location.path,
            Record.record_type, Record.source_role, Record.status,
        )
        for row in (await db.execute(record_query)).all():
            record_group = records_by_event.setdefault(str(row.event_id), {})
            record_group[str(row.record_type)] = record_group.get(str(row.record_type), 0) + int(row.total or 0)
            record_sources = record_group.setdefault("sources", {})
            role = row.source_role or "regular"
            record_sources[role] = record_sources.get(role, 0) + int(row.total or 0)
            record_group.setdefault("record_reports", []).append({
                "location_id": str(getattr(row, "location_id", "") or "") or None,
                "location": getattr(row, "location_name", None),
                "location_path": str(getattr(row, "path", "") or "") or None,
                "record_type": str(row.record_type), "source_role": role,
                "status": str(getattr(row, "status", "approved")), "count": int(row.total or 0),
            })

    # Event coverage uses event-specific reporting units. Locations are read
    # once for the requested scope; lifecycle dates are applied per occurrence.
    event_modes = {row[0].campaign.event_mode if row[0].campaign else row[0].event_mode for row in event_rows}
    locations_by_id: dict[str, dict[str, Any]] = {}
    child_nodes: list[dict[str, str]] = []
    scope_names: dict[str, str] = {}
    if event_modes.intersection({"crusade", "retreat"}):
        if "crusade" in event_modes:
            location_result = await db.execute(
                select(Location.location_id, Location.location_name, Location.path, Location.is_active,
                       Location.opened_on, Location.closed_on).where(scope_filter(Location.path, scope_path))
            )
            for row in location_result.all():
                locations_by_id[str(row.location_id)] = {
                    "location_id": str(row.location_id), "name": row.location_name, "path": str(row.path),
                    "is_active": bool(row.is_active), "opened_on": row.opened_on, "closed_on": row.closed_on,
                }
        if scope_depth in {3, 4, 5, 6}:
            # One SQL round trip returns ancestor labels for the breadcrumb and
            # visible reporting children for the drill table. This replaces the
            # full hierarchy tree read (which also queried workers and every
            # hierarchy table separately).
            ancestor_paths = [".".join(scope_path.split(".")[:depth]) for depth in range(3, scope_depth + 1)]
            scope_nodes_query = union_all(
                select(State.state_name.label("name"), State.path.label("path")).where(or_(scope_filter(State.path, scope_path), State.path.in_(ancestor_paths))),
                select(Region.region_name.label("name"), Region.path.label("path")).where(or_(scope_filter(Region.path, scope_path), Region.path.in_(ancestor_paths))),
                select(Group.group_name.label("name"), Group.path.label("path")).where(or_(scope_filter(Group.path, scope_path), Group.path.in_(ancestor_paths))),
                select(Location.location_name.label("name"), Location.path.label("path")).where(or_(scope_filter(Location.path, scope_path), Location.path.in_(ancestor_paths))),
            ).order_by("path")
            node_rows = (await db.execute(scope_nodes_query)).all()
            scope_names = {str(path): str(name) for name, path in node_rows}
            child_depth = scope_depth + 1
            child_nodes = [{"name": name, "path": str(path)} for name, path in node_rows if len(str(path).split(".")) == child_depth]
            if scope_depth == 6 and not child_nodes:
                child_nodes = [{"name": scope_names.get(scope_path, ""), "path": scope_path}]

    def _location_active(location: dict[str, Any], when: date) -> bool:
        was_open = location["is_active"] or (location["closed_on"] is not None and location["closed_on"] > when)
        return bool(was_open and (location["opened_on"] is None or location["opened_on"] <= when)
                    and (location["closed_on"] is None or location["closed_on"] > when))

    now_local = reporting_now()
    local_today = now_local.date()
    occurrences = []
    empty_counts = {"sources": {}, "approved_population": 0, "pending_population": 0, "counted_population": 0, "service_totals": {}, "returned_rows": 0, "approved_rows": 0, "pending_rows": 0, "row_count": 0}
    for event, ptype, pdomain in event_rows:
        key = str(event.id)
        totals = counts_by_event.get(key, empty_counts)
        records = records_by_event.get(key, {})
        campaign = event.campaign
        campaign_mode = campaign.event_mode if campaign else event.event_mode
        day_number = (
            (event.date - campaign.start_date).days + 1
            if campaign and campaign_mode in {"retreat", "crusade"}
            else None
        )
        event_details = detail_by_event.get(key, [])
        # Alpha is State-only. Source-role suppression is performed before
        # returning totals so lower scopes cannot infer the Alpha figure.
        if not can_view_alpha:
            event_details = [detail for detail in event_details if detail["source_role"] != "alpha"]
            visible_sources = {role: value for role, value in totals["sources"].items() if role != "alpha"}
        else:
            visible_sources = dict(totals["sources"])

        if campaign and campaign_mode == "retreat":
            unit_key = str(event.path)
            unit_rows = [detail for detail in event_details if detail["program_scope_path"] == unit_key]
            expected = 1
            reported = any(detail["approved_rows"] or detail["pending_rows"] for detail in unit_rows)
            approved_report = any(detail["approved_rows"] for detail in unit_rows)
            pending_report = any(detail["pending_rows"] for detail in unit_rows)
            conflict_report = any(detail.get("conflict_rows") for detail in unit_rows)
            returned_report = any(detail["returned_rows"] for detail in unit_rows) and not (approved_report or pending_report)
            unit_state = "conflict" if conflict_report else "reported" if reported else "returned" if returned_report else "upcoming" if event.date > local_today else receipt_state(event.date, now_local, received=False)
            coverage = {"label": "Regions reporting", "expected": expected, "reported": int(reported),
                        "pending": int(pending_report), "returned": int(returned_report), "conflict": int(conflict_report), "unit_path": unit_key}
            region_name = next((n["name"] for n in child_nodes if n["path"] == unit_key), unit_key.split(".")[-1])
            unit_reports = [{"name": region_name, "path": unit_key, "state": unit_state,
                             "population": sum(d["approved_population"] + (d["pending_population"] if include_pending else 0) for d in unit_rows),
                             "approved_population": sum(d["approved_population"] for d in unit_rows),
                             "pending_population": sum(d["pending_population"] for d in unit_rows),
                             "returned_rows": sum(d["returned_rows"] for d in unit_rows),
                             "conflict_rows": sum(d.get("conflict_rows", 0) for d in unit_rows)}]
        elif campaign and campaign_mode == "crusade":
            alpha_id = str(event.alpha_location_id or (campaign.alpha_location_id if campaign else "") or "")
            expected_locations = [loc for loc in locations_by_id.values() if _location_active(loc, event.date)
                                  and loc["location_id"] != alpha_id]
            location_by_id = {str(d["location_id"]): d for d in event_details}
            satellite_reports = 0
            pending_satellites = 0
            returned_satellites = 0
            conflict_satellites = 0
            child_totals: dict[str, dict[str, Any]] = {child["path"]: {"name": child["name"], "path": child["path"], "expected": 0, "reported": 0, "pending": 0, "returned": 0, "conflict": 0, "population": 0} for child in child_nodes}
            unit_reports = []
            for location in expected_locations:
                report = location_by_id.get(location["location_id"])
                if report and report["source_role"] == "satellite" and (report["approved_rows"] or report["pending_rows"]):
                    satellite_reports += 1
                    pending_satellites += int(bool(report["pending_rows"] and not report["approved_rows"]))
                    population = report["approved_population"] + (report["pending_population"] if include_pending else 0)
                    prefix = ".".join(location["path"].split(".")[:scope_depth + 1])
                    if prefix in child_totals:
                        child_totals[prefix]["reported"] += 1
                        child_totals[prefix]["pending"] += int(bool(report["pending_rows"] and not report["approved_rows"]))
                        child_totals[prefix]["population"] += population
                    unit_reports.append({"name": location["name"], "path": location["path"],
                                         "state": "reported", "population": population})
                elif report and report["returned_rows"]:
                    returned_satellites += 1
                    prefix = ".".join(location["path"].split(".")[:scope_depth + 1])
                    if prefix in child_totals:
                        child_totals[prefix]["returned"] += 1
                    unit_reports.append({"name": location["name"], "path": location["path"],
                                         "state": "returned", "population": None})
                elif report and report.get("conflict_rows"):
                    conflict_satellites += 1
                    prefix = ".".join(location["path"].split(".")[:scope_depth + 1])
                    if prefix in child_totals:
                        child_totals[prefix]["conflict"] += 1
                    unit_reports.append({"name": location["name"], "path": location["path"],
                                         "state": "conflict", "population": None})
                else:
                    state = "upcoming" if event.date > local_today else receipt_state(event.date, now_local, received=False)
                    unit_reports.append({"name": location["name"], "path": location["path"], "state": state, "population": None})
                prefix = ".".join(location["path"].split(".")[:scope_depth + 1])
                if prefix in child_totals:
                    child_totals[prefix]["expected"] += 1
            alpha_rows = [d for d in event_details if d["source_role"] == "alpha"] if can_view_alpha else []
            alpha_reported = bool(alpha_rows and any(d["approved_rows"] or d["pending_rows"] for d in alpha_rows))
            alpha_state = "reported" if alpha_reported else "upcoming" if event.date > local_today else receipt_state(event.date, now_local, received=False)
            coverage = {"label": "Locations reporting", "expected": len(expected_locations), "reported": satellite_reports,
                        "pending": pending_satellites, "returned": returned_satellites, "conflict": conflict_satellites}
            if can_view_alpha and alpha_id:
                coverage["alpha_expected"] = 1
                coverage["alpha_reported"] = int(alpha_reported)
                coverage["alpha_state"] = alpha_state
            unit_reports = [dict(value) for value in child_totals.values()]
            if scope_depth == 6:
                leaf = next((loc for loc in expected_locations if loc["path"] == scope_path), None)
                if leaf:
                    report = location_by_id.get(leaf["location_id"])
                    if report and report["source_role"] == "satellite" and (report["approved_rows"] or report["pending_rows"]):
                        leaf_state = "reported"
                        leaf_population = report["approved_population"] + (report["pending_population"] if include_pending else 0)
                    elif report and report["returned_rows"]:
                        leaf_state, leaf_population = "returned", None
                    elif report and report.get("conflict_rows"):
                        leaf_state, leaf_population = "conflict", None
                    else:
                        leaf_state, leaf_population = ("upcoming" if event.date > local_today else receipt_state(event.date, now_local, received=False)), None
                    unit_reports = [{"name": leaf["name"], "path": leaf["path"], "expected": 1,
                                     "reported": int(leaf_state == "reported"), "pending": int(leaf_state == "pending"),
                                     "returned": int(leaf_state == "returned"), "population": leaf_population,
                                     "state": leaf_state}]
            event_details = [d for d in event_details if can_view_alpha or d["source_role"] != "alpha"]
        else:
            expected, reported, pending, returned = 0, 0, 0, 0
            conflict_count = 0
            for detail_row in event_details:
                reported += int(bool(detail_row["approved_rows"] or detail_row["pending_rows"]))
                pending += int(bool(detail_row["pending_rows"] and not detail_row["approved_rows"]))
                returned += int(bool(detail_row["returned_rows"] and not (detail_row["approved_rows"] or detail_row["pending_rows"])))
                conflict_count += int(bool(detail_row.get("conflict_rows")))
            coverage = {"label": "Reporters", "expected": expected, "reported": reported, "pending": pending, "returned": returned, "conflict": conflict_count}
            unit_reports = []

        population = totals["approved_population"] + (totals["pending_population"] if include_pending else 0)
        approved_population = totals["approved_population"]
        pending_population = totals["pending_population"]
        visible_count_rows = totals["row_count"]
        if not can_view_alpha and campaign and campaign_mode == "crusade":
            population = sum(d["approved_population"] + (d["pending_population"] if include_pending else 0) for d in event_details if d["source_role"] == "satellite")
            approved_population = sum(d["approved_population"] for d in event_details if d["source_role"] == "satellite")
            pending_population = sum(d["pending_population"] for d in event_details if d["source_role"] == "satellite")
            visible_count_rows = sum(d["count_rows"] for d in event_details if d["source_role"] == "satellite")
        visible_returned_rows = totals["returned_rows"]
        if not can_view_alpha and campaign and campaign_mode == "crusade":
            visible_returned_rows = sum(d["returned_rows"] for d in event_details if d["source_role"] == "satellite")
        visible_approved_rows = totals["approved_rows"]
        visible_pending_rows = totals["pending_rows"]
        if not can_view_alpha and campaign and campaign_mode == "crusade":
            visible_approved_rows = sum(d["approved_rows"] for d in event_details if d["source_role"] == "satellite")
            visible_pending_rows = sum(d["pending_rows"] for d in event_details if d["source_role"] == "satellite")
        has_counted = bool(visible_approved_rows or include_pending and visible_pending_rows)
        has_pending = bool(visible_pending_rows)
        visible_conflicts = sum(detail.get("conflict_rows", 0) for detail in event_details)
        event_state = "counted" if has_counted else "pending" if has_pending else "conflict" if visible_conflicts else "returned" if visible_returned_rows else "upcoming" if event.date > local_today else receipt_state(event.date, now_local, received=False)
        if campaign and campaign_mode == "retreat":
            # Retreat counts are stored against the region reporting unit.
            population = sum(d["approved_population"] + (d["pending_population"] if include_pending else 0) for d in event_details if d["program_scope_path"] == str(event.path))
            approved_population = sum(d["approved_population"] for d in event_details if d["program_scope_path"] == str(event.path))
            pending_population = sum(d["pending_population"] for d in event_details if d["program_scope_path"] == str(event.path))
            visible_count_rows = sum(d["count_rows"] for d in event_details if d["program_scope_path"] == str(event.path))
        # Child drill rows are limited to the next jurisdiction below the
        # current scope. Location scope exposes only its own leaf report.
        children = []
        if campaign and campaign_mode == "retreat":
            children = [dict(item, expected=1, reported=int(item["state"] == "reported"), pending=int(item["state"] == "pending")) for item in unit_reports]
        elif campaign and campaign_mode == "crusade":
            children = [dict(item) for item in unit_reports]
        service_totals = totals.get("service_totals", {})
        multiple_services = len(service_totals) > 1
        occurrences.append({
            "event_id": key, "campaign_id": str(event.campaign_id) if event.campaign_id else None,
            "campaign_title": campaign.title if campaign else None,
            "campaign_mode": campaign_mode,
            "campaign_start_date": campaign.start_date.isoformat() if campaign else None,
            "date": event.date.isoformat(), "day_number": day_number,
            "title": event.title or ptype.name, "domain": pdomain.name, "domain_slug": pdomain.slug,
            "program_type": (ptype.name or "").strip(), "program_type_slug": ptype.slug,
            "program_level": event.reporting_scope, "scope_path": str(event.path),
            "alpha_location_id": str(event.alpha_location_id) if event.alpha_location_id else None,
            "is_alpha_event": bool(event.is_alpha_event), "approval_status": event.approval_status,
            "counted_population": None if multiple_services else population,
            "population_by_service": [{"service_id": service, "counted_population": value} for service, value in sorted(service_totals.items())],
            "approved_population": approved_population,
            "pending_population": pending_population, "returned_rows": visible_returned_rows,
            "count_rows": visible_count_rows, "sources": visible_sources,
            "location_reports": event_details, "unit_reports": unit_reports, "children": children, "coverage": coverage,
            "scheduled": True, "report_state": event_state,
            "converts": records.get("convert", 0), "newcomers": records.get("newcomer", 0),
            "record_sources": records.get("sources", {}),
            "record_reports": records.get("record_reports", []),
            "record_state": "reported" if records.get("convert", 0) or records.get("newcomer", 0) else "no_report",
            "campaign_id": str(event.campaign_id) if event.campaign_id else None,
        })
    return {"scope_path": scope_path, "include_pending": include_pending, "scope_names": scope_names, "occurrences": occurrences}
