# Pastor Report and Export Slice Report

**Status:** Implemented locally and verified. This is a separate checkpoint from the earlier admin leftovers work. No remote database writes, deployment, or push were performed.

## What was added

- A scoped **Pastor’s report** page at `/dashboard/pastor-report`, linked from the dashboard, recurring attendance page, Retreat/Crusade pages, and Reports hub. It supports the last 4 Sundays, 8 weeks, month-to-date, quarter-to-date, and a selected Retreat or Crusade campaign.
- A branded A4 report with DCLM logo, scope name, period, included-report status, generated time and author, section headings, a trend chart, definitions, and the `Powered by: Kwara State ICT Unit` footer. Browser print supports save-to-PDF. A server-side PDF download is also available through ReportLab.
- Deterministic findings with named thresholds in `app/services/analytics/pastor_report_config.py`. Findings include pooled attendance movement, coverage, consecutive missing weeks, child-scope comparisons, offerings, pending decisions, and documented-population coverage. Each finding has a short calculation note.
- Report sections for coverage; weekly attendance and six categories; child-scope comparison; approved and pending offerings; newcomer and convert **record counts**; roster-based workers’ meeting; House Caring Fellowship; pending decisions; event sessions; and definitions/data-quality notes.
- XLSX export with Summary, Weekly by unit, Location coverage, Counts by category, Offerings summary, Retreat Crusade, Definitions, and House Caring Fellowship sheets. CSV export is a ZIP containing those sheet-equivalent CSV files. Exports respect the actor’s scope, period, and pending filter. Location-level coverage contains no person-level contact details.
- Export and print audit entries with actor, effective scope and date range. An aggregate offering endpoint returns only date/program/fund/status totals and record counts.
- Extended the analytics series request to 26 weeks and made detailed per-location history opt-in so ordinary dashboard requests do not carry export-only detail.

## Data interpretation

- Approved records are counted by default. Pending data is separate and is included only when the report filter requests it.
- Missing attendance remains “No report”; a stored zero remains a counted zero.
- Newcomer and convert metrics are record counts, not unique people. When no records exist, the report says **“No newcomer or convert records are available”** and explicitly states that this does not mean a reported zero.
- Approved offerings are displayed only when approved records exist. Pending amounts remain separate; an empty approved result is not presented as a reported zero.
- Attendance changes use comparable reporting units and pooled totals. The report does not sum attendance across event days.

## Verification

- Pastor report tests: **7 passed**.
- Full Church_server suite: **349 passed, 1 skipped**. Pytest emitted the existing `pytest-asyncio` default-loop-scope deprecation warning.
- Generated a synthetic two-page server PDF and rendered both pages for visual inspection. The line chart and coverage bars are visible, the report spans two pages, the table rows stay intact, the Naira display uses `NGN` in the server PDF, and the footer includes page numbers and the requested attribution.
- Screenshots of the generated PDF pages:
  - [Page 1](output/playwright/pastor-report-final-1.png)
  - [Page 2](output/playwright/pastor-report-final-2.png)

The PDF screenshots use a synthetic fixture. They demonstrate the rendered report layout, not live church data. A fresh authenticated browser print-preview capture was not available in this pass; phone preview behavior is therefore not claimed as browser-verified.

## Files in this checkpoint

- `app/frontend/dclm_admin/routes/pastor_report.py`
- `app/frontend/dclm_admin/assets/css/pastor-report.css`
- `app/services/analytics/pastor_report_config.py`
- `app/api/v1/routes/reports.py`
- `app/api/v1/routes/dashboard.py`
- `app/api/v1/routes/analytics.py`
- `app/services/analytics/sunday_worship.py`
- `app/frontend/dclm_admin/app_factory.py`
- `app/frontend/dclm_admin/backend/client.py`
- `app/frontend/dclm_admin/communication/api_client.py`
- `app/frontend/dclm_admin/communication/dashboard_service.py`
- `app/frontend/dclm_admin/routes/analytics_dashboard.py`
- `app/frontend/dclm_admin/routes/population_analytics.py`
- `app/frontend/dclm_admin/routes/programs.py`
- `app/frontend/dclm_admin/routes/reports.py`
- `tests/test_pastor_report.py`
- `output/playwright/pastor-report-final-1.png`
- `output/playwright/pastor-report-final-2.png`

## Limits carried forward

- XLSX and zipped CSV exports are currently assembled in application memory; large-export streaming has not been implemented or measured.
- The report’s live browser print preview and phone rendering need an authenticated browser check.
- The five cold-process timing and live SQL trace requirements are part of Slice E and are not claimed complete here.
- No deployment or push was performed. The user requested to run FastAPI Cloud login/deployment from their terminal.
