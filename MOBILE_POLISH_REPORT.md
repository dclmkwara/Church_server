# Mobile Dashboard Polish Report

**Status:** Implemented locally and verified with rendered dashboard components. The authenticated four-persona route sweep remains available but was skipped because this run has no Playwright storage-state files configured.

## What caused the layout failure

The dashboard had competing grid rules. A more specific `.prototype-dashboard .analytics-content-split` rule restored a two-column layout after the generic responsive rule. That kept the Groups and Needs attention panels side by side on a phone and squeezed their contents into very narrow columns. The stylesheet URL also used a small cache version, so a browser could continue using the earlier layout.

The mobile override now forces one `minmax(0, 1fr)` column through 900px and the shell references a new stylesheet version. Child rows keep the child name and coverage summary on the first row, then show the key numbers in a compact two-column grid. The child name remains a real link and the whole row remains a tap target.

## Changes

- Needs-attention content is laid out vertically: linked title, metadata beneath it, then the reminder action. Reminder actions cannot sit inside wrapped title text.
- Technical metric badges are replaced by keyboard-operable “i” controls with short definitions. The classification label is no longer displayed in the card.
- The single-crumb breadcrumb is hidden. The dashboard subtitle reports whether pending reports are included. Mock mode is labelled “Demo data.”
- Waiting ages display in hours below 48 hours and in days from 48 hours onward.
- Returned reports remain red circles; conflicts use a distinct purple diamond and striped segment.
- Trend axis and date labels are scaled for at least 11px effective text. Existing label thinning is retained, and the legend wraps below the chart.
- Dashboard bottom padding is reduced while still reserving room for fixed navigation. The shared stylesheet cache key was bumped.
- The mobile browser tests now include recurring-program attendance and the finance and newcomers pages in the optional authenticated sweep.

## Verification

| Check | Result |
|---|---:|
| Full Church_server suite | 337 passed, 1 skipped |
| Rendered dashboard component test | State, Region, Group and Location at 360×740, 390×844 and 768×1024; passed |
| Phone document width | 360px and 390px fixtures stayed within viewport; no horizontal page overflow |
| Clipped content and small text | No clipped analytics text or text under 10px in tested components |
| SVG labels | At least 11px effective size at all three tested widths |
| Child cards and action targets | Stacked below 640px; links, info controls and reminder buttons are at least 40px high |
| Attention actions | Rendered below the title and metadata without overlap |
| Authenticated mobile sweep | Skipped: `DCLM_MOBILE_TEST_BASE_URL` and the four persona storage states were not supplied |

The browser fixture uses the dashboard's actual `_children_table`, `_attention_panel`, `_line_chart`, and metric-card renderers with synthetic values. It verifies the component layout and CSS, but does not claim that a signed-in browser completed a live API load for all routes.

## Screenshots

All files are 390×844. The before image is a crop of the phone screenshot supplied for this review, normalized to the requested viewport. After images use the real component renderers and synthetic development values.

- Before, State dashboard: [before-state-390x844.png](output/playwright/mobile-polish/before-state-390x844.png)
- After, State dashboard top: [after-state-390x844.png](output/playwright/mobile-polish/after-state-390x844.png)
- After, Region dashboard top: [after-region-390x844.png](output/playwright/mobile-polish/after-region-390x844.png)
- After, child cards: [after-state-child-cards-390x844.png](output/playwright/mobile-polish/after-state-child-cards-390x844.png)
- After, Needs attention and trend: [after-state-attention-390x844.png](output/playwright/mobile-polish/after-state-attention-390x844.png)
- After, trend and legend: [after-state-trend-390x844.png](output/playwright/mobile-polish/after-state-trend-390x844.png)

## Files in this checkpoint

- `app/frontend/dclm_admin/assets/css/analytics-dashboard.css`
- `app/frontend/dclm_admin/components/shell.py`
- `app/frontend/dclm_admin/routes/analytics_dashboard.py`
- `tests/test_analytics_dashboard_chart.py`
- `tests/test_analytics_mobile_layout.py`
- `tests/test_analytics_mobile_playwright.py`
- `output/playwright/mobile-polish/*.png`

## Remaining evidence

The authenticated mobile sweep still needs `DCLM_MOBILE_TEST_BASE_URL` plus browser storage states for State, Region, Group and Location. Once configured, it checks the analytics pages and the existing Inbox, People, Church data, Finance, Fellowship, Organization, Reports and Programs pages at 360px, 390px and 768px. The screenshots in this report are component-level synthetic renders, not screenshots from the deployed staging site.
