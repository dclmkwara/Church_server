"""Environment-gated live page/export reconciliation against independent SQL.

Set F3_DATABASE_URL to a disposable local clone, F3_BASE_URL to its running
Church Admin app, F3_SCOPE_PATHS to four comma-separated paths (state, region,
group, location), and F3_COOKIE_STATE to a Playwright storage-state JSON file.
The test never writes to the database.
"""
from __future__ import annotations

import io
import csv
import json
import os
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import pytest
from bs4 import BeautifulSoup
from openpyxl import load_workbook
from sqlalchemy import create_engine, text


pytestmark = pytest.mark.skipif(
    not all(os.getenv(name) for name in (
        "F3_DATABASE_URL", "F3_BASE_URL", "F3_SCOPE_PATHS", "F3_COOKIE_STATE",
    )),
    reason="F3 live reconciliation requires an explicitly configured disposable local app/DB and browser state",
)


def _cookies(storage_state: Path) -> dict[str, str]:
    state = json.loads(storage_state.read_text(encoding="utf-8"))
    return {row["name"]: row["value"] for row in state.get("cookies", [])}


def _independent_counts(connection, scope_path: str, start: date, end: date) -> dict[str, dict[str, int]]:
    query = text("""
        WITH accepted AS (
          SELECT c.*, coalesce(nullif(c.program_scope_path, ''), c.path) AS report_path
          FROM counts c
          WHERE c.status='approved' AND c.is_deleted IS NOT TRUE
            AND c.program_type_id=1
            AND c.date::date BETWEEN :start_date AND :end_date
        ), local_rows AS (
          SELECT a.* FROM accepted a
          WHERE lower(coalesce(a.program_level,'local')) IN ('local','location')
            AND (a.path=:scope_path OR a.path LIKE :scope_path || '.%')
            AND NOT EXISTS (
              SELECT 1 FROM accepted x
              WHERE lower(x.program_level) IN ('group','region','state')
                AND x.date::date=a.date::date AND a.path LIKE x.report_path || '.%'
            )
        ), combined_rows AS (
          SELECT a.* FROM accepted a
          WHERE lower(coalesce(a.program_level,'')) IN ('group','region','state')
            AND (a.report_path=:scope_path OR a.report_path LIKE :scope_path || '.%')
        ), effective_rows AS (
          SELECT * FROM local_rows UNION ALL SELECT * FROM combined_rows
        )
        SELECT date::date AS occurrence_date, sum(adult_male) adult_male,
          sum(adult_female) adult_female, sum(youth_male) youth_male,
          sum(youth_female) youth_female, sum(boys) children_male,
          sum(girls) children_female, sum(total) population
        FROM effective_rows GROUP BY 1 ORDER BY 1
    """)
    return {
        row["occurrence_date"].isoformat(): {key: row[key] for key in (
            "adult_male", "adult_female", "youth_male", "youth_female",
            "children_male", "children_female", "population",
        )}
        for row in connection.execute(query, {
            "scope_path": scope_path, "start_date": start, "end_date": end,
        }).mappings()
    }


def _independent_report_summary(connection, scope_path: str, start: date, end: date) -> list[dict]:
    """Independent Reports Summary SQL: parts group only by count_group_id."""
    query = text("""
        WITH source_rows AS (
          SELECT c.id, c.count_group_id, c.date::date AS day, c.event_id,
                 c.location_id, l.location_name, c.path::text AS path,
                 c.status, c.total, c.adult_male, c.adult_female,
                 c.youth_male, c.youth_female, c.boys, c.girls,
                 coalesce(cg.state, '') AS group_state,
                 coalesce(cg.service_id, 'main') AS service_id,
                 coalesce(pe.title, pt.name, c.program_type, c.program_domain, 'Unassigned program') AS program
          FROM counts c
          JOIN locations l ON l.location_id = c.location_id
          LEFT JOIN count_groups cg ON cg.id = c.count_group_id
          LEFT JOIN program_events pe ON pe.id = c.event_id
          LEFT JOIN program_types pt ON pt.id = coalesce(c.program_type_id, pe.program_type_id)
          WHERE c.date >= :start_date
            AND c.date < (CAST(:end_date AS date) + INTERVAL '1 day')
            AND c.is_deleted IS NOT TRUE
            AND (c.path <@ CAST(:scope_path AS ltree) OR c.path = CAST(:scope_path AS ltree))
        ), logical_groups AS (
          SELECT coalesce('group:' || count_group_id::text, 'legacy:' || id::text) AS occurrence_id,
                 day, event_id, location_id, location_name, path, service_id, program,
                 bool_and(lower(status) = 'approved') AS entirely_approved,
                 bool_or(group_state = 'conflict') AS is_conflicted,
                 count(*) AS record_count, sum(total) AS total,
                 sum(adult_male) AS adult_male, sum(adult_female) AS adult_female,
                 sum(youth_male) AS youth_male, sum(youth_female) AS youth_female,
                 sum(boys) AS boys, sum(girls) AS girls
          FROM source_rows
          GROUP BY 1,2,3,4,5,6,7,8
        )
        SELECT * FROM logical_groups
        WHERE entirely_approved AND NOT is_conflicted
        ORDER BY day DESC, path, service_id
    """)
    return [dict(row) for row in connection.execute(query, {
        "scope_path": scope_path, "start_date": start, "end_date": end,
    }).mappings()]


def _reports_summary_from_html(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    wrapper = soup.select_one("#reports-summary-table")
    table = wrapper if wrapper and wrapper.name == "table" else (wrapper.find("table") if wrapper else None)
    assert table is not None, "Reports Summary table was not rendered"
    headers = [cell.get_text(" ", strip=True).lower() for cell in table.select("thead th")]
    output = []
    for tr in table.select("tbody tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        if len(cells) == len(headers):
            output.append(dict(zip(headers, cells)))
    return output


def test_pastor_report_html_and_xlsx_match_independent_sql_for_four_scopes():
    db_url = os.environ["F3_DATABASE_URL"]
    if db_url.startswith("postgresql://"):
        db_host = urlparse(db_url).hostname
    else:
        db_host = urlparse(db_url.replace("postgresql+psycopg2://", "postgresql://", 1)).hostname
    assert db_host in {"127.0.0.1", "localhost", "::1"}, "refusing a non-local F3 database"
    base_url = os.environ["F3_BASE_URL"].rstrip("/")
    assert urlparse(base_url).hostname in {"127.0.0.1", "localhost", "::1"}, "refusing a non-local F3 app"
    scopes = [item.strip() for item in os.environ["F3_SCOPE_PATHS"].split(",") if item.strip()]
    assert len(scopes) == 4
    cookies = _cookies(Path(os.environ["F3_COOKIE_STATE"]))
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(db_url)
    try:
        with engine.connect() as connection, httpx.Client(
            base_url=base_url, cookies=cookies, follow_redirects=True, timeout=90,
        ) as client:
            for scope_path in scopes:
                params = {"period": "recent", "scope_path": scope_path, "profile": "state_overseer"}
                html_response = client.get("/dashboard/pastor-report", params=params)
                assert html_response.status_code == 200
                soup = BeautifulSoup(html_response.text, "html.parser")
                html_rows = {}
                for table in soup.select("table"):
                    headers = [cell.get_text(" ", strip=True).upper() for cell in table.select("thead th")]
                    if not headers or headers[0] != "SUNDAY" or "POPULATION" not in headers:
                        continue
                    indexes = {name: headers.index(name) for name in ("SUNDAY", "POPULATION")}
                    category_index = next((i for i, name in enumerate(headers) if "CATEGOR" in name), None)
                    for row in table.select("tbody tr"):
                        cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
                        if len(cells) == len(headers):
                            categories = {}
                            if category_index is not None:
                                for label, value in re.findall(
                                    r"(Adult male|Adult female|Youth male|Youth female|Children male|Children female)\s+([\d,]+)",
                                    cells[category_index], re.I,
                                ):
                                    categories[label.upper()] = int(value.replace(",", ""))
                            html_rows[cells[indexes["SUNDAY"]]] = (cells, categories)
                assert html_rows, f"report attendance table not rendered at {scope_path}"

                export = client.get("/dashboard/pastor-report/export.xlsx", params=params)
                assert export.status_code == 200
                workbook = load_workbook(io.BytesIO(export.content), read_only=True, data_only=True)
                sheet = workbook["Counts by category"]
                rows = list(sheet.values)
                header = [str(item or "").upper() for item in rows[0]]
                workbook_rows = {str(row[0]): row for row in rows[1:] if len(row) > 2 and row[2] == scope_path}

                latest_sunday = datetime.now(ZoneInfo("Africa/Lagos")).date()
                latest_sunday -= timedelta(days=(latest_sunday.weekday() + 1) % 7)
                start_sunday = latest_sunday - timedelta(days=21)
                expected = _independent_counts(connection, scope_path, start_sunday, latest_sunday)
                expected_dates = [(start_sunday + timedelta(days=7 * i)).isoformat() for i in range(4)]
                csv_response = client.get("/dashboard/pastor-report/export.csv", params=params)
                assert csv_response.status_code == 200
                with zipfile.ZipFile(io.BytesIO(csv_response.content)) as archive:
                    csv_rows = list(csv.reader(io.StringIO(archive.read("counts_by_category.csv").decode("utf-8-sig"))))
                csv_header = [item.strip().upper() for item in csv_rows[0]]
                csv_by_date = {
                    row[csv_header.index("SUNDAY")]: row
                    for row in csv_rows[1:]
                    if len(row) > 2 and row[csv_header.index("SCOPE PATH")] == scope_path
                }
                for occurrence in expected_dates:
                    assert occurrence in html_rows, f"HTML missing occurrence {occurrence} at {scope_path}"
                    assert occurrence in workbook_rows, f"XLSX missing occurrence {occurrence} at {scope_path}"
                    assert occurrence in csv_by_date, f"CSV missing occurrence {occurrence} at {scope_path}"
                    row = expected.get(occurrence)
                    html, html_categories = html_rows[occurrence]
                    xlsx = workbook_rows[occurrence]
                    csv_row = csv_by_date[occurrence]
                    if row is None:
                        assert html[indexes["POPULATION"]].lower() in {"no report", "not reported", ""}
                        assert xlsx[header.index("STATUS")] == "Not reported"
                        assert not xlsx[header.index("TOTAL")]
                        assert csv_row[csv_header.index("STATUS")] == "Not reported"
                        assert not csv_row[csv_header.index("TOTAL")]
                        continue
                    for label, key in (
                        ("POPULATION", "population"), ("ADULT MALE", "adult_male"),
                        ("ADULT FEMALE", "adult_female"), ("YOUTH MALE", "youth_male"),
                        ("YOUTH FEMALE", "youth_female"), ("CHILDREN MALE", "children_male"),
                        ("CHILDREN FEMALE", "children_female"),
                    ):
                        value = row[key]
                        assert value is not None
                        if label == "POPULATION":
                            rendered = "".join(ch for ch in html[indexes[label]] if ch.isdigit())
                            assert int(rendered.replace(",", "") or 0) == int(value), (scope_path, occurrence, label, rendered, value)
                        elif value:
                            assert html_categories.get(label) == int(value), (scope_path, occurrence, label, html_categories.get(label), value)
                    xlsx_map = {name: header.index(name) for name in header}
                    assert int(xlsx[xlsx_map["TOTAL"]] or 0) == int(row["population"] or 0)
                    assert int(csv_row[csv_header.index("TOTAL")] or 0) == int(row["population"] or 0)
                    for label, key in (
                        ("ADULT MALE", "adult_male"), ("ADULT FEMALE", "adult_female"),
                        ("YOUTH MALE", "youth_male"), ("YOUTH FEMALE", "youth_female"),
                        ("CHILDREN MALE", "children_male"), ("CHILDREN FEMALE", "children_female"),
                    ):
                        value = int(row[key] or 0)
                        assert int(xlsx[xlsx_map[label]] or 0) == value
                        assert int(csv_row[csv_header.index(label)] or 0) == value

                # Reports Summary and its counted-count export are rendered
                # and fetched through the running frontend/API, then compared
                # with independent source-row SQL. The scope loop is ordered
                # State, Region, Group, Location by the documented fixture.
                summary_expected = _independent_report_summary(connection, scope_path, start_sunday, latest_sunday)
                reports_params = {
                    "tab": "summary", "scope_path": scope_path, "profile": "state_overseer",
                    "start_date": start_sunday.isoformat(), "end_date": latest_sunday.isoformat(),
                }
                summary_response = client.get("/reports/content", params=reports_params)
                assert summary_response.status_code == 200
                rendered_summary = _reports_summary_from_html(summary_response.text)
                expected_summary = sorted(
                    (row["day"].isoformat(), row["location_name"], row["program"] if row["service_id"] == "main" else f"{row['program']} · {row['service_id']}", row["service_id"], int(row["total"]), "Approved")
                    for row in summary_expected
                )
                actual_summary = sorted(
                    (row["date"], row["location"], row["program"], row["service/session"], int(row["total"].replace(",", "")), row["status"])
                    for row in rendered_summary
                )
                assert actual_summary == expected_summary, (scope_path, actual_summary, expected_summary)

                count_export = client.get("/reports/export/live", params={
                    "report_type": "counts", "export_format": "csv", "scope_path": scope_path,
                    "start_date": start_sunday.isoformat(), "end_date": latest_sunday.isoformat(),
                })
                assert count_export.status_code == 200
                exported_counts = list(csv.DictReader(io.StringIO(count_export.text)))
                csv_occurrences = sorted(
                    (row["day"], row["location_name"], row["event_title"], row.get("service_id") or "main", int(row["total_attendance"]), row["status"].title())
                    for row in exported_counts
                )
                assert csv_occurrences == expected_summary, (scope_path, csv_occurrences, expected_summary)
    finally:
        engine.dispose()
