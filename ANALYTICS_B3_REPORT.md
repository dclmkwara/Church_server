# Analytics B3 Implementation Report

**Date:** 7 November 2026  
**Scope:** B3 occurrence inventory and read-only Retreat, Crusade, and Tuesday Leaders Meeting views. No B4/B5 work, menu changes, schema migration, or remote database writes.

## What was implemented

- Added `GET /api/v1/analytics/programs/occurrences`, scoped through the signed-in user's allowed hierarchy. It accepts domain, program type, program level, event/campaign, date range, and pending inclusion filters.
- Added a shared occurrence service that keeps each dated event and program type separate. Approved totals are counted by default; pending totals are opt-in; rejected/returned records are not included in counted totals. A reported zero remains distinguishable from no report.
- Added Retreat and Global Crusade report views beneath the existing Programs page. A selected campaign displays its recorded program types by date/day. Retreat attendance is not summed across days. Crusade attendance and converts are shown by Alpha and satellite source, with a labelled total; Alpha is hidden below State scope. Pending rows follow the page switch.
- Added a separate Tuesday Leaders Meeting received-record table. Saturday Workers Meeting remains a separate page and the two filters are not combined.
- Kept the existing sidebar and did not add navigation entries. The Programs page contains links to the two new report views.
- A Crusade convert-only submission now shows as reported in the converts view even when there is no matching population-count row.

## Storage inventory and database evidence

The pre-build inventory is in [ANALYTICS_B3_INVENTORY.md](ANALYTICS_B3_INVENTORY.md). Existing `ProgramCampaign`, `ProgramEvent`, and `ProgramType` rows can express a dated sub-program within a multi-day Retreat or Crusade. The day number is derived from the campaign start date and event date. The existing schema does not define a planned-session catalogue.

`EventAssignment` is assigned to workers and has a source role; it does not identify a distinct expected reporting unit (such as an expected Region or satellite Location). The pages therefore say planned sessions and coverage expectations are not defined when that information is absent. They do not manufacture missing sessions or treat unknown coverage as complete.

Read-only inspection of the disposable local restored clone `dclm_perf` found two campaign rows, three event rows (all weekly program types), no event assignments, and ten count rows with no event link. There were no Retreat or Crusade event submissions to display. This is why the browser captures show empty states rather than attendance figures.

The existing `ProgramService.campaign_activity()` still sums count rows across event dates. B3 views do not call that aggregate for attendance. The older campaign report was not changed because changing its semantics needs a separate compatibility review.

## Verification

- Full test suite: **259 passed**, one third-party `fastcore` deprecation warning.
- `git diff --check` on B3 implementation files: passed.
- Browser checked State, Region, Group, and Location personas for the Retreat, Crusade, and Tuesday Leaders Meeting routes. The routes rendered with HTTP 200 after authentication. State and Location views were visually inspected; empty event data is presented as “No sessions reported” / “No campaign is available in this scope yet,” not zero attendance.
- Existing captures: [State Retreat](output/playwright/b3/state-retreat.png), [State Crusade](output/playwright/b3/state-crusade.png), [State Leaders Meeting](output/playwright/b3/state-leaders-tuesday.png), [Location Retreat](output/playwright/b3/location-retreat.png), [Location Crusade](output/playwright/b3/location-crusade.png), [Location Leaders Meeting](output/playwright/b3/location-leaders-tuesday.png). Region and Group captures are alongside them in `output/playwright/b3/`.
- No schema migration was required or run. No write was made to Supabase or any remote database.
- Browser server: port **8014**. Database: disposable local restored clone `dclm_perf`, PostgreSQL port **55432**.

## Known gaps before calling B3 fully complete

1. **Hierarchical drill-down is not complete.** Clicking a matrix cell opens the event's Location-level report rows. It does not yet step through Region → Group → Location children, and Retreat is not yet presented as a Region aggregate with drill-down.
2. **Coverage and comparisons are not implemented.** The view does not calculate `n of m` Region or satellite Location coverage, Alpha expected reporters, or deltas against the previous same-kind campaign. The current worker assignment model does not supply a reliable reporting-unit denominator, so these need an agreed mapping before implementation.
3. **Weekly-program configs are not moved to this endpoint.** The existing Sunday Worship dashboard remains specialized; Monday Bible Study and Thursday Revival are not yet configurations of the occurrence endpoint.
4. **Leaders Meeting values are stored attendance rows.** The page lists meeting date, held level, home location, and present entries, but it does not deduplicate roster snapshots into a unique-worker attendance metric. Coverage remains not defined.
5. **Load-time impact was not measured for this slice.** The endpoint uses one event query plus grouped count/detail/record reads and a campaign relationship read when events are present. No dedicated B3 browser timing series or per-request SQL timing was captured, so no latency claim is made.

## Files in the B3 checkpoint

- `app/api/v1/routes/analytics.py`
- `app/services/analytics/program_occurrences.py`
- `app/main.py`
- `app/frontend/dclm_admin/backend/client.py`
- `app/frontend/dclm_admin/communication/api_client.py`
- `app/frontend/dclm_admin/communication/church_data_service.py`
- `app/frontend/dclm_admin/communication/program_service.py`
- `app/frontend/dclm_admin/routes/programs.py`
- `app/frontend/dclm_admin/routes/church_data.py`
- `tests/test_program_occurrences_api.py`
- `ANALYTICS_B3_INVENTORY.md`
- `ANALYTICS_B3_REPORT.md`
- `output/playwright/b3/` browser captures

**Next gate:** report these remaining B3 gaps for review before beginning B4. No B4/B5 or menu work has started.
