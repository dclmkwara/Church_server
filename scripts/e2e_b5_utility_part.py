"""Add the second usher part and approve a count group created in Field Utility.

Use only with the disposable localhost test database and a Utility-synced first
part. Closing is performed in the Utility UI between --submit-part and
--approve so the script exercises that screen's close action as well.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, time
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import httpx

DEFAULT_LOCATION = "cb56bc5e-4445-448c-a3b2-1b4503b4aea9"
LAGOS = ZoneInfo("Africa/Lagos")


def login(client: httpx.Client, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": password})
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8020/api/v1")
    parser.add_argument("--location-id", default=DEFAULT_LOCATION)
    parser.add_argument("--date", default="2040-01-01")
    parser.add_argument("--password", default=os.getenv("B5_TEST_PASSWORD", "DemoPass2026#"))
    parser.add_argument("--stage", choices=("submit-part", "approve"), required=True)
    args = parser.parse_args()
    if urlparse(args.base_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Refusing non-local API host; this script writes synthetic records.")
    occurrence = date.fromisoformat(args.date)
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        usher_b = login(client, "fellowship.leader@admin.dclm.ng", args.password)
        group_pastor = login(client, "group.pastor@admin.dclm.ng", args.password)
        categories = {"adult_male": 2, "adult_female": 1, "youth_male": 1,
                      "youth_female": 1, "boys": 0, "girls": 0}
        client_id = str(uuid5(NAMESPACE_URL, f"B5_UTILITY_E2E:{args.location_id}:{occurrence.isoformat()}"))
        payload = {
            "client_id": client_id, "location_id": args.location_id,
            "date": datetime.combine(occurrence, time.min, LAGOS).isoformat(),
            "church_type": "DCLM", "program_level": "Local", "program_domain": "Weekly Programs",
            "program_type": "Sunday Worship Service", "total": sum(categories.values()), **categories,
            "count_mode": "section", "section_label": "Utility B", "service_id": "main",
            "submission_channel": "field_utility", "note": "B5_DEMO:UTILITY_E2E:part-b",
        }
        if args.stage == "submit-part":
            response = client.post("/counts/", headers=usher_b, json=payload)
            response.raise_for_status()
            part = response.json()
            groups = client.get("/counts/review/groups", headers=group_pastor).raise_for_status().json()
            group = next(row for row in groups if row["count_group_id"] == part["count_group_id"])
            expected_categories = {"adult_male": 12, "adult_female": 9, "youth_male": 4,
                                  "youth_female": 5, "boys": 1, "girls": 2}
            assert group["total"] == 33 and group["categories"] == expected_categories
            assert group["section_labels"] == ["Utility A", "Utility B"]
            print(json.dumps({"part_b_id": part["id"], "count_group_id": part["count_group_id"],
                              "total": group["total"], "categories": group["categories"],
                              "sections": group["section_labels"], "closed_by_utility_user": False}, indent=2))
            return

        groups = client.get("/counts/review/groups", headers=group_pastor).raise_for_status().json()
        group = next(row for row in groups if row["date"][:10] == occurrence.isoformat()
                     and str(row["location_id"]) == args.location_id
                     and row["section_labels"] == ["Utility A", "Utility B"])
        assert group["total"] == 33
        response = client.post(f"/counts/review/{group['count_id']}/approve", headers=group_pastor, json={})
        response.raise_for_status()
        dashboard = client.get("/dashboard/sunday-worship", headers=group_pastor,
                               params={"occurrence_date": occurrence.isoformat()}).raise_for_status().json()
        assert dashboard["total"] == 33
        print(json.dumps({"approved_count_ids": response.json()["count_ids"],
                          "dashboard_total": dashboard["total"], "categories": dashboard["categories"]}, indent=2))


if __name__ == "__main__":
    main()
