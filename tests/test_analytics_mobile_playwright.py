"""Authenticated mobile layout sweep for the admin analytics surfaces.

Set DCLM_MOBILE_TEST_BASE_URL and DCLM_MOBILE_TEST_STATES to run. The latter
is a JSON object mapping state, region, group and location to Playwright storage
state file paths created outside the repository.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

BASE_URL = os.getenv("DCLM_MOBILE_TEST_BASE_URL", "").rstrip("/")
STATES_RAW = os.getenv("DCLM_MOBILE_TEST_STATES", "")
STATES = json.loads(STATES_RAW) if STATES_RAW else {}
authenticated_sweep_requires_env = pytest.mark.skipif(
    not BASE_URL or set(STATES) != {"state", "region", "group", "location"},
    reason="Set DCLM_MOBILE_TEST_BASE_URL and persona storage-state files to run the authenticated mobile sweep.",
)

PERSONAS = ("state", "region", "group", "location")
VIEWPORTS = ((360, 740), (390, 844), (768, 1024))
ANALYTICS_PAGES = {
    "dashboard": "/dashboard",
    "retreat": "/church-data/programs/analytics/retreat",
    "crusade": "/church-data/programs/analytics/crusade",
    "leaders": "/church-data/meetings/leaders-tuesday",
    "workers-meeting": "/church-data/meetings/workers-saturday",
    "count-review": "/church-data/count-review",
    "expected-attendance": "/analytics/expected-population",
    "attendance": "/church-data/attendance",
    "recurring-program-attendance": "/church-data/population-attendance",
    "finance-analytics": "/church-data/finance",
    "newcomers": "/church-data/newcomers",
    "pastor-report": "/dashboard/pastor-report",
}
PAGES = {
    **ANALYTICS_PAGES,
    "Inbox": "/inbox",
    "People": "/people/workers",
    "Church data": "/church-data/programs",
    "Finance": "/church-data/finance",
    "Fellowship": "/fellowship",
    "Organization": "/organization",
    "Reports": "/reports",
    "Programs": "/church-data/programs",
}


def _launch_chromium(runtime):
    """Prefer Playwright's browser, then fall back to an installed Chrome/Edge."""
    candidates = [
        os.getenv("DCLM_CHROME_PATH"),
        shutil.which("chrome"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    executable = next((path for path in candidates if path and Path(path).is_file()), None)
    options = {"headless": True}
    if executable:
        options["executable_path"] = executable
    return runtime.chromium.launch(**options)


def _layout_violations(page, viewport_width: int) -> list[str]:
    return page.evaluate(
        """(viewportWidth) => {
          const problems = [];
          if (document.documentElement.scrollWidth > viewportWidth) {
            problems.push(`document scrollWidth ${document.documentElement.scrollWidth} > ${viewportWidth}`);
          }
          for (const element of document.querySelectorAll('body *')) {
            const rect = element.getBoundingClientRect();
            if (!rect.width || !rect.height) continue;
            const style = getComputedStyle(element);
            if (element.closest('.offcanvas:not(.show)')) continue;
            if (typeof element.checkVisibility === 'function' && !element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) continue;
            if (element.closest('.prototype-dashboard,#program-analytics-content,#count-review-content,.expected-population-table') &&
                element.tagName !== 'SUMMARY' &&
                element.textContent.trim() && style.fontSize && parseFloat(style.fontSize) < 10) {
              problems.push(`${element.tagName}.${element.className} text is ${style.fontSize}`);
              break;
            }
            const scroller = element.closest('[style*="overflow-x: auto"], .table-responsive, .analytics-table-wrap');
            if (rect.right > viewportWidth + 1 && !scroller && style.position !== 'fixed') {
              problems.push(`${element.tagName}.${element.className} extends to ${Math.round(rect.right)}px`);
              break;
            }
            if ((style.overflow === 'hidden' || style.overflowX === 'hidden') &&
                (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1) &&
                !element.matches('.visually-hidden,[aria-hidden="true"]')) {
              problems.push(`${element.tagName}.${element.className} clips content`);
              break;
            }
          }
          for (const button of document.querySelectorAll('.analytics-attention-item button')) {
            const buttonRect = button.getBoundingClientRect();
            const content = button.closest('.analytics-attention-copy') || button.parentElement;
            for (const textNode of content.querySelectorAll('.analytics-attention-title,.analytics-attention-meta')) {
              const textRect = textNode.getBoundingClientRect();
              const overlaps = buttonRect.left < textRect.right && buttonRect.right > textRect.left &&
                buttonRect.top < textRect.bottom && buttonRect.bottom > textRect.top;
              if (overlaps) {
                problems.push('an attention action overlaps its title or metadata');
                break;
              }
            }
          }
          return problems;
        }""",
        viewport_width,
    )


@authenticated_sweep_requires_env
def test_analytics_and_existing_admin_pages_fit_mobile_viewports():
    from playwright.sync_api import sync_playwright

    failures = []
    with sync_playwright() as runtime:
        browser = _launch_chromium(runtime)
        for persona in PERSONAS:
            context = browser.new_context(storage_state=str(Path(STATES[persona]).resolve()))
            page = context.new_page()
            for width, height in VIEWPORTS:
                page.set_viewport_size({"width": width, "height": height})
                for page_name, route in PAGES.items():
                    response = page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded", timeout=30_000)
                    if response and response.status >= 500:
                        failures.append(f"{persona} {page_name} {width}px returned HTTP {response.status}")
                        continue
                    page.wait_for_timeout(100)
                    failures.extend(
                        f"{persona} {page_name} {width}px: {issue}"
                        for issue in _layout_violations(page, width)
                    )
                    if page_name in ANALYTICS_PAGES and width < 640:
                        card_rows = page.locator(".analytics-child-table-wrap tbody tr.analytics-row")
                        if card_rows.count():
                            display = card_rows.first.evaluate("element => getComputedStyle(element).display")
                            if display != "grid":
                                failures.append(f"{persona} dashboard {width}px: child rows are not stacked cards")
                    for control in page.locator(".analytics-remind-form button, .analytics-child-link, .analytics-attention-title, .analytics-info summary").all():
                        if control.is_visible() and control.evaluate("element => element.getBoundingClientRect().height") < 40:
                            failures.append(f"{persona} {page_name} {width}px: analytics action/link target is under 40px")
            context.close()
        browser.close()
    assert not failures, "Mobile layout violations:\n" + "\n".join(failures)


def test_analytics_dashboard_stacks_content_panels_on_tablet_and_phone():
    """Keep dashboard content full width through tablet sizes."""
    from playwright.sync_api import sync_playwright

    assets = Path(__file__).parents[1] / "app/frontend/dclm_admin/assets/css"
    admin_style = (assets / "admin.css").read_text(encoding="utf-8")
    analytics_style = (assets / "analytics-dashboard.css").read_text(encoding="utf-8")
    with sync_playwright() as runtime:
        browser = _launch_chromium(runtime)
        page = browser.new_page()
        for width, height in ((320, 740), (360, 740), (390, 844), (640, 900), (768, 1024)):
            page.set_viewport_size({"width": width, "height": height})
            page.set_content(
                f"""<style>{admin_style}</style><style>{analytics_style}</style>
                <main class="prototype-dashboard">
                  <div class="analytics-content-split">
                    <section class="analytics-table-panel">Groups</section>
                    <section class="analytics-attention-panel">Needs attention</section>
                  </div>
                </main>"""
            )
            grid_columns = page.locator(".analytics-content-split").evaluate(
                "element => getComputedStyle(element).gridTemplateColumns"
            )
            panel_widths = page.locator(".analytics-content-split > *").evaluate_all(
                "elements => elements.map(element => Math.round(element.getBoundingClientRect().width))"
            )
            expected_columns = 1 if width <= 900 else 2
            assert len(grid_columns.split()) == expected_columns, (
                f"Expected {expected_columns} column(s) at {width}px, got {grid_columns}"
            )
            if expected_columns == 1:
                assert panel_widths[0] == panel_widths[1] and panel_widths[0] > 0
        browser.close()


def test_consolidated_menu_fits_mobile_and_tablet_for_all_personas(monkeypatch):
    """Render the real permission-filtered sidebar for all eight personas."""
    from types import SimpleNamespace
    from fasthtml.common import to_xml
    from app.frontend.dclm_admin.auth_context import build_context
    from app.frontend.dclm_admin import auth_context
    from app.frontend.dclm_admin.components import shell
    from app.frontend.dclm_admin.components.shell import _sidebar
    from playwright.sync_api import sync_playwright

    monkeypatch.setattr(shell, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    css_root = Path(__file__).parents[1] / "app/frontend/dclm_admin/assets/css"
    admin_css = (css_root / "admin.css").read_text(encoding="utf-8")
    analytics_css = (css_root / "analytics-dashboard.css").read_text(encoding="utf-8")
    personas = (
        "location_pastor", "location_admin", "group_pastor", "group_admin",
        "region_pastor", "region_admin", "state_overseer", "state_admin",
    )

    with sync_playwright() as runtime:
        browser = _launch_chromium(runtime)
        page = browser.new_page()
        for persona in personas:
            ctx = build_context({"profile": persona})
            sidebar = to_xml(_sidebar(ctx, "dashboard"))
            for width, height in ((360, 740), (390, 844), (768, 1024)):
                page.set_viewport_size({"width": width, "height": height})
                page.set_content(
                    f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
                    f"<style>body{{margin:0}}</style><style>{admin_css}</style><style>{analytics_css}</style>"
                    f"<div class='admin-sidebar-shell' style='box-sizing:border-box;width:min(100%, 320px);height:100vh;padding:12px'>"
                    f"{sidebar}</div>"
                )
                assert page.evaluate("document.documentElement.scrollWidth") <= width, persona
                links = page.locator(".sidebar-link")
                assert links.count() > 0
                for link in links.all():
                    assert link.evaluate("e => e.getBoundingClientRect().height") >= 40, (
                        persona, width, link.inner_text()
                    )
                if persona.endswith("admin") or persona == "state_admin":
                    assert page.get_by_text("Count Review", exact=True).count() == 0, persona
        browser.close()


def test_dashboard_does_not_reintroduce_a_stale_analytics_stylesheet():
    """The dashboard fragment must use the shared shell stylesheet exactly once."""
    root = Path(__file__).parents[1]
    dashboard_route = (root / "app/frontend/dclm_admin/routes/analytics_dashboard.py").read_text(encoding="utf-8")
    shell = (root / "app/frontend/dclm_admin/components/shell.py").read_text(encoding="utf-8")
    assert "analytics-dashboard.css" not in dashboard_route
    assert 'analytics-dashboard.css?v=20261111_01' in shell


def test_rendered_dashboard_components_fit_phone_and_tablet_widths():
    """Exercise the real dashboard components without requiring login credentials."""
    from playwright.sync_api import sync_playwright
    from datetime import date
    from types import SimpleNamespace
    from urllib.parse import urlencode
    from fasthtml.common import to_xml
    from app.frontend.dclm_admin.routes.analytics_dashboard import (
        _attention_panel,
        _children_table,
        _line_chart,
    )

    css_root = Path(__file__).parents[1] / "app/frontend/dclm_admin/assets/css"
    base_css = (css_root / "admin.css").read_text(encoding="utf-8")
    analytics_css = (css_root / "analytics-dashboard.css").read_text(encoding="utf-8")
    personas = {
        "State": ("org.234.kw", "org.234.kw.region"),
        "Region": ("org.234.kw.region", "org.234.kw.region.group"),
        "Group": ("org.234.kw.region.group", "org.234.kw.region.group.location"),
        "Location": ("org.234.kw.region.group.location", ""),
    }

    def make_context(kind, path):
        def url_for(url, **params):
            return f"{url}?{urlencode(params)}" if params else url
        return SimpleNamespace(
            current_scope_path=path, current_scope_kind=kind,
            current_scope_label=f"{kind} name", current_scope_level={"State": 5, "Region": 4, "Group": 3, "Location": 2}[kind],
            profile=SimpleNamespace(root_path=path, key=kind.lower()),
            query_extras={"scope_path": path, "home_path": path, "period": "month", "weeks": "8", "include_pending": "false"},
            url_for=url_for, has_permission=lambda _permission: True,
        )

    with sync_playwright() as runtime:
        browser = _launch_chromium(runtime)
        for kind, (scope_path, child_path) in personas.items():
            context = browser.new_context(viewport={"width": 390, "height": 844})
            page = context.new_page()
            ctx = make_context(kind, scope_path)
            children = [{"name": f"{kind} child", "path": child_path}] if child_path else []
            rows = [{"overview": {"n_expected": 4, "n_received": 2, "n_counted": 2, "total": 470, "expected_population_total": 400, "expected_population_percent": 117.5, "coverage": {"pending": 1, "missing": 2}}}] if child_path else []
            table_html = to_xml(_children_table(children, rows, kind, ctx))
            queue = [{"location_id": "loc-a", "program_scope_path": child_path or scope_path, "age_hours": 61 * 24, "program_type": "Sunday Worship"}]
            attention_html = to_xml(_attention_panel(
                {}, queue, children,
                [{"overview": {"n_expected": 4, "n_received": 2, "coverage": {"missing": 2}}}] if child_path else [],
                {"missing_locations": [{"location_id": "loc-missing", "path": (child_path or scope_path) + ".missing"}]},
                ctx, date(2026, 11, 8), "sunday-worship",
            ))
            chart_html = to_xml(_line_chart([
                {"date": f"2026-10-{day:02d}", "average": 120 + day, "counted": 3, "expected": 4}
                for day in (4, 11, 18, 25)
            ], 4))
            page.set_content(
                f"<style>{base_css}</style><style>{analytics_css}</style>"
                f"<main class='prototype-dashboard'><div class='analytics-dashboard-main'>"
                f"<h1 class='analytics-title'>{kind} name</h1><div class='analytics-content-split'>"
                f"{table_html}{attention_html}</div><section class='panel analytics-trend-panel'>"
                f"<h2>Weekly trend</h2>{chart_html}</section></div></main>"
            )
            for width, height in ((360, 740), (390, 844), (768, 1024)):
                page.set_viewport_size({"width": width, "height": height})
                problems = _layout_violations(page, width)
                assert not problems, f"{kind} at {width}px: {problems}"
                if width < 640 and child_path:
                    assert page.locator(".analytics-child-table-wrap tr.analytics-row").first.evaluate(
                        "element => getComputedStyle(element).display"
                    ) == "grid"
                title = page.locator(".analytics-attention-title").first
                if title.count():
                    action = page.locator(".analytics-attention-item button").first
                    if action.count():
                        assert action.bounding_box()["y"] >= title.bounding_box()["y"] + title.bounding_box()["height"]
                effective_svg_font = page.locator(".analytics-svg-label").first.evaluate(
                    "element => parseFloat(getComputedStyle(element).fontSize) * element.ownerSVGElement.getBoundingClientRect().width / element.ownerSVGElement.viewBox.baseVal.width"
                )
                assert effective_svg_font >= 11, f"{kind} SVG label is {effective_svg_font:.1f}px at {width}px"
                for control in page.locator(".analytics-child-link, .analytics-attention-title, .analytics-remind-form button, .analytics-info summary").all():
                    assert control.evaluate("element => element.getBoundingClientRect().height") >= 40
            context.close()
        browser.close()
