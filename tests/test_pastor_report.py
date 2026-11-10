from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

from app.frontend.dclm_admin.routes.pastor_report import (
    _previous_period_range,
    _report_period,
    _csv_zip_bytes,
    _insights,
    _pdf_bytes,
    _sections,
    _table,
    _workbook_bytes,
)


def report_fixture():
    history = [
        {"occurrence_date": "2026-10-25", "total": 100, "categories": {"adult_male": 20, "adult_female": 25, "youth_male": 15, "youth_female": 15, "boys": 10, "girls": 15}, "n_counted": 1, "n_expected": 2, "n_received": 1, "coverage": {"approved": 1, "pending": 0, "returned": 0, "conflict": 0, "missing": 1}, "expected_population_percent": 50, "expected_population_counted_locations": 1, "expected_population_no_estimate_locations": 0},
        {"occurrence_date": "2026-11-01", "total": 0, "categories": {"adult_male": 0, "adult_female": 0, "youth_male": 0, "youth_female": 0, "boys": 0, "girls": 0}, "n_counted": 1, "n_expected": 2, "n_received": 1, "coverage": {"approved": 1, "pending": 0, "returned": 0, "conflict": 0, "missing": 1}, "expected_population_percent": 0, "expected_population_counted_locations": 1, "expected_population_no_estimate_locations": 0},
    ]
    location_history = [
        {**history[0], "status": "approved", "expected_population_total": 200},
        {**history[1], "status": "approved", "expected_population_total": 200},
    ]
    return {
        "scope_name": "Test Region", "scope_path": "dclm.234.kw.test", "period": "4w", "period_label": "Last 4 Sundays (25 Oct – 1 Nov 2026)",
        "start_date": __import__("datetime").date(2026, 10, 25), "end_date": __import__("datetime").date(2026, 11, 1),
        "include_pending": False, "summary": {"pending_approvals": [], "attendance_summary": {}, "newcomer_period": {}},
        "series": {"locations": [{"name": "Sample Location", "path": "dclm.234.kw.test.sample", "location_id": "loc-1", "history": location_history}]},
        "history": history, "all_history": history, "previous_history": [], "children": [{"name": "Sample Group", "path": "dclm.234.kw.test.group", "history": history}],
        "standing": {"house_caring_fellowship": {"scope": [history[0], history[1]]}},
        "offerings": [{"date": "2026-11-01", "program": "Sunday Worship", "fund_type": "Tithe", "status": "approved", "amount": 1000, "records": 1}],
        "offering_summary": {"approved": 1000.0, "pending": 0.0, "approved_records": 1, "pending_records": 0}, "offering_previous": {"approved": 800.0, "pending": 0.0, "approved_records": 1, "pending_records": 0},
        "events": [], "campaigns": [], "selected_campaign": None,
        "generated_at": datetime(2026, 11, 2, 10, 30, tzinfo=ZoneInfo("Africa/Lagos")), "generated_by": "Pastor Test",
    }


def test_insights_distinguish_missing_from_zero_and_are_repeatable():
    data = report_fixture()
    first = _insights(data["all_history"], data["children"], data["summary"])
    second = _insights(data["all_history"], data["children"], data["summary"])
    assert first == second
    assert any("missing" in item["how"].lower() for item in first)
    assert data["history"][1]["total"] == 0
    assert "No report" not in str(data["history"][1]["total"])


def test_empty_report_has_explicit_findings_and_calendar_periods():
    assert len(_insights([], [], {})) == 3
    month = _report_period("month", __import__("datetime").date(2026, 11, 8))
    quarter = _report_period("quarter", __import__("datetime").date(2026, 11, 8))
    assert month[1] == __import__("datetime").date(2026, 11, 1) and month[3] == 2
    assert quarter[1] == __import__("datetime").date(2026, 10, 1) and quarter[3] == 6
    assert _previous_period_range("month", month[1], month[2]) == (__import__("datetime").date(2026, 10, 1), __import__("datetime").date(2026, 10, 8))


def test_excel_and_csv_export_have_location_coverage_and_six_categories():
    data = report_fixture()
    workbook = load_workbook(io.BytesIO(_workbook_bytes(data)), read_only=True, data_only=True)
    assert {"Summary", "Weekly by unit", "Location coverage", "Counts by category", "Offerings summary", "Retreat Crusade", "Definitions", "House Caring Fellowship"}.issubset(workbook.sheetnames)
    coverage = list(workbook["Location coverage"].values)
    assert coverage[1][0:5] == ("Sample Location", "dclm.234.kw.test.sample", "2026-10-25", "Counted", 100)
    assert coverage[1][5:11] == (20, 25, 15, 15, 10, 15)
    assert coverage[2][4] == 0
    assert "Pastor Test" not in str(coverage)
    with zipfile.ZipFile(io.BytesIO(_csv_zip_bytes(data))) as archive:
        names = set(archive.namelist())
        assert "location_coverage.csv" in names
        rows = list(csv.reader(io.StringIO(archive.read("counts_by_category.csv").decode())))
        assert "Adult male" in rows[0]
        assert all("nan" not in cell.lower() and "undefined" not in cell.lower() for row in rows for cell in row)


def test_pdf_export_has_brand_footer_and_page_number_and_is_pdf():
    content = _pdf_bytes(report_fixture())
    assert content.startswith(b"%PDF-")
    assert b"Powered by: Kwara State ICT Unit" in content
    assert b"Page 1" in content


def test_table_escapes_stored_text():
    rendered = str(_table(["Name"], [["<script>alert(1)</script>"]]))
    assert "&lt;script&gt;" in rendered
    assert "<script>" not in rendered


def test_empty_newcomer_and_convert_records_are_not_reported_as_zero():
    data = report_fixture()
    sections = dict(_sections(data))
    html = str(sections["Newcomers and converts"])
    assert "No newcomer or convert records are available" in html
    assert "No records does not mean a reported zero" in html
    pdf = _pdf_bytes(data)
    assert b"No newcomer or convert records are available" in pdf


def test_report_totals_and_offerings_state_match_dashboard_fixture():
    data = report_fixture()
    sections = dict(_sections(data))
    offerings = str(sections["Offerings and tithes"])
    assert "Approved in period: \u20a61,000.00 across 1 records." in offerings
    data["history"][-1]["total"] = None
    assert "No report" in str(dict(_sections(data))["Attendance"])
    data["offering_summary"] = {"approved": 0, "pending": 0, "approved_records": 0, "pending_records": 0}
    no_offerings = dict(_sections(data))["Offerings and tithes"]
    assert "No approved offering records" in str(no_offerings)
