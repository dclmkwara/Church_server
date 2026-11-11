"""Exercise the B5 count workflow against a real local Church Server API/DB.

Requires the disposable B5 database plus the seeded local accounts. Run only
against localhost; each run creates visibly marked synthetic count rows.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine, text

DEFAULT_LOCATION = "9cc2fb04-76e3-41a8-96bd-bab6a880e2ff"
LAGOS = ZoneInfo("Africa/Lagos")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8020/api/v1")
    parser.add_argument("--location-id", default=DEFAULT_LOCATION)
    parser.add_argument("--password", default=os.getenv("B5_TEST_PASSWORD", "DemoPass2026#"))
    parser.add_argument("--sync-database-url", default=os.getenv("SYNC_DATABASE_URL", ""))
    args = parser.parse_args()
    host = urlparse(args.base_url).hostname
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Refusing non-local API host. This script creates synthetic records.")

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        tokens = {
            key: login(client, email, args.password)
            for key, email in {
                "usher_a": "location.worker@admin.dclm.ng",
                "usher_b": "fellowship.leader@admin.dclm.ng",
                "location_admin": "location.admin@admin.dclm.ng",
                "location_pastor": "location.pastor@admin.dclm.ng",
                "group_pastor": "group.pastor@admin.dclm.ng",
            }.items()
        }
        headers = {key: {"Authorization": f"Bearer {token}"} for key, token in tokens.items()}
        now = datetime.now(LAGOS)
        existing = client.get("/counts/", headers=headers["usher_a"], params={"limit": 500}).raise_for_status().json()
        used_sundays = {
            str(row.get("date", ""))[:10]
            for row in existing
            if str(row.get("location_id")) == args.location_id
            and str(row.get("program_type", "")).lower() == "sunday worship service"
        }
        future_year = 2040 + (uuid.uuid4().int % 50)
        next_sunday = date(future_year, 1, 1)
        next_sunday += timedelta(days=(6 - next_sunday.weekday()) % 7)
        while next_sunday.isoformat() in used_sundays:
            next_sunday += timedelta(days=7)
        conflict_sunday = next_sunday + timedelta(days=7)
        edit_sunday = next_sunday + timedelta(days=14)
        expired_sunday = next_sunday + timedelta(days=21)
        previous_sunday = now.date() - timedelta(days=(now.weekday() + 1) % 7 or 7)
        while previous_sunday.isoformat() in used_sundays:
            previous_sunday -= timedelta(days=7)
        run_marker = f"F2_TEST:f2-e2e:{uuid.uuid4().hex[:8]}"
        test_service_id = f"e2e-{run_marker[-8:]}"

        categories_a = {"adult_male": 40, "adult_female": 30, "youth_male": 10, "youth_female": 10, "boys": 15, "girls": 15}
        categories_b = {"adult_male": 5, "adult_female": 5, "youth_male": 5, "youth_female": 5, "boys": 5, "girls": 5}
        part_a_body = count_body(args.location_id, next_sunday, "section", "Adult A", 120, run_marker, service_id=test_service_id, categories=categories_a)
        part_a = submit_count_via_sync(client, headers["usher_a"], part_a_body, headers["group_pastor"])
        replay_result = post_count_sync_result(client, headers["usher_a"], part_a_body)
        assert replay_result["status"] == "duplicate", "same client id was not recognized as a replay"

        duplicate_label = count_body(args.location_id, next_sunday, "section", "Adult A", 1, run_marker, service_id=test_service_id)
        duplicate_label["client_id"] = str(uuid.uuid4())
        duplicate_response = post_count_sync_result(client, headers["usher_b"], duplicate_label)
        assert duplicate_response["status"] == "error" and "already been reported" in duplicate_response["error"]

        mixed_mode = count_body(args.location_id, next_sunday, "single", None, 10, run_marker, service_id=test_service_id)
        response = post_count_sync_result(client, headers["usher_b"], mixed_mode)
        assert response["status"] == "error" and "different count mode" in response["error"]

        part_b_body = count_body(args.location_id, next_sunday, "section", "Youth", 30, run_marker, service_id=test_service_id, categories=categories_b)
        part_b = submit_count_via_sync(client, headers["usher_b"], part_b_body, headers["group_pastor"])
        before_default = client.get(
            "/dashboard/sunday-worship", headers=headers["group_pastor"],
            params={"occurrence_date": next_sunday.isoformat()},
        ).raise_for_status().json()
        before_pending = client.get(
            "/dashboard/sunday-worship", headers=headers["group_pastor"],
            params={"occurrence_date": next_sunday.isoformat(), "include_pending": "true"},
        ).raise_for_status().json()
        assert before_default["total"] is None and before_pending["total"] == 150

        close = client.post(f"/counts/groups/{part_a['id']}/close", headers=headers["location_admin"], json={}).raise_for_status().json()
        soft_warning = close.get("missing_suggested_labels", [])
        if close.get("confirmation_required"):
            soft_warning = close["missing_suggested_labels"]
            close = client.post(
                f"/counts/groups/{part_a['id']}/close", headers=headers["location_admin"],
                json={"confirm_missing_suggestions": True},
            ).raise_for_status().json()
        assert close["state"] == "complete" and close["finalized_by"]

        review_groups = client.get("/counts/review/groups", headers=headers["group_pastor"]).raise_for_status().json()
        review = next(item for item in review_groups if item["count_group_id"] == part_a["count_group_id"])
        assert review["total"] == 150 and review["section_labels"] == ["Adult A", "Youth"]
        expected_categories = {key: categories_a[key] + categories_b[key] for key in categories_a}
        assert review["categories"] == expected_categories
        assert {row["count_id"] for row in review["parts"]} == {part_a["id"], part_b["id"]}
        approval = client.post(f"/counts/review/{part_a['id']}/approve", headers=headers["group_pastor"], json={}).raise_for_status().json()
        assert approval["status"] == "approved"
        after_approval = client.get(
            "/dashboard/sunday-worship", headers=headers["group_pastor"],
            params={"occurrence_date": next_sunday.isoformat()},
        ).raise_for_status().json()
        assert after_approval["total"] == 150 and after_approval["categories"] == expected_categories, json.dumps(after_approval, indent=2)
        locked_edit = client.post(f"/counts/{part_a['id']}/edit", headers=headers["usher_a"], json={
            "edit_id": str(uuid.uuid4()), "base_revision": 0, "values": {"total": 121},
        })
        assert locked_edit.status_code == 409 and "locked" in locked_edit.text.lower()

        single_sunday = next_sunday + timedelta(days=28)
        single_categories = {"adult_male": 2, "adult_female": 3, "youth_male": 4,
                             "youth_female": 5, "boys": 6, "girls": 7}
        single_body = count_body(args.location_id, single_sunday, "single", None, 27, run_marker,
                                 service_id=test_service_id, categories=single_categories)
        single_report = submit_count_via_sync(client, headers["usher_a"], single_body, headers["group_pastor"])
        single_review = client.get("/counts/review/groups", headers=headers["group_pastor"]).raise_for_status().json()
        assert next(item for item in single_review if item["count_group_id"] == single_report["count_group_id"])["categories"] == single_categories
        client.post(f"/counts/review/{single_report['id']}/approve", headers=headers["group_pastor"], json={}).raise_for_status()
        single_dashboard = client.get("/dashboard/sunday-worship", headers=headers["group_pastor"],
                                     params={"occurrence_date": single_sunday.isoformat()}).raise_for_status().json()
        assert single_dashboard["total"] == 27 and single_dashboard["categories"] == single_categories

        offering_context = {"location_id": args.location_id, "service_date": single_sunday.isoformat(),
                            "fund_type": "offering", "program_domain": "Weekly Programs",
                            "program_type": "Sunday Worship Service"}
        offering_before = client.get("/offerings/preflight", headers=headers["usher_a"], params=offering_context).raise_for_status().json()
        assert offering_before["already_recorded"] is False
        offering_body = {"client_id": str(uuid.uuid4()), "location_id": args.location_id,
                         "date": datetime.combine(single_sunday, datetime.min.time(), LAGOS).isoformat(),
                         "church_type": "DCLM", "program_level": "Local", "program_domain": "Weekly Programs",
                         "program_type": "Sunday Worship Service", "amount": "100.00",
                         "payment_method": "cash", "fund_type": "offering", "note": run_marker}
        offering_result = post_resource_sync_result(client, headers["usher_a"], "offerings", offering_body)
        assert offering_result["status"] == "synced", offering_result
        offering_after = client.get("/offerings/preflight", headers=headers["usher_b"], params=offering_context).raise_for_status().json()
        assert offering_after["already_recorded"] is True and offering_after["record_count"] == 1, json.dumps(offering_after)

        # Exercise the same sync resources used by the Field Utility for a real
        # roster capture and House Caring Fellowship record.
        worker_roster = client.get(
            "/attendance/workers", headers=headers["group_pastor"],
            params={"location_id": args.location_id, "limit": 500},
        ).raise_for_status().json()
        assert worker_roster, "The local fixture has no approved workers for attendance capture"
        worker_saturday = single_sunday + timedelta(days=6)
        worker_body = {
            "client_id": str(uuid.uuid4()), "location_id": args.location_id,
            "date": datetime.combine(worker_saturday, datetime.min.time(), LAGOS).isoformat(),
            "church_type": "DLCF", "program_level": "Local", "program_domain": "Weekly Programs",
            "program_type": "Saturday Workers Meeting", "expected_workers_count": len(worker_roster),
            "present_workers": [{"worker_id": worker_roster[0]["worker_id"], "worker_name": "Synthetic attendee"}],
            "submitted_by_worker_id": None, "note": f"{run_marker}:worker-attendance",
        }
        worker_result = post_resource_sync_result(client, headers["usher_a"], "worker_attendance_submissions", worker_body)
        assert worker_result["status"] == "synced", worker_result
        attendance_view = client.get(
            "/attendance/submissions", headers=headers["group_pastor"], params={"limit": 500},
        ).raise_for_status().json()
        worker_view = next((row for row in attendance_view if row["client_id"] == worker_body["client_id"]), None)
        assert worker_view and worker_view["present_count"] == 1 and worker_view["note"].startswith(run_marker)

        # The local clone has no fellowship at this location, and the current
        # RBAC seed grants no persona `hierarchy:create_fellowship`. Create one
        # explicitly marked fixture row in the disposable DB so the Utility
        # fellowship submission can be exercised without changing RBAC.
        sync_url = args.sync_database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        if urlparse(args.sync_database_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise SystemExit("Refusing non-local SYNC_DATABASE_URL; this test creates a marked synthetic fellowship.")
        synthetic_fellowship = create_marked_fellowship(sync_url, args.location_id, run_marker)
        fellowship_body = {
            "client_id": str(uuid.uuid4()), "fellowship_id": synthetic_fellowship["fellowship_id"],
            # The fellowship field sends an HTML date (naive midnight); its
            # persisted column is TIMESTAMP WITHOUT TIME ZONE.
            "date": datetime.combine(worker_saturday, datetime.min.time()).isoformat(),
            "adult_male": 2, "adult_female": 3, "youth_male": 1, "youth_female": 2,
            "boys": 4, "girls": 5, "topic": "F2 synthetic fellowship meeting",
            "note": f"{run_marker}:fellowship-attendance",
        }
        fellowship_result = post_resource_sync_result(client, headers["usher_a"], "fellowship_attendance", fellowship_body)
        assert fellowship_result["status"] == "synced", fellowship_result
        fellowship_view = client.get(
            "/fellowships/attendance", headers=headers["group_pastor"],
            params={"fellowship_id": synthetic_fellowship["fellowship_id"], "limit": 100},
        ).raise_for_status().json()
        fellowship_view_row = next((row for row in fellowship_view if row["client_id"] == fellowship_body["client_id"]), None)
        assert fellowship_view_row and fellowship_view_row["total"] == 17 and fellowship_view_row["note"].startswith(run_marker)

        single_a = count_body(args.location_id, conflict_sunday, "single", None, 40, run_marker, service_id=test_service_id)
        single_b = count_body(args.location_id, conflict_sunday, "single", None, 50, run_marker, service_id=test_service_id)
        first_single = submit_count_via_sync(client, headers["usher_a"], single_a, headers["group_pastor"])
        submit_count_via_sync(client, headers["usher_b"], single_b, headers["group_pastor"])
        conflicts = client.get("/counts/review/groups", headers=headers["group_pastor"]).raise_for_status().json()
        conflict = next(item for item in conflicts if item["count_group_id"] == first_single["count_group_id"])
        assert conflict["group_conflict"] is True and conflict["total"] is None

        edit_body = count_body(args.location_id, edit_sunday, "single", None, 20, run_marker, service_id=test_service_id)
        editable = submit_count_via_sync(client, headers["usher_a"], edit_body, headers["group_pastor"])
        edit_payload = {"edit_id": str(uuid.uuid4()), "base_revision": 0,
                        "values": {"total": 25, "adult_male": 25}}
        edited = client.post(f"/counts/{editable['id']}/edit", headers=headers["usher_a"], json=edit_payload).raise_for_status().json()
        duplicate_edit = client.post(f"/counts/{editable['id']}/edit", headers=headers["usher_a"], json=edit_payload).raise_for_status().json()
        assert edited["revision"] == duplicate_edit["revision"] == 1 and duplicate_edit["duplicate"] is True
        concurrent = [
            {"edit_id": str(uuid.uuid4()), "base_revision": 1, "values": {"total": 26, "adult_male": 26}},
            {"edit_id": str(uuid.uuid4()), "base_revision": 1, "values": {"total": 27, "adult_male": 27}},
        ]
        def concurrent_edit(payload: dict) -> httpx.Response:
            return httpx.post(f"{args.base_url}/counts/{editable['id']}/edit", headers=headers["usher_a"], json=payload, timeout=30)
        with ThreadPoolExecutor(max_workers=2) as pool:
            edit_responses = list(pool.map(concurrent_edit, concurrent))
        assert sorted(item.status_code for item in edit_responses) == [200, 409]
        latest_revision = 2
        revision_response = client.post(f"/counts/{editable['id']}/edit", headers=headers["usher_a"], json={
            "edit_id": str(uuid.uuid4()), "base_revision": latest_revision,
            "values": {"total": 28, "adult_male": 28},
        })
        revision_response.raise_for_status()
        latest_revision += 1
        fourth = client.post(f"/counts/{editable['id']}/edit", headers=headers["usher_a"], json={
            "edit_id": str(uuid.uuid4()), "base_revision": latest_revision,
            "values": {"total": 30, "adult_male": 30},
        })
        assert fourth.status_code == 409 and "edit limit" in fourth.text.lower()
        await_return = client.post(
            f"/counts/review/{editable['id']}/return", headers=headers["group_pastor"],
            json={"reason": "Please correct the submitted population figure."},
        ).raise_for_status().json()
        extra_edit = {"edit_id": str(uuid.uuid4()), "base_revision": latest_revision + 1,
                      "values": {"total": 31, "adult_male": 31}}
        client.post(f"/counts/{editable['id']}/edit", headers=headers["usher_a"], json=extra_edit).raise_for_status()

        if not args.sync_database_url:
            raise SystemExit("Set SYNC_DATABASE_URL to the same local disposable database to run the expired-window check.")
        db_host = urlparse(args.sync_database_url).hostname
        if db_host not in {"localhost", "127.0.0.1", "::1"}:
            raise SystemExit("Refusing non-local SYNC_DATABASE_URL; this test adjusts only a marked synthetic row.")
        expired_body = count_body(args.location_id, expired_sunday, "single", None, 8, run_marker, service_id=test_service_id)
        expired_row = submit_count_via_sync(client, headers["usher_a"], expired_body, headers["group_pastor"])
        sync_url = args.sync_database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        engine = create_engine(sync_url)
        try:
            with engine.begin() as connection:
                connection.execute(text("UPDATE counts SET created_at = now() - interval '25 hours' WHERE id = :id"), {"id": expired_row["id"]})
        finally:
            engine.dispose()
        expired_edit = client.post(f"/counts/{expired_row['id']}/edit", headers=headers["usher_a"], json={
            "edit_id": str(uuid.uuid4()), "base_revision": 0, "values": {"total": 9},
        })
        assert expired_edit.status_code == 409 and "24-hour edit window" in expired_edit.text

        offline_date = single_sunday + timedelta(days=7)
        offline_body = count_body(args.location_id, offline_date, "single", None, 9, run_marker, service_id=test_service_id)
        assert offline_date not in {next_sunday, conflict_sunday, edit_sunday, expired_sunday, single_sunday}
        sync_payload = {"counts": [offline_body]}
        first_sync = client.post("/sync/batch", headers=headers["usher_a"], json=sync_payload).raise_for_status().json()
        retry_syncs = [
            client.post("/sync/batch", headers=headers["usher_a"], json=sync_payload).raise_for_status().json()
            for _ in range(2)
        ]
        assert first_sync["counts"]["synced"] == 1
        assert all(retry["counts"]["duplicates"] == 1 for retry in retry_syncs)
        offline_rows = client.get("/counts/", headers=headers["group_pastor"], params={"limit": 500}).raise_for_status().json()
        assert sum(str(row.get("client_id")) == offline_body["client_id"] for row in offline_rows) == 1

        expired_section = count_body(args.location_id, previous_sunday, "section", "Auto-close", 5, run_marker,
                                     service_id=f"auto-{run_marker[-8:]}")
        auto_row = submit_count_via_sync(client, headers["usher_a"], expired_section, headers["group_pastor"])
        notification_response = client.get(
            "/notifications/history", headers=headers["location_pastor"],
            params={"since": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(), "kind": "count_group_auto_closed"},
        )
        assert notification_response.is_success, notification_response.text
        notifications = notification_response.json()
        auto_notice = next((item for item in notifications if item["source_id"] == auto_row["count_group_id"]), None)
        assert auto_notice is not None, "Location Pastor did not receive the auto-close notification"

        print(json.dumps({
            "run_marker": run_marker,
            "utility_submission_verified_separately": True,
            "split_workflow": {"date": next_sunday.isoformat(), "count_group_id": part_a["count_group_id"], "total": 150,
                               "labels": review["section_labels"], "soft_warning": soft_warning,
                               "closer": close["finalized_by"], "approved": approval["status"], "dashboard_total": after_approval["total"]},
            "single_count_categories": {"date": single_sunday.isoformat(), "total": single_dashboard["total"],
                                        "categories": single_dashboard["categories"]},
            "offering_duplicate_warning_preflight": offering_after,
            "worker_attendance": {"client_id": worker_body["client_id"], "present_count": worker_view["present_count"], "visible_in_admin_list": True},
            "fellowship_attendance": {"client_id": fellowship_body["client_id"], "total": fellowship_view_row["total"], "visible_in_admin_list": True},
            "duplicate_label_rejected": duplicate_response["status"] == "error",
            "single_conflict": conflict["group_conflict"],
            "edit_revision": edited["revision"], "idempotent_edit": duplicate_edit["duplicate"],
            "return_and_extra_edit": await_return["status"],
            "expired_edit_refused": expired_edit.status_code == 409,
            "offline_replays": len(retry_syncs),
            "offline_retry": retry_syncs[-1]["counts"]["duplicates"],
            "offline_client_rows": sum(str(row.get("client_id")) == offline_body["client_id"] for row in offline_rows),
            "auto_close_notification": auto_notice["kind"],
        }, indent=2))


def login(client: httpx.Client, email: str, password: str) -> str:
    response = client.post("/auth/login", data={"username": email, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]


def post_count_sync_result(client: httpx.Client, headers: dict, body: dict) -> dict:
    """Submit as the Field Utility does and return its per-item outcome."""
    return post_resource_sync_result(client, headers, "counts", body)


def post_resource_sync_result(client: httpx.Client, headers: dict, resource: str, body: dict) -> dict:
    response = client.post("/sync/batch", headers=headers, json={resource: [body]})
    response.raise_for_status()
    return response.json()[resource]["details"][0]


def submit_count_via_sync(client: httpx.Client, headers: dict, body: dict, read_headers: dict) -> dict:
    outcome = post_count_sync_result(client, headers, body)
    if outcome.get("status") not in {"synced", "duplicate"}:
        raise AssertionError(f"Field Utility count sync failed: {outcome}")
    response = client.get("/counts/", headers=read_headers, params={"limit": 500})
    response.raise_for_status()
    row = next((item for item in response.json() if str(item.get("client_id")) == str(body["client_id"])), None)
    if row is None:
        raise AssertionError(f"Sync confirmed count {body['client_id']} but it is absent from the count list")
    return row


def count_body(location_id: str, occurrence: date, mode: str, label: str | None, total: int,
               marker: str, *, service_id: str = "main", categories: dict[str, int] | None = None) -> dict:
    categories = categories or {"adult_male": total, "adult_female": 0, "youth_male": 0, "youth_female": 0, "boys": 0, "girls": 0}
    return {
        "client_id": str(uuid.uuid4()), "location_id": location_id,
        "date": datetime.combine(occurrence, datetime.min.time(), LAGOS).isoformat(),
        "church_type": "DLCF", "program_level": "Local", "program_domain": "Weekly",
        "program_type": "Sunday Worship Service", "total": total,
        **categories, "count_mode": mode, "section_label": label,
        "service_id": service_id, "submission_channel": "field_utility", "note": marker,
    }


def create_marked_fellowship(sync_url: str, location_id: str, marker: str) -> dict:
    code = f"F2{marker[-8:].upper()}"
    engine = create_engine(sync_url)
    try:
        with engine.begin() as connection:
            location = connection.execute(text(
                "SELECT location_name, church_type, path::text FROM locations WHERE location_id=:location_id"
            ), {"location_id": location_id}).mappings().one()
            row = connection.execute(text("""
                INSERT INTO fellowships (
                    location_id, fellowship_code, fellowship_name, fellowship_group,
                    location_name, church_type, path, version
                ) VALUES (
                    :location_id, :code, :name, 'adult', :location_name, :church_type,
                    (:location_path || '.' || :path_label)::ltree, 1
                ) RETURNING fellowship_id::text, fellowship_code, fellowship_name
            """), {
                "location_id": location_id, "code": code,
                "name": f"{marker} synthetic fellowship", "location_name": location["location_name"],
                "church_type": location["church_type"], "location_path": location["path"],
                "path_label": code,
            }).mappings().one()
        return dict(row)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
