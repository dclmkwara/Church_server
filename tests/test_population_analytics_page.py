from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from starlette.requests import Request

from app.frontend.dclm_admin.app_factory import app
from app.frontend.dclm_admin.communication.dashboard_service import DashboardService
from app.frontend.dclm_admin.backend.config import get_backend_config
from app.frontend.dclm_admin.routes.population_analytics import _report_label


def _request(path: str, query: str) -> Request:
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request({
        "type": "http", "method": "GET", "path": path,
        "headers": [], "query_string": query.encode(), "path_params": {}, "app": app,
    }, receive)


def test_unapproved_report_is_not_presented_as_missing_or_zero():
    assert _report_label({"total": None, "coverage": {"pending": 1}}) == "Pending review · excluded from totals"
    assert _report_label({"total": None, "coverage": {"missing": 1}}) == "Not reported"
    assert _report_label({"total": 0, "coverage": {"approved": 1}}) == "Reported 0"


def test_population_page_drilldown_keeps_program_period_pending_and_scope(monkeypatch):
    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "mock")
    get_backend_config.cache_clear()
    monkeypatch.setattr(DashboardService, "scope_path", staticmethod(AsyncMock(return_value="dcl.234.kw")))
    current = {"occurrence_date": "2026-11-08", "total": 100, "n_counted": 1, "n_expected": 2, "n_received": 1, "coverage": {"approved": 1, "pending": 0, "returned": 0, "missing": 1}}
    child = {"path": "dcl.234.kw.ilr", "name": "Ilorin Region", "history": [current] * 8}
    monkeypatch.setattr(DashboardService, "standing_program_series", staticmethod(AsyncMock(return_value={
        "scope": [current] * 8,
        "children": [child],
            "ancestors": [{"path": "dcl.234.kw", "name": "Kwara State"}],
        "location_nodes": [],
    })))
    route = next(row for row in app.routes if getattr(row, "path", None) == "/church-data/population-attendance/content")
    response = asyncio.run(route.endpoint(_request(
        "/church-data/population-attendance/content",
        "profile=state_overseer&program_key=monday_bible_study&weeks=8&include_pending=true&scope_path=dcl.234.kw",
    )))
    html = response.body.decode()
    assert "Monday Bible Study" in html
    assert "Ilorin Region" in html
    assert "scope_path=dcl.234.kw.ilr" in html
    assert "program_key=monday_bible_study" in html
    assert "weeks=8" in html
    assert "include_pending=true" in html
    assert "No counted report" not in html
    assert "% of documented population" not in html


def test_house_fellowship_page_discloses_unit_and_no_review_status(monkeypatch):
    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "mock")
    get_backend_config.cache_clear()
    monkeypatch.setattr(DashboardService, "scope_path", staticmethod(AsyncMock(return_value="dcl.234.kw")))
    current = {"occurrence_date": "2026-11-08", "total": 13, "n_counted": 1, "n_expected": 2, "n_received": 1, "coverage": {"approved": 1, "pending": 0, "returned": 0, "missing": 1}}
    monkeypatch.setattr(DashboardService, "standing_program_series", staticmethod(AsyncMock(return_value={
        "scope": [current] * 4, "children": [],
        "ancestors": [{"path": "dcl.234.kw", "name": "Kwara State"}], "location_nodes": [],
    })))
    route = next(row for row in app.routes if getattr(row, "path", None) == "/church-data/population-attendance/content")
    response = asyncio.run(route.endpoint(_request(
        "/church-data/population-attendance/content",
        "profile=state_overseer&program_key=house_caring_fellowship&weeks=4&scope_path=dcl.234.kw",
    )))
    html = response.body.decode()
    assert "Fellowship" in html
    assert "Fellowship submissions have no approval status" in html
    assert "all saved rows are included" in html
    assert "disabled" in html


def test_sunday_summary_and_region_card_show_latest_demographics_and_expected_share(monkeypatch):
    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "mock")
    get_backend_config.cache_clear()
    monkeypatch.setattr(DashboardService, "scope_path", staticmethod(AsyncMock(return_value="dcl.234.kw")))
    current = {
        "occurrence_date": "2026-11-08", "total": 100, "n_counted": 1, "n_expected": 2, "n_received": 1,
        "categories": {"adult_male": 30, "adult_female": 25, "youth_male": 15, "youth_female": 15, "boys": 8, "girls": 7},
        "expected_population_total": 200, "expected_population_counted_total": 100,
        "expected_population_scope_total": 300, "expected_population_scope_locations": 2,
        "expected_population_no_estimate_locations": 1,
        "coverage": {"approved": 1, "pending": 0, "returned": 0, "missing": 1},
    }
    child_report = {**current, "expected_population_total": 100, "expected_population_counted_total": 50, "expected_population_scope_total": 200, "expected_population_scope_locations": 2, "expected_population_no_estimate_locations": 0}
    child = {"path": "dcl.234.kw.ilr", "name": "Ilorin Region", "history": [child_report] * 4}
    monkeypatch.setattr(DashboardService, "standing_program_series", staticmethod(AsyncMock(return_value={
        "scope": [current] * 4, "children": [child],
        "ancestors": [{"path": "dcl.234.kw", "name": "Kwara State"}], "location_nodes": [],
    })))
    route = next(row for row in app.routes if getattr(row, "path", None) == "/church-data/population-attendance/content")
    response = asyncio.run(route.endpoint(_request(
        "/church-data/population-attendance/content",
        "profile=state_overseer&program_key=sunday_worship_service&weeks=4&scope_path=dcl.234.kw",
    )))
    html = response.body.decode()
    for text in ("Program Attendance", "Latest Sunday Worship", "Adults", "Youth", "Children", "Ilorin Region", "50%", "DCL-234-KW-ILR", "across 2 of 2 locations with estimates"):
        assert text in html
    assert "program-child-card" in html
    assert "Demographic percentages are shares of counted attendance" in html
