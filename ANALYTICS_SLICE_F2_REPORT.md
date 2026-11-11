# Analytics Slice F2 Report

**Part 1 status:** Complete against the disposable local clone. Parts 2–4 were not started.  
**Date:** 11 November 2026  
**Environment:** local PostgreSQL clone `dclm_slice_f` on port `55434`; Field Utility on port `8013`; Church Admin/API on port `8015`. The server process was started with explicit loopback database URLs. No remote database was read or written, and nothing was pushed.

## 1. Utility single and split count investigation

### Reproduction and root cause

I reproduced the behavior with the real Utility counter screen and the local API/database.

| Attempt | Evidence | Finding |
|---|---|---|
| Single count | The Utility showed no reliable success confirmation in the failed run, but the matching count row and all six demographic values were present in PostgreSQL. A fresh browser submission then displayed the success message. | Utility client defect. The server had accepted and persisted the report; the Utility sync routine then threw a JavaScript `ReferenceError` because `failed` was used without being initialized. The catch path treated that post-response programming error like a connectivity failure and saved the already-accepted record to the device queue. |
| Second split part / repeated label | The first labeled part submitted and the running group total appeared. For a repeated label, the batch endpoint returned HTTP 200 with a per-record `status: "error"` and the message that the label had already been reported. The old client threw while trying to count that rejection and misclassified it as an offline failure, leaving it in the local queue. After the fix, the Utility displays the rejection and does not queue it. | Utility client defect, not intended offline behavior and not a server acceptance. A separately labeled second part succeeds; the live API run verified both parts and their total. |

The triggering bug is in the response-handling portion of `submitManyOrQueue`: initialize the per-batch failed counter and handle a server-returned rejected item as a rejection. The queue fallback remains for actual offline/transport failures. A regression test, `test_server_rejected_sync_item_is_not_misclassified_as_offline_queue_item`, verifies the distinction.

The actual Utility browser flow also exercised an offline submit. With the browser taken offline, the screen said it was saved on the device. After restoring connectivity and replaying the queue twice, the queue emptied and the database held one row for that client ID. This was separate from the API script's idempotency replay check.

### Other submission defects found and fixed

- **Worker attendance API:** the Utility's `Weekly Programs` domain was rejected by an allow-list that only recognized `weekly`; location rosters were also being revalidated through historical `Worker.path` values that did not match the location roster shown by the Utility. The request failed before a valid attendance submission. The API now accepts the church's domain label and validates/captures a local roster using `Worker.location_id`; combined event rosters still use hierarchy scope. A missing SQL `text` import in the duplicate-attendance check was also fixed. Regression tests cover accepted domain labels and location versus combined-event roster selection.
- **Worker attendance analytics:** the real Admin meeting page initially showed the marked February meeting as 1 present of 7 expected (14.3%), though the submitted roster snapshot contained 14 expected IDs. A fresh server process reproduced the mismatch. The analytics then rechecked the snapshot against today's hierarchy and discarded IDs whose worker paths had changed. It now uses the IDs stored in the scoped meeting roster snapshot, preserving the denominator for that meeting. Regression tests cover stale worker paths. After restarting the server, the page showed that February meeting as 1 of 14 (7.1%). Its overall summary also includes other meetings in the group and is therefore a separate aggregate.
- **Finance Admin page:** an offering's reporting date was being taken from its creation timestamp rather than its service date. The normalizer now uses the submitted service date in `Africa/Lagos`; tests cover a later-created offering and Lagos date conversion. The Admin finance list showed the synthetic offering on the service date.
- **Fellowship Admin detail:** the page raised a 500 while resolving location details because an async result was evaluated and cached as if it were synchronous. The service now awaits the location lookup directly. A regression test covers the adapter, and the live local detail page loaded with the synthetic fellowship attendance.
- **Offering pagination adapter:** the Finance page passed `skip` but the backend client method did not accept it. The adapter and its pagination test were corrected.

### Repeatable local end-to-end run

`scripts/e2e_b5_split_counts.py` now defaults to the local location belonging to its seeded test accounts. Its loopback-only guard prevents sending the synthetic workflow to a remote API. Run it with the local API and database, for example:

```powershell
$env:SYNC_DATABASE_URL = 'postgresql+psycopg2://postgres@127.0.0.1:55434/dclm_slice_f'
$env:B5_TEST_PASSWORD = '<local test account password>'
.\.venv\Scripts\python.exe scripts/e2e_b5_split_counts.py `
  --base-url http://127.0.0.1:8015/api/v1 `
  --sync-database-url $env:SYNC_DATABASE_URL
```

The successful run marker was `F2_TEST:f2-e2e:8877cf7d`. The script used synthetic dates and verified:

- A single count with six categories `(2, 3, 4, 5, 6, 7)` and total `27`.
- Two labeled parts, `Adult A` and `Youth`, with each category summed from the two saved rows and total `150`. The Group Pastor's review payload showed both parts and category totals; one group approval made the dashboard report `150`.
- Repeated-label rejection, single-count conflict and mixed-mode rejection.
- Offline-style replay of the same client ID twice; both retries were reported as duplicates and only one row existed.
- In-window edit, repeated edit ID idempotency, concurrent edit conflict, the three-edit limit, one extra edit after return, refusal after 24 hours, and lock after approval.
- Offering save and preflight before/after: before save `already_recorded=false`; after one save `already_recorded=true, record_count=1`.
- Worker attendance and fellowship attendance submissions; the Admin data paths returned the submitted records.
- Auto-close notification to the Location Pastor.

The real Utility UI was separately exercised for the demographic counter, a labeled split count, repeated-label message and offline queue/replay. The script's HTTP/API checks are not being represented as a fully automated browser test of the entire Utility flow.

### Admin view and offering duplicate behavior

The local Admin app was opened in a real browser under the Group Pastor persona. I checked Program Counts/Count Review, the Saturday Workers Meeting page, Finance, and Fellowship detail. The split review showed the parts and categories; the count view showed approved counts; Finance showed the offering at its service date; Fellowship showed the test attendance; and the worker page reflected the corrected 14-person roster snapshot. Test rows were then removed.

Two ushers can still create two offering records for the same service if both pass the preflight before either saves, or if a user explicitly confirms the second save. `/offerings/preflight` is a read-only warning check and there is no unique database constraint for location + service date + fund + program occurrence. The Utility now presents the requested confirmation, **“An offering was already recorded for this service. Save another one?”** before a second save. This warns the usher; it is not a race-proof server-side duplicate prohibition.

## Test results and cleanup

- Church Server full suite: **358 passed, 1 skipped**.
- Field Utility full suite: **41 passed** (one third-party deprecation warning).
- `git diff --check` passed for the changed Church Server files and Utility files.
- The repeatable API scenario completed successfully on the local server. It initially refused to run because its former default location ID did not exist in this clone; the default was corrected to the seeded test account location, then the scenario passed.
- `scripts/remove_slice_f2_demo.py --apply` removed the marked synthetic rows. A follow-up SQL check returned **0** marked rows in counts, offerings, worker attendance submissions/rows, records, fellowship attendance/offerings, and fellowships.
- The removal command only accepts loopback and database name `dclm_slice_f`. It can be rerun with `SYNC_DATABASE_URL` pointing to that local database.

## Changes made

Church Server changes cover sync validation, finance and fellowship adapters, worker meeting aggregates, the repeatable E2E and removal scripts, and regression tests. Field Utility changes cover the sync response-handling defect and its regression test. The working trees contain other unrelated existing modifications; no changes were committed or staged.

## Still open

Part 2 (independent SQL reconciliation against rendered pages/exports at State, Location, Group and Region), Part 3 (A4 print preview and phone save-to-PDF check), and Part 4 (three cold timings for dashboard and Pastor Report plus sign-in timing) have not been started. This report stops at Part 1 as requested.
