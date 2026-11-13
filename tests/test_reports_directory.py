from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from fasthtml.common import to_xml
from starlette.datastructures import QueryParams

from app.frontend.dclm_admin import auth_context
from app.frontend.dclm_admin.auth_context import build_context
from app.frontend.dclm_admin.routes import reports


def _request(query: str = ""):
    return SimpleNamespace(query_params=QueryParams(query))


def test_reports_overview_links_to_distinct_authoritative_pages_and_keeps_scope(monkeypatch):
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    ctx = build_context({"profile": "state_overseer"})
    ctx = replace(
        ctx,
        query_extras={
            **ctx.query_extras,
            "scope_path": ctx.current_scope_path,
            "include_pending": "false",
            "weeks": "8",
            "user_name": "must-not-appear",
            "role_label": "must-not-appear",
        },
    )

    rendered = to_xml(asyncio.run(reports._overview_tab(_request("start_date=2026-10-01&end_date=2026-11-01&weeks=8"), ctx)))

    for title in (
        "Weekly attendance",
        "Special events",
        "Money",
        "New people",
        "Worker and leader meetings",
        "Print a report",
    ):
        assert title in rendered
    page_text = BeautifulSoup(rendered, "html.parser").get_text(" ", strip=True).lower()
    assert "separate reports for each weekly service" in page_text
    assert "separate meeting attendance reports" in page_text
    assert 'class="reports-overview-actions d-flex flex-wrap gap-2"' in rendered
    assert 'cls="reports-overview-actions d-flex flex-wrap gap-2"' not in rendered

    links = {}
    for anchor in BeautifulSoup(rendered, "html.parser").select("a[href]"):
        links[anchor.get_text(" ", strip=True)] = anchor["href"]

    assert set(("Sunday Worship", "Monday Bible Study", "Thursday Revival")) <= links.keys()
    assert "Retreat" in links and "Crusade" in links
    assert "Saturday Workers" in links and "Tuesday Leaders" in links
    for label in ("Sunday Worship", "Monday Bible Study", "Thursday Revival", "Retreat", "Crusade", "Money records", "Newcomers", "Saturday Workers", "Tuesday Leaders", "4 weeks", "8 weeks"):
        query = parse_qs(urlsplit(links[label]).query)
        assert query.get("scope_path") == [ctx.current_scope_path], (label, query)
        assert "user_name" not in query and "role_label" not in query
    assert parse_qs(urlsplit(links["Thursday Revival"]).query)["program_key"] == ["thursday_revival_hour"]
    assert parse_qs(urlsplit(links["Thursday Revival"]).query)["weeks"] == ["8"]
    money_query = parse_qs(urlsplit(links["Money records"]).query)
    assert money_query["date_from"] == ["2026-10-01"]
    assert money_query["date_to"] == ["2026-11-01"]


def test_reports_overview_omits_sections_the_role_cannot_read(monkeypatch):
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    ctx = build_context({"profile": "state_overseer"})
    ctx = replace(ctx, permissions=frozenset({"reports:read"}))

    rendered = to_xml(asyncio.run(reports._overview_tab(_request(), ctx)))

    assert "Print a report" in rendered
    for title in ("Weekly attendance", "Special events", "Money", "New people", "Worker and leader meetings"):
        assert title not in rendered
    assert "No reports available" not in rendered


def test_reports_default_and_existing_tab_bookmarks_are_preserved():
    assert reports._active_report_tab("unknown") == "overview"
    for tab in ("summary", "financial", "attendance", "timeseries", "breakdown", "growth", "anomalies", "exports"):
        assert reports._active_report_tab(tab) == tab
