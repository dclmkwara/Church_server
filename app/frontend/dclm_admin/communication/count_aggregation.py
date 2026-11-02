from __future__ import annotations

from datetime import date
from typing import Any, Iterable


COUNT_FIELDS = ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")


def aggregate_count_submissions(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine complementary usher rows at event + service date + location."""
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        event_id = str(row.get("event_id") or row.get("event_title") or "")
        service_date = str(row.get("date") or "")
        location_id = str(row.get("location_id") or row.get("location") or "")
        key = (event_id, service_date, location_id)
        group = grouped.setdefault(
            key,
            {
                "event_id": event_id,
                "event_title": str(row.get("event_title") or "Unknown event"),
                "date": service_date,
                "location_id": location_id,
                "location": str(row.get("location") or "Unknown location"),
                "count_id": str(row.get("count_id") or ""),
                "total": 0,
                "submissions": 0,
                "sections": [],
                "submitted_by": [],
                "source_rows": [],
                "latest_submission_at": "",
                **{field: 0 for field in COUNT_FIELDS},
            },
        )
        group["total"] += int(row.get("total") or 0)
        group["submissions"] += 1
        for field in COUNT_FIELDS:
            group[field] += int(row.get(field) or 0)
        section = str(row.get("usher_section") or row.get("assignment_id") or "").strip()
        if section and section not in group["sections"]:
            group["sections"].append(section)
        submitter = str(row.get("submitted_by") or "").strip()
        if submitter and submitter not in group["submitted_by"]:
            group["submitted_by"].append(submitter)
        submitted_at = str(row.get("submitted_at") or row.get("created_at") or "")
        group["latest_submission_at"] = max(group["latest_submission_at"], submitted_at)
        group["source_rows"].append(row)
    return sorted(
        grouped.values(),
        key=lambda group: (group["date"], group["latest_submission_at"], group["event_title"], group["location"]),
        reverse=True,
    )


def summarize_count_submissions(rows: Iterable[dict[str, Any]], *, today: date | None = None) -> dict[str, int]:
    today = today or date.today()
    groups = aggregate_count_submissions(rows)
    month_key = today.strftime("%Y-%m")
    month_groups = [group for group in groups if group["date"][:7] == month_key]
    totals = [group["total"] for group in groups]
    return {
        "latest_total": int(groups[0]["total"]) if groups else 0,
        "monthly_total": sum(int(group["total"]) for group in month_groups),
        "locations_reporting": len({group["location_id"] for group in month_groups}),
        "average_total": round(sum(totals) / len(totals)) if totals else 0,
    }
