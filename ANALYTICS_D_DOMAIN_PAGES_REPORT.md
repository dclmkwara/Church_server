# Step D: Domain Pages and Field Utility Submission Handoff

**Status:** Step D implementation is committed locally. The next validation and navigation-consolidation gates have not started.

## Admin analytics and data pages

- Added a shared recurring population attendance page for Sunday Worship, House Caring Fellowship, Monday Bible Study and Thursday Revival Hour. It has a program selector, 4/8-week window, pending switch where applicable, named breadcrumbs, scope drill-down, weekly trend and location-level records. Location views retain eight weekly rows and distinguish `Reported 0` from `Not reported`.
- Added a parameterized read-only API endpoint for those four programs. House Caring Fellowship uses active fellowships as its expected units and reads the saved fellowship attendance categories. Its rows do not have an approval status, so the page says all saved rows are included and disables the pending switch instead of inventing an approval state.
- Finance rows and summary cards use the selected date range and fund/location/method filters. Pending and corrected entries remain separate from approved totals; rejected entries are excluded from totals. Pending entries appear in the table only when the pending switch is selected.
- Newcomer and convert totals remain visible at State and Region scope, while person-level names and contact details are withheld there. Person-level records remain available at Group and Location scope.
- Workers Meeting and Leaders Meeting remain separate. Their existing dashboard paths use the B4 roster-based meeting metrics; the Leaders Meeting list retains the “records, not unique attendees” disclosure.

The domain-page implementation commit is `d5f6992` (`Add recurring program and finance analytics pages`). No migration or menu change was added.

## Field Utility fixes included in this handoff

- Submitted-record panels now filter out records that are locked, have no time remaining, or have no edits remaining. The queue page refreshes those panels at most one hour later while it remains open.
- Recent sync history and local attendance-confirmation badges are pruned after 25 hours (the 24-hour edit period plus one hour). Unsubmitted queue records are not pruned by this cleanup.
- Worker attendance now honors the account’s submission preference. Instant mode posts directly; it queues when offline or when an online transport failure makes delivery unavailable. Queue-first mode remains an explicit setting. Attendance no longer forces immediate submission around that setting.
- Online validation and server rejections are shown to the user and are not mislabeled as offline queue items. Explicitly queued records remain in the queue if a manual sync is rejected.
- The Utility worker-attendance schema now carries `program_level`, `assignment_id` and `note`; the proxy validates an assignment ID before forwarding. Tests cover the complete forwarded metadata and malformed assignment IDs.
- Settings copy now explains that instant mode queues only when the connection is unavailable and that validation errors stay visible for correction.

The Utility commit is `f87bc09` (`Fix utility submission and edit window behavior`). Neither commit has been pushed or deployed.

## Verification and limits

- Church_server full suite: **334 passed, 1 skipped**, with one third-party `asyncio.iscoroutinefunction` deprecation warning.
- Field Utility full suite: **40 passed**.
- Utility JavaScript syntax checks passed for `app.js`, `db.js` and `sync.js`.
- No live attendance submission was made. At verification time, port 8000 was the only app port listening; it served the Church_server API and its configured database host was the remote Supabase development pooler. The Field Utility server was not running. I did not write synthetic records to the remote database, so an authenticated Utility-to-database end-to-end confirmation remains outstanding.
- No browser screenshots were captured for the new admin page or Utility queue changes in this pass. Automated route/service tests establish the source behavior, but do not establish the deployed phone layout or a live submission.

## Repository state and next gate

The two commits stage only their listed code and tests. Existing unrelated working-tree files and generated artifacts remain untouched. The B3/B4/B5 and previous completion reports remain separate.

Step D is ready for review. The next agreed work is the validation gate; navigation consolidation remains deferred until after review and its separate plan.
