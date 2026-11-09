"""Authenticated mobile layout sweep for the admin analytics surfaces.

Set DCLM_MOBILE_TEST_BASE_URL and DCLM_MOBILE_TEST_STATES to run. The latter
is a JSON object mapping state, region, group and location to Playwright storage
state file paths created outside the repository.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

BASE_URL = os.getenv("DCLM_MOBILE_TEST_BASE_URL", "").rstrip("/")
STATES_RAW = os.getenv("DCLM_MOBILE_TEST_STATES", "")
STATES = json.loads(STATES_RAW) if STATES_RAW else {}
pytestmark = pytest.mark.skipif(
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


def test_analytics_and_existing_admin_pages_fit_mobile_viewports():
    from playwright.sync_api import sync_playwright

    failures = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
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
