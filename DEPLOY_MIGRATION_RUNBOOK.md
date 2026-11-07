# Alembic Baseline Audit and Deployment Runbook

**Audit date:** 7 November 2026  
**Scope:** Read-only audit of the Supabase development catalog, local Alembic proof for `e2b4c6d8f013`, and a proposed operator runbook. No Alembic migration, stamp, schema change, or other write was run against Supabase.

## Current finding

The saved read-only catalog snapshot reports the remote Alembic ledger at `c2e5a8f14b31`, with one row. `d4a9c1e7f235` (recipient-specific count reminders) and `e2b4c6d8f013` (versioned expected population) are not recorded and their tables are absent. This is different from the earlier report that described the ledger as empty; the newer snapshot is the current evidence for this audit.

The comparison is against SQLAlchemy metadata at commit `20d8898b713aea27907ff8a14f16e7c0a76724e9`, immediately before B2b. It reports real schema drift as well as reflection artifacts. Do not treat `alembic check` as a safe deploy gate on this baseline: it may propose unrelated changes. The catalog and model comparison are in `output/remote_schema_catalog.json` and `output/remote_public_model_diffs.json` (these are audit artifacts, not migration inputs).

## A. Migration revisions in order

The list is chronological from base to head. ?Ledger evidence? means the revision is at or before the remote ledger revision. It is evidence Alembic recorded that revision; it does not guarantee no later schema drift. The object column summarizes upgrade DDL found in each revision file; direct final-schema drift is detailed after the table.

| # | Revision | Upgrade purpose | Main schema/data operations | Remote status / evidence |
|---:|---|---|---|---|
| 1 | `4f7eda7933f7` | Placeholder base revision to match existing database state. | custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 2 | `f14fc281567e` | add approvals, app_versions, and offering fund_type | column locations.latitude; column locations.longitude; column offerings.fund_type; plus 22 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 3 | `b1a2c3d4e5f6` | add worker approval fields | column workers.approved_at; column workers.approved_by; column workers.rejection_reason; plus 2 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 4 | `111a86ab3979` | Add WorkerRemovalRequest model | index op.f('ix_worker_removal_requests_created_at') on worker_removal_requests; index op.f('ix_worker_removal_requests_path') on worker_removal_requests; index op.f('ix_worker_removal_requests_status') on worker_removal_requests; plus 2 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 5 | `fead1055eafd` | add_location_profile_church_member_worker_transfer_absence_notice | column workers.approval_status; column workers.approved_at; column workers.approved_by; plus 31 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 6 | `9f0d0e1a2b3c` | Fix ltree columns and reporting materialized views | custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 7 | `b8c1d2e3f4a5` | add_notification_read_states | index op.f('ix_notification_read_states_created_at') on notification_read_states; index op.f('ix_notification_read_states_notification_key') on notification_read_states; index op.f('ix_notification_read_states_read_at') on notification_read_states; plus 2 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 8 | `c9d2e3f4a5b6` | add_public_intake_and_visibility_flags | column media_galleries.is_public; column media_galleries.published_at; column program_events.is_public; plus 15 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 9 | `d1e2f3a4b5c6` | add program event operational metadata | column program_events.alpha_location_id; column program_events.campaign_code; column program_events.collection_window_end; plus 9 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 10 | `e4f5a6b7c8d9` | add crusade submission metadata and assignments | column counts.assignment_id; column counts.campaign_code; column counts.source_role; plus 22 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 11 | `f7a8b9c0d1e2` | add program campaigns | column program_events.campaign_id; index op.f('ix_program_campaigns_alpha_location_id') on program_campaigns; index op.f('ix_program_campaigns_campaign_code') on program_campaigns; plus 10 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 12 | `a1b2c3d4e5f6` | add official appointments | index op.f('ix_official_appointments_appointed_by_id') on official_appointments; index op.f('ix_official_appointments_appointed_role') on official_appointments; index op.f('ix_official_appointments_appointment_date') on official_appointments; plus 9 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 13 | `b2c3d4e5f6a7` | add program event audience segments | column program_events.audience_segment; index op.f('ix_program_events_audience_segment') on program_events | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 14 | `c3d4e5f6a7b8` | align program campaign and assignment audit columns | column table_name.last_modify; column table_name.operation; custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 15 | `d4e5f6a7b8c9` | add refresh_tokens table for secure token rotation | index ix_refresh_tokens_expires_at on refresh_tokens; index ix_refresh_tokens_jti_revoked on refresh_tokens; index ix_refresh_tokens_user_id_revoked on refresh_tokens; plus 1 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 16 | `e5f6a7b8c9d0` | add missing performance indexes | custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 17 | `f6a7b8c9d0e1` | move hierarchy tables to uuid primary keys and parent-scoped local codes | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 18 | `f7b8c9d0e1f2` | add audit columns to uuid hierarchy tables | column table_name.created_by; column table_name.version; index index_name on table_name | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 19 | `a07be837513a` | enforce client submission idempotency | custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 20 | `b18f2c6d9a40` | enforce attendance and record integrity rules | check_constraint name; custom SQL / RBAC / RLS / view operations; index uq_worker_attendance_active_event_worker on worker_attendance | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 21 | `c29d3a61e8ab` | add financial review and correction audit trail | check_constraint ck_offerings_review_status; column offerings.review_note; column offerings.reviewed_at; plus 8 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 22 | `d30e17a4bc52` | correct report materialization grain and source semantics | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 23 | `e41a8b9c7d6f` | add fail-closed row level security policies | custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 24 | `fa12c0e7d8b9` | Preserve event grain in population count summaries. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 25 | `b73c1d9e5f20` | Use ltree for the scoped daily count summary path. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 26 | `c84d2f7a6b91` | Expose ltree paths on all scoped report materialized views. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 27 | `d95e3f1a2b4c` | Grant scoped reporting reads to pastor roles at levels 3-5. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 28 | `e01c4a8b6d20` | Keep report refresh restricted to pastor/overseer roles. | custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 29 | `f12a9c6e4d31` | Expose a narrowly scoped analytics refresh to the runtime role. | custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 30 | `3f8a2c7d91e4` | Allow routine field records without scheduled event and persist metadata. | check_constraint ck_fellowship_members_group; column fellowship_members.fellowship_group; column records.date; plus 13 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 31 | `9d4c2f1a6b80` | Persist fellowship category and permit field-role batch uploads. | check_constraint ck_fellowships_group; column fellowships.fellowship_group; custom SQL / RBAC / RLS / view operations; plus 1 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 32 | `aa71b5c49d20` | Store usher attendance captures atomically while retaining worker rows. | column worker_attendance.submission_id; custom SQL / RBAC / RLS / view operations; foreign_key fk_worker_attendance_submission_id; plus 2 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 33 | `0d8f6a2b4c91` | Align RBAC role scores with the canonical church hierarchy. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 34 | `1c7d4e9a2f60` | Normalize shared-backend higher admin home paths. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 35 | `6a9c2e1f4b70` | Reserve direct worker removal for group leadership and above. | custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 36 | `92b7e4c1d630` | Persist the reporting level selected for program submissions. | column table.program_level; index f'ix_{table}_program_level' on table | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 37 | `4e68a01bd527` | Seed the five mother domains and canonical lookup IDs on submissions. | column table.program_domain_id; column table.program_type_id; custom SQL / RBAC / RLS / view operations; plus 4 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 38 | `a4c29e81b705` | Persist the hierarchy scope of each program submission. | column table.program_scope_path; custom SQL / RBAC / RLS / view operations; index f'ix_{table}_program_scope_path' on table | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 39 | `b1342f6a7c91` | Add staged worker transfer reviews and removal restoration snapshots. | column transfer_requests.rejection_reason; column worker_removal_requests.user_was_active_before_request; column worker_removal_requests.worker_status_before_request; plus 1 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 40 | `c2138e4a6f90` | Route legacy origin-approved transfers through the receiving leadership stages. | custom SQL / RBAC / RLS / view operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 41 | `d9e3a70c18f4` | Add stable client IDs for offline worker candidate intake. | column workers.client_id; index uq_workers_client_id on workers | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 42 | `e1f4c0b72a91` | Persist the submitting user for worker registrations. | column workers.created_by; foreign_key fk_workers_created_by_users; index ix_workers_created_by on workers | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 43 | `f0a19b3c7d42` | Persist event assignments on aggregate and individual worker attendance. | column table.assignment_id; foreign_key f'fk_{table}_assignment_id'; index f'ix_{table}_assignment_id' on table | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 44 | `f1b2c3d4e5a6` | Add structured weekly information and scoped broadcast messages. | column announcements.sa.Column(name, sa.String(length=length), nullable=True); column announcements.sa.Column(name, sa.Text(), nullable=True); custom SQL / RBAC / RLS / view operations; plus 7 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 45 | `f2c4a8d1e730` | Require same-level pastor approval for scheduled events. | check_constraint ck_program_events_approval_status; column program_events.approval_note; column program_events.approval_status; plus 6 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 46 | `f3e6b8c0d2a4` | Allow level pastors to schedule events with immediate same-level approval. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 47 | `f4c1d8a6b203` | Grant group, region, and state administrators and pastors event assignment governance. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 48 | `f5a7c9e1d3b2` | Add GiST indexes for hierarchy path filters. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 49 | `f6b8d2a4c910` | Restore Region and State grants for fellowship hierarchy management. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 50 | `f7c2d4a6b810` | Restore State fellowship deletion permission from canonical RBAC policy. | No table/column/index DDL parsed; inspect migration for data/RBAC/view changes | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 51 | `a71c3f9d2b40` | Add lifecycle dates and active status for locations. | check_constraint ck_locations_lifecycle_dates; column locations.closed_on; column locations.is_active; plus 2 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 52 | `c2e5a8f14b31` | Add count review, correction history, and scoped review permission. | column counts.approved_at; column counts.approved_by_id; column counts.auto_accepted; plus 12 more operations | Recorded by ledger `c2e5a8f14b31`; final public-catalog comparison below |
| 53 | `d4a9c1e7f235` | Store count reminders as recipient-specific, auditable records. | index ix_count_reminder_location_day_sent on count_reminder_recipients; index ix_count_reminder_recipient_sent on count_reminder_recipients; index ix_count_reminder_recipients_reminder_id on count_reminder_recipients; plus 1 more operations | Not recorded in remote ledger; expected new migration |
| 54 | `e2b4c6d8f013` | Add versioned location expected Sunday attendance estimates. | custom SQL / RBAC / RLS / view operations; index ix_location_expected_population_location_effective on location_expected_population; index ix_location_expected_population_path_gist on location_expected_population; plus 1 more operations | Not recorded in remote ledger; expected new migration |

The chain contains 54 revisions and one head. Revisions through `c2e5a8f14b31` are ancestors of the remote ledger revision. In the final remote catalog, tables/columns/indexes from those revisions were checked as a whole against the pre-B2b model; details follow. Data-only RBAC and RLS operations cannot be proven by a schema-only catalog query.

### Focus revisions

| Revision | Expected objects | Remote finding from read-only catalog |
|---|---|---|
| `a71c3f9d2b40` | `locations.is_active`, `opened_on`, `closed_on`; index `ix_locations_is_active`; check `ck_locations_lifecycle_dates` | All three columns, the index, and the check constraint are present. The ledger is later than this revision. |
| `c2e5a8f14b31` | Seven review columns on `counts`; three review foreign keys; indexes `ix_counts_approved_by_id`, `ix_counts_auto_accepted`, `ix_counts_supersedes_id`, `ix_counts_rejected_by_id`; RBAC grant for `counts:review` | All seven columns, all three FKs, and all four indexes are present. Ledger is exactly at this revision. RBAC grant rows were not part of the saved schema catalog, so grants are not confirmed by this comparison. |
| `d4a9c1e7f235` | `count_reminder_recipients` and three indexes | Table and indexes absent. Revision not recorded. |
| `e2b4c6d8f013` | `location_expected_population`, effective/location index and path GiST index, RLS policies | Table, columns, and indexes absent. Revision not recorded. |

## B. Remote catalog vs pre-B2b model metadata

Remote snapshot totals: **52 public tables including `alembic_version`, 792 columns, 493 indexes, 199 constraints**. Pre-B2b model metadata contains 52 application tables. Results from the public-schema comparison:

| Difference | Result | Assessment |
|---|---|---|
| Application tables | Missing `count_reminder_recipients`; no extra application table found. `alembic_version` is infrastructure, not an application model. | Expected for remote ledger at `c2`; reminder migration `d4` has not run. |
| Columns | No add/drop column operations in the model comparison. | Column names/coverage match, excluding type/default/nullability differences below. |
| Indexes | 47 model `add_index` candidates: 46 names are absent in the remote catalog, one (`ix_nations_nation_code`) exists. 49 model `remove_index` candidates are all present in the remote catalog. | 46 absent indexes are schema differences. The 49 apparent removals are reflection mismatches: the catalog has those expression GiST and unique indexes. Do not drop them. |
| Constraints | Seven expected FKs reported: six fellowship-to-fellowship FKs are absent; the `workers.created_by` FK exists under a named constraint with `ON DELETE SET NULL`. The `nations.nation_code` unique constraint exists, despite a name/reflection mismatch. | Six missing fellowship FKs are real differences to review; worker and nation items are naming/definition mismatches. |
| Column types | Six `fellowship_id` columns are `varchar` remotely but `UUID` in the model. | Real type drift; do not auto-convert until data and client compatibility are checked. |
| Nullability/defaults | `offerings.status` is nullable in catalog although model expects non-null; a check constraint currently rejects null. Eleven server-default differences were reported on identifiers/status/JSON/defaulted flags. | Verify intended defaults and nullability. These are not safe to reconcile automatically from autogenerate. |

### Absent named indexes reported by metadata comparison

- `ix_count_reminder_location_day_sent` on `count_reminder_recipients` (location_id, occurrence_date, sent_at)
- `ix_count_reminder_recipient_sent` on `count_reminder_recipients` (recipient_user_id, sent_at)
- `ix_count_reminder_recipients_reminder_id` on `count_reminder_recipients` (reminder_id)
- `ix_announcement_items_announcement_id` on `announcement_items` (announcement_id)
- `ix_broadcast_messages_created_at` on `broadcast_messages` (created_at)
- `ix_church_members_entered_by_id` on `church_members` (entered_by_id)
- `ix_counts_entered_by_id` on `counts` (entered_by_id)
- `ix_dclm_groups_created_at` on `dclm_groups` (created_at)
- `ix_event_assignments_approved_by_id` on `event_assignments` (approved_by_id)
- `ix_event_assignments_assigned_by_id` on `event_assignments` (assigned_by_id)
- `ix_fellowship_attendance_entered_by_id` on `fellowship_attendance` (entered_by_id)
- `ix_fellowship_attendance_summaries_entered_by_id` on `fellowship_attendance_summaries` (entered_by_id)
- `ix_fellowship_offerings_entered_by_id` on `fellowship_offerings` (entered_by_id)
- `ix_fellowship_prayer_request_entered_by_id` on `fellowship_prayer_request` (entered_by_id)
- `ix_fellowship_testimony_entered_by_id` on `fellowship_testimony` (entered_by_id)
- `ix_fellowships_created_at` on `fellowships` (created_at)
- `ix_idempotency_keys_created_at` on `idempotency_keys` (created_at)
- `ix_locations_created_at` on `locations` (created_at)
- `ix_media_galleries_created_by_id` on `media_galleries` (created_by_id)
- `ix_media_items_uploaded_by_id` on `media_items` (uploaded_by_id)
- `ix_nations_created_at` on `nations` (created_at)
- `ix_offering_audits_created_at` on `offering_audits` (created_at)
- `ix_offerings_entered_by_id` on `offerings` (entered_by_id)
- `ix_program_campaigns_created_by_id` on `program_campaigns` (created_by_id)
- `ix_program_events_approved_by_id` on `program_events` (approved_by_id)
- `ix_program_events_created_by_id` on `program_events` (created_by_id)
- `ix_public_contact_submissions_reviewed_by_id` on `public_contact_submissions` (reviewed_by_id)
- `ix_public_prayer_submissions_reviewed_by_id` on `public_prayer_submissions` (reviewed_by_id)
- `ix_records_entered_by_id` on `records` (entered_by_id)
- `ix_regions_created_at` on `regions` (created_at)
- `ix_states_created_at` on `states` (created_at)
- `ix_status_change_requests_approved_by` on `status_change_requests` (approved_by)
- `ix_status_change_requests_requested_by` on `status_change_requests` (requested_by)
- `ix_transfer_requests_approved_by` on `transfer_requests` (approved_by)
- `ix_transfer_requests_requested_by` on `transfer_requests` (requested_by)
- `ix_users_approved_by` on `users` (approved_by)
- `ix_worker_absence_notices_acknowledged_by` on `worker_absence_notices` (acknowledged_by)
- `ix_worker_attendance_entered_by_id` on `worker_attendance` (entered_by_id)
- `ix_worker_removal_requests_decided_by` on `worker_removal_requests` (decided_by)
- `ix_worker_removal_requests_escalated_by` on `worker_removal_requests` (escalated_by)
- `ix_worker_removal_requests_requested_by` on `worker_removal_requests` (requested_by)
- `ix_worker_transfers_destination_approved_by` on `worker_transfers` (destination_approved_by)
- `ix_worker_transfers_origin_approved_by` on `worker_transfers` (origin_approved_by)
- `ix_worker_transfers_rejected_by` on `worker_transfers` (rejected_by)
- `ix_worker_transfers_requested_by_id` on `worker_transfers` (requested_by_id)
- `ix_workers_approved_by` on `workers` (approved_by)

The comparison also listed these 49 existing indexes as model removals, but each name exists in the remote catalog; this is a SQLAlchemy reflection/type-expression artifact, not evidence they should be dropped. Their full definitions are in the catalog snapshot. Fellowship FK gaps are: `fellowship_attendance.fellowship_id`, `fellowship_attendance_summaries.fellowship_id`, `fellowship_members.fellowship_id`, `fellowship_offerings.fellowship_id`, `fellowship_prayer_request.fellowship_id`, and `fellowship_testimony.fellowship_id`, each expected to reference `fellowships.fellowship_id`.

The 11 server-default differences are `dclm_groups.group_id`, `fellowships.fellowship_id`, `locations.location_id`, `nations.nation_id`, `offerings.status`, `regions.region_id`, `states.state_id`, `transfer_requests.reviews`, `worker_attendance_submissions.is_deleted`, `worker_attendance_submissions.operation`, and `worker_transfers.reviews`. Six type differences are the `fellowship_id` columns listed above. `workers.created_by` is represented as a named FK remotely (`fk_workers_created_by_users`, `ON DELETE SET NULL`), while the model comparison expects an unnamed FK; this must be reconciled deliberately.

## C. Local Alembic proof

These commands targeted only local Postgres at `127.0.0.1:55432`; no remote target was used.

1. **Empty database:** `python -m alembic upgrade head` exited 0 from an empty database. Final revision: `e2b4c6d8f013`; `location_expected_population.path` is PostgreSQL `ltree`; both expected-population indexes plus the primary-key index exist.
2. **Restored clone:** the source restored clone was at `e2b4c6d8f013` with no estimate rows. To prepare a disposable proof copy, I dropped only `location_expected_population` and its two-revision ledger state on that local copy, set its ledger to `c2e5a8f14b31`, then ran `alembic stamp d4a9c1e7f235`, `upgrade e2b4c6d8f013`, `downgrade d4a9c1e7f235`, and `upgrade e2b4c6d8f013`. All four Alembic commands exited 0. Final revision: `e2b4c6d8f013`; the expected-population table has three indexes including its primary key. The source restored clone and remote database were not modified by this proof.

`alembic/env.py` now defers creation of the new table's GiST index during empty-schema bootstrap, changes `path` to `ltree`, then creates the GiST index. This addresses the earlier empty-database bootstrap failure where the custom ltree model type initially compiled as varchar.

## D. Deployment runbook

### 1. Backup and identify the target

Configure a PostgreSQL service alias (`dclm_dev`) in the operator's protected `pg_service.conf` and credentials in a user-only `pgpass.conf`/`PGPASSFILE`. Do not place a database URI or password in a command argument, shell history, report, or log. Verify the alias identifies the intended development project before continuing.

**REMOTE READ:** Confirm the connection target without printing its password-bearing connection string:

```powershell
psql "service=dclm_dev" -v ON_ERROR_STOP=1 -c "SELECT current_database(), inet_server_addr(), current_user;"
```

**REMOTE READ / backup creation:** Create a custom-format dump and record its hash. The dump contains a copy of database contents and must be stored in the approved protected backup location.

```powershell
$backup = Join-Path $PWD ('church_server_pre_analytics_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.dump')
pg_dump --dbname="service=dclm_dev" --format=custom --no-owner --no-privileges --file $backup
if ($LASTEXITCODE -ne 0) { throw 'Backup failed; stop deployment.' }
Get-FileHash -Algorithm SHA256 $backup
pg_restore --list $backup | Select-Object -First 20
```

Also create a Supabase-managed snapshot through the project's approved backup process and restore the dump to a disposable local cluster before any deployment approval.

### 2. Read-only preflight

**REMOTE READ:** These commands use the service alias and run read-only transactions. Require the ledger to show `c2e5a8f14b31`; inspect the new tables and relevant objects before migration. If the baseline differs, stop and reconcile the schema first.

```powershell
psql "service=dclm_dev" -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY; SELECT version_num FROM alembic_version; SELECT to_regclass('public.count_reminder_recipients'), to_regclass('public.location_expected_population'); ROLLBACK;"
psql "service=dclm_dev" -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY; SELECT column_name, data_type, udt_name FROM information_schema.columns WHERE table_schema='public' AND table_name='locations' AND column_name IN ('is_active','opened_on','closed_on') ORDER BY column_name; SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename='counts' AND indexname IN ('ix_counts_approved_by_id','ix_counts_auto_accepted','ix_counts_supersedes_id','ix_counts_rejected_by_id') ORDER BY indexname; ROLLBACK;"
```

The six missing fellowship FKs, 46 missing named indexes, UUID/varchar differences, and default/nullability differences are pre-existing model/schema differences, not objects created by these two revisions. Have the database owner review these differences and the migration SQL before approval.

### 3. Apply the two pending revisions

**REMOTE WRITE ? requires your explicit deployment approval.** The operator must set `DATABASE_URL` and `SYNC_DATABASE_URL` in a protected process environment to the reviewed service connection. This adds the recipient-specific reminder table and versioned expected-attendance table, indexes, and RLS policies. It does not stamp the database.

```powershell
if (-not $env:SYNC_DATABASE_URL -or -not $env:DATABASE_URL) { throw 'Set both protected database environment variables first.' }
python -m alembic upgrade e2b4c6d8f013
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; preserve logs and use the rollback/restore decision below.' }
```

### 4. Verify after upgrade

**REMOTE READ:** Expect one ledger row at `e2b4c6d8f013`, both tables present, expected-population path type `ltree`, and indexes listed below. RLS policy presence should be checked before opening the feature to users.

```powershell
psql "service=dclm_dev" -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY; SELECT version_num FROM alembic_version; SELECT to_regclass('public.count_reminder_recipients'), to_regclass('public.location_expected_population'); SELECT column_name, data_type, udt_name, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='location_expected_population' ORDER BY ordinal_position; SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename IN ('count_reminder_recipients','location_expected_population') ORDER BY tablename,indexname; SELECT tablename, policyname, cmd FROM pg_policies WHERE schemaname='public' AND tablename='location_expected_population' ORDER BY policyname; ROLLBACK;"
```

Deploy the application code containing revision `e2b4c6d8f013`; verify State Overseer can view the empty estimate state and preview a CSV. **REMOTE WRITE ? requires separate approval:** applying any CSV creates version and audit rows. Test apply on the disposable local clone first; do not apply a remote CSV during read-only verification.

### 5. Roll back if migration verification fails

**REMOTE WRITE ? requires your explicit deployment approval.** Downgrading to `c2e5a8f14b31` drops the two new tables and any reminder/estimate rows written since deployment. Prefer restoring the pre-migration backup if user data has been entered.

```powershell
if (-not $env:SYNC_DATABASE_URL -or -not $env:DATABASE_URL) { throw 'Set both protected database environment variables first.' }
python -m alembic downgrade c2e5a8f14b31
if ($LASTEXITCODE -ne 0) { throw 'Downgrade failed; restore the verified backup through the approved recovery procedure.' }
```

**REMOTE READ:** After rollback, run the read-only ledger/table verification from step 2. A backup restore is a **REMOTE WRITE** and can replace data; confirm the exact target and follow the church's approved recovery procedure.

## Not performed

- No remote migration, stamp, DDL, DML, or role/permission update was run.
- The direct permission-grant rows for `counts:review` were not present in the saved schema catalog; schema presence does not prove RBAC assignment.
- Existing schema drift is documented, not repaired in this runbook.
