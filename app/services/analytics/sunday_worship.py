"""Sunday Worship population coverage and totals for the B1 analytics slice."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Date, DateTime, Integer, String, and_, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.filters import scope_filter, scope_or_ancestor_filter
from app.models.counts import Count, CountReminderRecipient
from app.models.expected_population import LocationExpectedPopulation
from app.models.location import Group, Location, Region, State
from app.models.programs import ProgramCampaign, ProgramEvent, ProgramType

from .program_config import (
    AWAITING_HOURS_AFTER_OCCURRENCE,
    MISSING_HOURS_AFTER_OCCURRENCE,
    REPORTING_TIMEZONE,
    STANDING_PROGRAMS,
)


_PROGRAM = STANDING_PROGRAMS["sunday_worship_service"]
_CATEGORIES = ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")
_RETURNED_STATUSES = {"rejected", "returned"}


def latest_sunday(today: date) -> date:
    """Return the most recent Sunday on or before the supplied local date."""
    return today - timedelta(days=(today.weekday() - _PROGRAM.weekday) % 7)


def receipt_state(
    occurrence_date: date,
    now: datetime,
    *,
    received: bool,
    combined: bool = False,
) -> str:
    """Map a missing weekly report to the church's Africa/Lagos time window."""
    if combined:
        return "combined"
    if received:
        return "received"
    local_now = now.astimezone(ZoneInfo(REPORTING_TIMEZONE)) if now.tzinfo else now.replace(tzinfo=ZoneInfo(REPORTING_TIMEZONE))
    deadline = datetime.combine(occurrence_date + timedelta(days=1), time.min, ZoneInfo(REPORTING_TIMEZONE))
    elapsed = local_now - deadline
    if elapsed <= timedelta(hours=AWAITING_HOURS_AFTER_OCCURRENCE):
        return "awaiting"
    if elapsed <= timedelta(hours=MISSING_HOURS_AFTER_OCCURRENCE):
        return "late"
    return "missing"


def _report_review_state(rows: Iterable[Any]) -> str | None:
    """Resolve one legacy report made from one or more count rows."""
    rows = list(rows)
    states = {str(getattr(row, "status", "pending") or "pending").lower() for row in rows}
    if not states:
        return None
    current_rows = [row for row in rows if str(getattr(row, "status", "pending") or "pending").lower() not in _RETURNED_STATUSES]
    if not current_rows:
        return "returned" if states & _RETURNED_STATUSES else None
    current_states = {str(getattr(row, "status", "pending") or "pending").lower() for row in current_rows}
    if current_states == {"approved"}:
        return "approved"
    return "pending"


def _count_values(rows: Iterable[Any]) -> dict[str, int]:
    """Sum the existing count fields without converting an absent report to zero."""
    rows = [row for row in rows if str(getattr(row, "status", "pending") or "pending").lower() not in _RETURNED_STATUSES]
    return {key: sum(int(getattr(row, key, 0) or 0) for row in rows) for key in (*_CATEGORIES, "total")}


def _within(path: str, ancestor: str) -> bool:
    """Compare normalized ltree paths for event coverage after SQL scope filtering."""
    path = str(path or "").strip(".").lower()
    ancestor = str(ancestor or "").strip(".").lower()
    return path == ancestor or path.startswith(ancestor + ".")


def _build_overview(
    *,
    scope_path: str,
    occurrence_date: date,
    now: datetime,
    locations: list[Any],
    events: list[Any],
    count_rows: list[Any],
    include_pending: bool,
    estimates_by_location: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    """Build independent coverage states and counted values from loaded rows."""
    locations_by_id = {str(row.location_id): row for row in locations}
    rows_by_location: dict[str, list[Any]] = defaultdict(list)
    rows_by_event: dict[str, list[Any]] = defaultdict(list)
    rows_by_scope: dict[str, list[Any]] = defaultdict(list)
    event_by_id = {str(event.id): event for event in events}

    for row in count_rows:
        event_id = str(row.event_id) if getattr(row, "event_id", None) else None
        if event_id in event_by_id:
            rows_by_event[event_id].append(row)
        elif not event_id:
            level = str(getattr(row, "program_level", "") or "").strip().lower()
            report_scope = getattr(row, "program_scope_path", None)
            if level in {"group", "region", "state"} and report_scope:
                rows_by_scope[str(report_scope)].append(row)
            elif str(row.location_id) in locations_by_id:
                rows_by_location[str(row.location_id)].append(row)

    combined_events = [
        event for event in events
        if str(getattr(event, "reporting_scope", "")).lower() in {"group", "region", "state"}
    ]
    # Prefer the closest reporting scope when approved combined events overlap.
    combined_events.sort(key=lambda event: len(str(event.path).split(".")), reverse=True)
    event_for_location: dict[str, Any] = {}
    for event in combined_events:
        for location in locations:
            location_id = str(location.location_id)
            if location_id not in event_for_location and _within(str(location.path), str(event.path)):
                event_for_location[location_id] = event

    # Eventless combined reports use the stored reporting scope. ProgramEvent
    # can add coverage, but it is not required for a valid combined report.
    combined_count_scopes = sorted(rows_by_scope, key=lambda path: len(path.split(".")), reverse=True)
    count_scope_for_location: dict[str, str] = {}
    for location in locations:
        location_id = str(location.location_id)
        if location_id in event_for_location:
            continue
        for report_scope in combined_count_scopes:
            if _within(str(location.path), report_scope):
                count_scope_for_location[location_id] = report_scope
                break

    coverage = {
        "approved": 0,
        "pending": 0,
        "returned": 0,
        "awaiting": 0,
        "late": 0,
        "missing": 0,
        "combined": 0,
        "superseded": 0,
    }
    included_rows: list[Any] = []
    received_units: set[str] = set()
    counted_units: set[str] = set()
    location_totals: dict[str, int] = {}
    included_combined_count_scopes: set[str] = set()
    unreported_location_ids: list[str] = []

    local_event_rows_by_location: dict[str, list[Any]] = defaultdict(list)
    for event_id, event_rows in rows_by_event.items():
        event = event_by_id[event_id]
        if str(getattr(event, "reporting_scope", "")).lower() not in {"location", "local"}:
            continue
        for row in event_rows:
            location_id = str(row.location_id)
            if location_id in locations_by_id:
                local_event_rows_by_location[location_id].append(row)

    for location_id, location in locations_by_id.items():
        event = event_for_location.get(location_id)
        count_scope = count_scope_for_location.get(location_id)
        own_rows = rows_by_location.get(location_id, [])
        event_rows = local_event_rows_by_location.get(location_id, [])
        if event is not None or count_scope is not None:
            coverage["combined"] += 1
            if own_rows or event_rows:
                coverage["superseded"] += 1
            combined_rows = rows_by_event.get(str(event.id), []) if event is not None else rows_by_scope[count_scope]
            review = _report_review_state(combined_rows)
            if review:
                received_units.add(location_id)
                coverage[review] += 1
                if review == "approved" or (include_pending and review == "pending"):
                    counted_units.add(location_id)
                    # A combined total cannot be attributed to each covered
                    # location. Keep it in scope totals but out of per-location
                    # comparisons to avoid manufacturing location trends.
                    if count_scope is not None:
                        included_combined_count_scopes.add(count_scope)
            else:
                state = receipt_state(occurrence_date, now, received=False)
                coverage[state] += 1
                if state in {"missing", "late", "awaiting"}:
                    unreported_location_ids.append(location_id)
            continue

        rows = own_rows or event_rows
        review = _report_review_state(rows)
        if review:
            received_units.add(location_id)
            coverage[review] += 1
            if review == "approved" or (include_pending and review == "pending"):
                counted_units.add(location_id)
                included_rows.extend(rows)
                location_totals[location_id] = _count_values(rows)["total"]
        else:
            state = receipt_state(occurrence_date, now, received=False)
            coverage[state] += 1
            if state in {"missing", "late", "awaiting"}:
                unreported_location_ids.append(location_id)
    # Include each combined report once when its reporting scope is within this view.
    selected_event_ids = {str(event.id) for event in event_for_location.values()}
    for event in combined_events:
        if str(event.id) not in selected_event_ids:
            continue
        event_rows = rows_by_event.get(str(event.id), [])
        if not event_rows or not _within(str(event.path), scope_path):
            continue
        review = _report_review_state(event_rows)
        if review == "approved" or (include_pending and review == "pending"):
            included_rows.extend(event_rows)
    # Add each eventless combined report once even when it covers many locations.
    for report_scope in included_combined_count_scopes:
        if _within(report_scope, scope_path):
            included_rows.extend(rows_by_scope[report_scope])

    values = _count_values(included_rows)
    has_counted_rows = bool(included_rows)
    total = values["total"] if has_counted_rows else None
    values_payload = {
        key: value if has_counted_rows else None
        for key, value in values.items()
    }
    estimates_by_location = estimates_by_location or {}
    expected_by_location: dict[str, int] = {}
    for location_id, versions in estimates_by_location.items():
        eligible = [version for version in versions if version.effective_from <= occurrence_date]
        if eligible:
            version = max(eligible, key=lambda item: (item.effective_from, getattr(item, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc)))
            expected_by_location[location_id] = int(version.expected_value)
    counted_location_ids = set(counted_units)
    estimated_counted_locations = set()
    expected_total = 0
    expected_counted_population = 0
    # Location-level reports can be paired directly with each location's
    # estimate. Combined reports are comparable only when every covered
    # location has an estimate; otherwise their aggregate cannot be split
    # honestly across estimated and unestimated locations.
    for location_id, reported_total in location_totals.items():
        if location_id in expected_by_location:
            estimated_counted_locations.add(location_id)
            expected_total += expected_by_location[location_id]
            expected_counted_population += reported_total
    for event in combined_events:
        event_id = str(event.id)
        if not _within(str(event.path), scope_path):
            continue
        rows = rows_by_event.get(event_id, [])
        covered = {
            location_id for location_id in counted_units
            if str(getattr(event_for_location.get(location_id), "id", "")) == event_id
        }
        if covered and covered.issubset(expected_by_location):
            review = _report_review_state(rows)
            if review == "approved" or (include_pending and review == "pending"):
                estimated_counted_locations.update(covered)
                expected_total += sum(expected_by_location[item] for item in covered)
                expected_counted_population += _count_values(rows)["total"]
    for report_scope in included_combined_count_scopes:
        if not _within(report_scope, scope_path):
            continue
        rows = rows_by_scope.get(report_scope, [])
        covered = {
            location_id for location_id in counted_units
            if count_scope_for_location.get(location_id) == report_scope
        }
        if covered and covered.issubset(expected_by_location):
            review = _report_review_state(rows)
            if review == "approved" or (include_pending and review == "pending"):
                estimated_counted_locations.update(covered)
                expected_total += sum(expected_by_location[item] for item in covered)
                expected_counted_population += _count_values(rows)["total"]
    expected_percent = round(expected_counted_population * 100 / expected_total, 1) if expected_total > 0 else None
    return {
        "program_domain": "weekly_programs",
        "program_type": _PROGRAM.key,
        "program_label": _PROGRAM.label,
        "program_level": "Location",
        "expected_unit": _PROGRAM.expected_unit,
        "scope_path": scope_path,
        "occurrence_date": occurrence_date.isoformat(),
        "n_expected": len(locations),
        "n_received": len(received_units),
        "n_counted": len(counted_units),
        "total": total,
        "categories": {key: values_payload[key] for key in _CATEGORIES},
        "coverage": coverage,
        "unreported_location_ids": unreported_location_ids,
        "location_totals": location_totals,
        "location_expected_values": expected_by_location,
        "expected_population_total": expected_total if estimated_counted_locations else None,
        "expected_population_counted_total": expected_counted_population if estimated_counted_locations else None,
        "expected_population_counted_locations": len(estimated_counted_locations),
        "expected_population_no_estimate_locations": len(counted_location_ids - set(expected_by_location)),
        "locations_with_estimate": len(set(expected_by_location) & set(locations_by_id)),
        "expected_population_percent": expected_percent,
        "additivity": "additive",
        "status_rule": "approved" if not include_pending else "approved+pending",
        "include_pending": include_pending,
        "combined_levels": sorted({
            str(event.reporting_scope).lower()
            for event in event_for_location.values()
        }),
    }


class SundayWorshipAnalytics:
    """Query and summarize the latest (or selected) Sunday Worship occurrence."""

    @staticmethod
    async def overview(
        db: AsyncSession,
        scope_path: str,
        *,
        occurrence_date: date | None = None,
        now: datetime | None = None,
        include_pending: bool = False,
    ) -> dict[str, Any]:
        """Return Sunday coverage and totals without treating absence as zero."""
        now = now or datetime.now(timezone.utc)
        local_now = now.astimezone(ZoneInfo(REPORTING_TIMEZONE)) if now.tzinfo else now.replace(tzinfo=ZoneInfo(REPORTING_TIMEZONE))
        occurrence_date = occurrence_date or latest_sunday(local_now.date())
        if occurrence_date.weekday() != _PROGRAM.weekday:
            raise ValueError("Sunday Worship occurrence_date must be a Sunday")

        type_result = await db.execute(
            select(ProgramType.id).where(
                ProgramType.slug == _PROGRAM.program_type_slug,
                ProgramType.is_deleted.is_(False),
            )
        )
        type_id = type_result.scalar_one_or_none()
        location_result = await db.execute(
            select(Location).where(
                scope_filter(Location.path, scope_path),
                or_(
                    Location.is_active.is_(True),
                    and_(Location.is_active.is_(False), Location.closed_on.is_not(None), Location.closed_on > occurrence_date),
                ),
                or_(Location.opened_on.is_(None), Location.opened_on <= occurrence_date),
                or_(Location.closed_on.is_(None), Location.closed_on > occurrence_date),
            ).order_by(Location.location_name)
        )
        locations = list(location_result.scalars().all())
        event_result = await db.execute(
            select(ProgramEvent).options(joinedload(ProgramEvent.campaign)).where(
                ProgramEvent.program_type_id == type_id if type_id is not None else ProgramEvent.id.is_(None),
                ProgramEvent.date == occurrence_date,
                ProgramEvent.approval_status == "approved",
                ProgramEvent.is_deleted.is_(False),
                scope_or_ancestor_filter(ProgramEvent.path, scope_path),
            )
        )
        events = [
            event
            for event in event_result.scalars().unique().all()
            if event.campaign is None
            or (event.campaign.status == "active" and not event.campaign.is_deleted)
        ]

        local_start = datetime.combine(occurrence_date, time.min, ZoneInfo(REPORTING_TIMEZONE)).astimezone(timezone.utc)
        local_end = datetime.combine(occurrence_date + timedelta(days=1), time.min, ZoneInfo(REPORTING_TIMEZONE)).astimezone(timezone.utc)
        canonical_filters = []
        if type_id is not None:
            canonical_filters.append(Count.program_type_id == type_id)
        canonical_filters.append(
            and_(
                Count.event_id.is_(None),
                func.lower(func.trim(Count.program_type)) == "sunday worship service",
                or_(Count.program_domain.is_(None), func.lower(func.trim(Count.program_domain)).in_({"weekly programs", "weekly_programs"})),
            )
        )
        count_filters = [
            Count.is_deleted.is_(False),
            Count.date >= local_start,
            Count.date < local_end,
            or_(*canonical_filters),
        ]
        included_locations = [str(row.location_id) for row in locations]
        event_ids = [event.id for event in events]
        storage_filters = []
        if included_locations:
            storage_filters.append(Count.location_id.in_(included_locations))
        if event_ids:
            storage_filters.append(Count.event_id.in_(event_ids))
        storage_filters.append(
            and_(
                Count.event_id.is_(None),
                func.lower(func.coalesce(Count.program_level, "" )).in_({"group", "region", "state"}),
                scope_filter(Count.program_scope_path, scope_path),
            )
        )
        if storage_filters:
            count_result = await db.execute(select(Count).where(*count_filters, or_(*storage_filters)))
            count_rows = list(count_result.scalars().all())
        else:
            count_rows = []
        return _build_overview(
            scope_path=scope_path,
            occurrence_date=occurrence_date,
            now=now,
            locations=locations,
            events=events,
            count_rows=count_rows,
            include_pending=include_pending,
        )

    @staticmethod
    async def series(
        db: AsyncSession,
        scope_path: str,
        *,
        occurrence_dates: list[date],
        include_pending: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Load all weeks and direct children in a small fixed set of queries."""
        if not occurrence_dates:
            return {"scope": [], "children": []}
        if any(item.weekday() != _PROGRAM.weekday for item in occurrence_dates):
            raise ValueError("Every occurrence date must be a Sunday")
        now = now or datetime.now(timezone.utc)
        first_date, last_date = min(occurrence_dates), max(occurrence_dates)

        depth = max(len([part for part in scope_path.split(".") if part]) - 1, 0)
        child_model = {2: Region, 3: Group, 4: Location}.get(depth)
        hierarchy_selects = []
        # Carry the location roster in the same hierarchy/estimate round trip.
        # The reporting calculator and child table share this request-scoped set.
        reminder_time = select(func.max(CountReminderRecipient.sent_at)).where(
            CountReminderRecipient.location_id == Location.location_id,
            CountReminderRecipient.occurrence_date == last_date,
        ).correlate(Location).scalar_subquery()
        hierarchy_selects.append(
            select(
                Location.path.label("path"), Location.location_name.label("name"),
                cast(Location.location_id, String).label("location_id"), literal("location").label("node_type"),
                literal(None, type_=Date).label("effective_from"),
                literal(None, type_=Integer).label("expected_value"),
                literal(None, type_=DateTime(timezone=True)).label("estimate_created_at"),
                Location.is_active.label("is_active"), Location.opened_on.label("opened_on"),
                Location.closed_on.label("closed_on"), reminder_time.label("reminded_at"),
            ).where(
                scope_filter(Location.path, scope_path),
                or_(Location.is_active.is_(True), and_(Location.is_active.is_(False), Location.closed_on.is_not(None), Location.closed_on > first_date)),
                or_(Location.opened_on.is_(None), Location.opened_on <= last_date),
                or_(Location.closed_on.is_(None), Location.closed_on > first_date),
            )
        )
        if child_model:
            child_name = {Region: Region.region_name, Group: Group.group_name, Location: Location.location_name}[child_model]
            child_location_id = cast(Location.location_id, String) if child_model is Location else literal("", type_=String)
            hierarchy_selects.append(
                select(
                    child_model.path.label("path"), child_name.label("name"),
                    child_location_id.label("location_id"), literal("child").label("node_type"),
                    literal(None, type_=Date).label("effective_from"),
                    literal(None, type_=Integer).label("expected_value"),
                    literal(None, type_=DateTime(timezone=True)).label("estimate_created_at"),
                    literal(None, type_=Boolean).label("is_active"), literal(None, type_=Date).label("opened_on"),
                    literal(None, type_=Date).label("closed_on"), literal(None, type_=DateTime(timezone=True)).label("reminded_at"),
                ).where(scope_filter(child_model.path, scope_path))
            )
        scope_parts = [part for part in scope_path.split(".") if part]
        ancestor_paths = [".".join(scope_parts[:node_depth]) for node_depth in range(3, len(scope_parts) + 1)]
        for node_depth, path in enumerate(ancestor_paths, start=3):
            node_model, name_column = {
                3: (State, State.state_name),
                4: (Region, Region.region_name),
                5: (Group, Group.group_name),
            }.get(node_depth, (Location, Location.location_name))
            node_location_id = cast(Location.location_id, String) if node_model is Location else literal("", type_=String)
            hierarchy_selects.append(
                select(
                    node_model.path.label("path"), name_column.label("name"),
                    node_location_id.label("location_id"), literal("ancestor").label("node_type"),
                    literal(None, type_=Date).label("effective_from"),
                    literal(None, type_=Integer).label("expected_value"),
                    literal(None, type_=DateTime(timezone=True)).label("estimate_created_at"),
                    literal(None, type_=Boolean).label("is_active"), literal(None, type_=Date).label("opened_on"),
                    literal(None, type_=Date).label("closed_on"), literal(None, type_=DateTime(timezone=True)).label("reminded_at"),
                ).where(node_model.path == path)
            )
        hierarchy_selects.append(
            select(
                LocationExpectedPopulation.path.label("path"),
                Location.location_name.label("name"),
                cast(LocationExpectedPopulation.location_id, String).label("location_id"),
                literal("estimate").label("node_type"),
                LocationExpectedPopulation.effective_from.label("effective_from"),
                LocationExpectedPopulation.expected_value.label("expected_value"),
                LocationExpectedPopulation.created_at.label("estimate_created_at"),
                literal(None, type_=Boolean).label("is_active"), literal(None, type_=Date).label("opened_on"),
                literal(None, type_=Date).label("closed_on"), literal(None, type_=DateTime(timezone=True)).label("reminded_at"),
            ).join(Location, Location.location_id == LocationExpectedPopulation.location_id)
            .where(
                scope_filter(LocationExpectedPopulation.path, scope_path),
                LocationExpectedPopulation.effective_from <= last_date,
            )
        )
        hierarchy_result = await db.execute(union_all(*hierarchy_selects).order_by("path")) if hierarchy_selects else None
        hierarchy_rows = list(hierarchy_result.all()) if hierarchy_result is not None else []
        location_rows = [row for row in hierarchy_rows if row.node_type == "location"]
        locations = [SimpleNamespace(
            location_id=row.location_id, path=row.path, location_name=row.name,
            is_active=row.is_active, opened_on=row.opened_on, closed_on=row.closed_on,
        ) for row in location_rows]
        reminded_at_by_location = {
            str(row.location_id): row.reminded_at for row in location_rows if row.reminded_at is not None
        }
        children = [row for row in hierarchy_rows if row.node_type == "child"]
        ancestors = [{"path": str(row.path), "name": str(row.name or "")} for row in hierarchy_rows if row.node_type == "ancestor"]
        estimates_by_location: dict[str, list[Any]] = defaultdict(list)
        for row in hierarchy_rows:
            if row.node_type == "estimate":
                estimates_by_location[str(row.location_id)].append(SimpleNamespace(
                    effective_from=row.effective_from,
                    expected_value=row.expected_value,
                    created_at=row.estimate_created_at,
                ))

        type_and_events = select(
            ProgramType.id.label("program_type_id"), ProgramEvent,
            ProgramCampaign.status.label("campaign_status"),
            ProgramCampaign.is_deleted.label("campaign_deleted"),
        ).select_from(ProgramType).outerjoin(
            ProgramEvent, and_(ProgramEvent.program_type_id == ProgramType.id,
                ProgramEvent.date.in_(occurrence_dates),
                ProgramEvent.approval_status == "approved",
                ProgramEvent.is_deleted.is_(False),
                scope_or_ancestor_filter(ProgramEvent.path, scope_path)),
        ).outerjoin(
            ProgramCampaign, ProgramCampaign.id == ProgramEvent.campaign_id,
        ).where(
            ProgramType.slug == _PROGRAM.program_type_slug,
            ProgramType.is_deleted.is_(False),
        )
        event_result = await db.execute(type_and_events)
        event_rows = list(event_result.all())
        type_id = event_rows[0].program_type_id if event_rows else None
        event_rows = [row for row in event_rows if row[1] is not None]
        events = [
            row[1] for row in event_rows
            if not row[1].campaign_id or (
                row.campaign_status == "active" and not row.campaign_deleted
            )
        ]
        start_at = datetime.combine(first_date, time.min, ZoneInfo(REPORTING_TIMEZONE)).astimezone(timezone.utc)
        end_at = datetime.combine(last_date + timedelta(days=1), time.min, ZoneInfo(REPORTING_TIMEZONE)).astimezone(timezone.utc)
        canonical_filters = []
        # Resolve the canonical type and events in one query. The empty event
        # result retains legacy name matching without another type lookup.
        if type_id is not None:
            canonical_filters.append(Count.program_type_id == type_id)
        canonical_filters.append(and_(
            Count.event_id.is_(None),
            func.lower(func.trim(Count.program_type)) == "sunday worship service",
            or_(Count.program_domain.is_(None), func.lower(func.trim(Count.program_domain)).in_({"weekly programs", "weekly_programs"})),
        ))
        count_filters = [
            Count.is_deleted.is_(False), Count.date >= start_at, Count.date < end_at,
            or_(*canonical_filters),
        ]
        storage_filters = []
        location_ids = [str(row.location_id) for row in locations]
        event_ids = [row.id for row in events]
        if location_ids:
            storage_filters.append(Count.location_id.in_(location_ids))
        if event_ids:
            storage_filters.append(Count.event_id.in_(event_ids))
        storage_filters.append(and_(
            Count.event_id.is_(None),
            func.lower(func.coalesce(Count.program_level, "")).in_({"group", "region", "state"}),
            scope_filter(Count.program_scope_path, scope_path),
        ))
        count_result = await db.execute(select(Count).where(*count_filters, or_(*storage_filters)))
        count_rows = list(count_result.scalars().all())

        def build(path: str, when: date) -> dict[str, Any]:
            active_locations = [
                location for location in locations
                if (location.opened_on is None or location.opened_on <= when)
                and (location.closed_on is None or location.closed_on > when)
                and _within(str(location.path), path)
            ]
            active_events = [event for event in events if event.date == when and _within(str(event.path), scope_path)]
            start = datetime.combine(when, time.min, ZoneInfo(REPORTING_TIMEZONE)).astimezone(timezone.utc)
            end = datetime.combine(when + timedelta(days=1), time.min, ZoneInfo(REPORTING_TIMEZONE)).astimezone(timezone.utc)
            daily_counts = [row for row in count_rows if start <= row.date < end]
            return _build_overview(
                scope_path=path, occurrence_date=when, now=now,
                locations=active_locations, events=active_events,
                count_rows=daily_counts, include_pending=include_pending,
                estimates_by_location=estimates_by_location,
            )

        scope_history = [build(scope_path, when) for when in occurrence_dates]
        location_by_id = {str(location.location_id): location for location in locations}
        missing_locations = [
            {
                "path": str(location_by_id[location_id].path),
                "name": str(location_by_id[location_id].location_name),
                "location_id": location_id,
                "reminded_at": reminded_at_by_location.get(location_id),
            }
            for location_id in scope_history[-1].get("unreported_location_ids", [])
            if location_id in location_by_id
        ]
        return {
            "scope": scope_history,
            "ancestors": ancestors,
            "location_nodes": [
                {"path": str(location.path), "name": str(location.location_name), "location_id": str(location.location_id)}
                for location in locations
            ],
            "missing_locations": missing_locations,
            "program_type_id": type_id,
            "children": [
                {
                    "path": str(child.path),
                    "name": str(child.name or ""),
                    "location_id": str(child.location_id or ""),
                    "history": [build(str(child.path), when) for when in occurrence_dates],
                }
                for child in children
            ],
        }
