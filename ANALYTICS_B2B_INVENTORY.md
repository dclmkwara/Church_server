# B2b Inventory: Expected Sunday Attendance

**Inventory date:** 7 November 2026  
**Scope:** Read-only source review before adding any estimated or expected population field.

## Finding

The current application has no location-level estimate for expected congregation attendance or population. There is no existing field to reuse or version. `WorkerAttendanceSubmission.expected_workers_count` is a meeting roster snapshot for workers; it is not a congregation estimate and must keep its current meaning.

## Source-by-source inspection

| Area | Existing data inspected | Result |
|---|---|---|
| `app/models/location.py` — `Location` | `location_id`, hierarchy (`group_id`, `path`), code/name, church type, address/contact, coordinates, active state and opening/closing dates | No population, membership-size, expected-attendance or estimate field. |
| `app/models/location_profile.py` — `LocationProfile` | History, founding date/name, full address, landmark, map URL, projects and cover image | No estimate field. The profile is documentary/public information and is not a safe place to overload with attendance estimates. |
| `app/models/attendance.py` — `WorkerAttendanceSubmission` | `expected_workers_count`, `present_count`, roster snapshot and event/program metadata | This is the expected worker roster for a specific workers' meeting submission. It is not an expected Sunday congregation size. Reusing it would change its meaning and corrupt worker-attendance reporting. |
| `app/schemas/location.py` | `LocationCreate`, `LocationUpdate`, `LocationResponse`, `LocationDetailResponse` | Location create/update schemas contain identity, address, coordinates and church type only. No estimate can be sent or returned. |
| Location and hierarchy pages | `app/frontend/dclm_admin/routes/organization.py`; location profile form and hierarchy explorer | The editable location/profile fields are descriptive location data. No expected-population control exists. |
| Hierarchy import template and import flow | `/bulk/templates/hierarchy`, `app/api/v1/routes/bulk_import.py`, hierarchy import UI | Bulk hierarchy template/import handles hierarchy/location basics. No expected-population column or import mapping exists. |
| Worker import template | `/bulk/templates/workers` and worker import flow | Worker identity and role data only; no location attendance estimate. |
| Count and reporting data | `Count` stores submitted population counts by program/date/source; aggregate attendance submissions store worker roster snapshots | These are actual reports, not a maintained estimate or versioned expectation. |

## Sample values

There are no non-identifying estimate values to show because no such field or table exists in the inspected models, schemas, forms, or import templates. Existing actual `Count.total` values and worker roster sizes represent submissions and must not be treated as estimates.

## Consequence for B2b

Add a separate, versioned location estimate record with value, effective-from date, author, and note. Keep it scoped to Sunday Worship analytics. Do not add a duplicate field to `LocationProfile` or reinterpret worker-attendance data. This inventory was written before the B2b implementation began.

## Read-only development database verification

The configured remote development database was inspected read-only before the additive schema change was prepared:

- `to_regclass('public.location_expected_population')` returned `NULL`; the table does not exist there.
- The `locations` and `location_profiles` column inventories contain no expected, estimated population, membership-size, or attendance estimate column.
- The `alembic_version` relation exists but contains no revision rows, while the database already contains 52 public tables. This is an unbaselined/pre-existing schema, so applying the new Alembic head directly would be unsafe. No migration was run against that database.
- Ten warmed `SELECT 1` round trips measured 134.7 ms minimum, 163.5 ms median, and 191.1 ms maximum from the app host to remote Supabase. These are connection round-trip figures, not dashboard response times.

The additive migration is verified only against a disposable local restored development clone. It creates the table and indexes without seeding estimates. This does not substitute for reconciling the remote Alembic baseline and applying the migration there.
