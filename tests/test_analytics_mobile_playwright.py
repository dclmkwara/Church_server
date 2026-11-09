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
PAGES = {
    "dashboard": "/dashboard",
    "retreat": "/church-data/programs/analytics/retreat",
    "crusade": "/church-data/programs/analytics/crusade",
    "leaders": "/church-data/meetings/leaders-tuesday",
    "workers-meeting": "/church-data/meetings/workers-saturday",
    "count-review": "/church-data/count-review",
    "expected-attendance": "/analytics/expected-population",
    "attendance": "/church-data/attendance",
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
                    if page_name == "dashboard" and width < 640:
                        card_rows = page.locator(".analytics-child-table-wrap tbody tr.analytics-row")
                        if card_rows.count():
                            display = card_rows.first.evaluate("element => getComputedStyle(element).display")
                            if display != "grid":
                                failures.append(f"{persona} dashboard {width}px: child rows are not stacked cards")
                    for control in page.locator(".analytics-remind-form button, .analytics-child-link, .analytics-attention-title").all():
                        if control.is_visible() and control.evaluate("element => element.getBoundingClientRect().height") < 40:
                            failures.append(f"{persona} {page_name} {width}px: analytics action/link target is under 40px")
            context.close()
        browser.close()
    assert not failures, "Mobile layout violations:\n" + "\n".join(failures)


def test_analytics_dashboard_stacks_content_panels_below_640px():
    """Keep the groups table and attention panel full-width in the shell cascade."""
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
            expected_columns = 1 if width <= 640 else 2
            assert len(grid_columns.split()) == expected_columns, (
                f"Expected {expected_columns} column(s) at {width}px, got {grid_columns}"
            )
            if expected_columns == 1:
                assert panel_widths[0] == panel_widths[1] and panel_widths[0] > 0
        browser.close()


def test_dashboard_does_not_reintroduce_a_stale_analytics_stylesheet():
    """The dashboard fragment must use the shared shell stylesheet exactly once."""
    root = Path(__file__).parents[1]
    dashboard_route = (root / "app/frontend/dclm_admin/routes/analytics_dashboard.py").read_text(encoding="utf-8")
    shell = (root / "app/frontend/dclm_admin/components/shell.py").read_text(encoding="utf-8")
    assert "analytics-dashboard.css" not in dashboard_route
    assert 'analytics-dashboard.css?v=10' in shell
