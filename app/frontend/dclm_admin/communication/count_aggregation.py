from __future__ import annotations

from datetime import date
from typing import Any, Iterable


COUNT_FIELDS = ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")


def aggregate_count_submissions(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize submissions without allowing pending or rejected counts into totals."""
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        event_id = str(row.get("event_id") or row.get("event_title") or "")
        service_date = str(row.get("date") or "")
        location_id = str(row.get("location_id") or row.get("location") or "")
        program_type = str(row.get("program_type") or row.get("event_title") or "").strip().lower()
        program_level = str(row.get("program_level") or "").strip().lower()
        report_scope = str(row.get("program_scope_path") or "")
        # The persisted count_group_id is the occurrence identity. Date/program/
        # location is only a legacy fallback and never joins separate services.
        count_group_id = str(row.get("count_group_id") or "").strip()
        service_id = str(row.get("service_id") or "main")
        key = ("group", count_group_id) if count_group_id else ("legacy", location_id, program_type, service_date, event_id, service_id)
        group = grouped.setdefault(
            key,
            {
                "event_id": event_id,
                "event_title": str(row.get("event_title") or "Unknown event"),
                "date": service_date,
                "location_id": location_id,
                "location": str(row.get("location") or "Unknown location"),
                "program_type": str(row.get("program_type") or row.get("event_title") or "Unknown program"),
                "program_level": str(row.get("program_level") or ""),
                "program_scope_path": report_scope,
                "count_id": str(row.get("count_id") or ""),
                "count_group_id": count_group_id,
                "service_id": service_id,
                "total": None,
                "pending_total": 0,
                "submissions": 0,
                "approved_submissions": 0,
                "pending_submissions": 0,
                "rejected_submissions": 0,
                "sections": [],
                "section_count": 0,
                "count_modes": [],
                "mode_recorded": True,
                "submitted_by": [],
                "source_rows": [],
                "latest_submission_at": "",
                **{field: 0 for field in COUNT_FIELDS},
            },
        )
        group["submissions"] += 1
        mode = str(row.get("count_mode") or "").strip().lower()
        if not mode:
            group["mode_recorded"] = False
        elif mode not in group["count_modes"]:
            group["count_modes"].append(mode)
        if mode == "section":
            group["section_count"] += 1
        # Demo fixtures predate explicit review fields; treat those static rows
        # as approved historical examples. Live API rows always include status.
        review_status = str(row.get("status") or "approved").lower()
        if review_status == "approved":
            group["approved_submissions"] += 1
            group["total"] = int(group["total"] or 0) + int(row.get("total") or 0)
            for field in COUNT_FIELDS:
                group[field] += int(row.get(field) or 0)
        elif review_status == "pending":
            group["pending_submissions"] += 1
            group["pending_total"] += int(row.get("total") or 0)
        elif review_status in {"rejected", "returned"}:
            group["rejected_submissions"] += 1
        section = str(row.get("usher_section") or row.get("assignment_id") or "").strip()
        if section and section not in group["sections"]:
            group["sections"].append(section)
        submitter = str(row.get("submitted_by") or "").strip()
        if submitter and submitter not in group["submitted_by"]:
            group["submitted_by"].append(submitter)
        submitted_at = str(row.get("submitted_at") or row.get("created_at") or "")
        group["latest_submission_at"] = max(group["latest_submission_at"], submitted_at)
        group["source_rows"].append(row)
    for group in grouped.values():
        has_split_mode = bool(group["count_modes"])
        single_count = sum(1 for source in group["source_rows"] if source.get("count_mode") == "single")
        split_conflict = has_split_mode and (
            len(group["count_modes"]) > 1 or ("single" in group["count_modes"] and single_count != 1)
        )
        labels = [str(source.get("section_label") or "").strip().casefold() for source in group["source_rows"] if source.get("count_mode") == "section"]
        if labels and len(labels) != len(set(labels)):
            split_conflict = True
        all_approved = group["approved_submissions"] == group["submissions"]
        group["split_count"] = has_split_mode
        group["mode_recorded"] = bool(group["mode_recorded"])
        group["auto_accepted"] = bool(group["approved_submissions"]) and group["approved_submissions"] == len(group["source_rows"]) and all(
            bool(source.get("auto_accepted")) for source in group["source_rows"]
        )
        if group["approved_submissions"] and group["pending_submissions"]:
            group["status"] = "approved_with_pending"
        elif group["approved_submissions"] and group["rejected_submissions"]:
            group["status"] = "corrected"
        elif group["approved_submissions"]:
            group["status"] = "approved"
        elif group["pending_submissions"]:
            group["status"] = "pending"
        else:
            group["status"] = "rejected"
        if split_conflict:
            group["status"] = "conflict"
            group["total"] = None
        elif has_split_mode and not all_approved:
            group["status"] = "partial_approval"
            group["total"] = None
        elif has_split_mode:
            group["total"] = sum(int(source.get("total") or 0) for source in group["source_rows"])
    return sorted(
        grouped.values(),
        key=lambda group: (group["date"], group["latest_submission_at"], group["event_title"], group["location"]),
        reverse=True,
    )


def summarize_count_submissions(rows: Iterable[dict[str, Any]], *, today: date | None = None) -> dict[str, int]:
    today = today or date.today()
    groups = aggregate_count_submissions(rows)
    month_key = today.strftime("%Y-%m")
    month_groups = [group for group in groups if group["date"][:7] == month_key and group["total"] is not None]
    counted_groups = [group for group in groups if group["total"] is not None]
    totals = [int(group["total"]) for group in counted_groups]
    return {
        "latest_total": next((int(group["total"]) for group in groups if group["total"] is not None), None),
        "monthly_total": sum(int(group["total"]) for group in month_groups) if month_groups else None,
        "locations_reporting": len({group["location_id"] for group in month_groups}),
        "average_total": round(sum(totals) / len(totals)) if totals else None,
    }
