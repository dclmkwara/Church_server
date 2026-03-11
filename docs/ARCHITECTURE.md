# Architecture

## What This Server Is
The DCLM Church Management System is a FastAPI backend for Deeper Christian Life Ministry, Kwara State branch. It manages church structure, membership/worker data, attendance, offerings, and reporting. It provides authenticated admin APIs and a public-facing read-only API.

## Core Subsystems
- **Hierarchy**: Nation → State → Region → Group → Location → Fellowship.
- **Users/Workers**: Workers are profiles; Users are auth accounts tied to workers.
- **Programs**: Domains, types, and scheduled events; Counts/Offerings/Attendance link to events.
- **Data Collection**: Counts, offerings (incl. tithes), worker attendance, records.
- **Reports/Statistics**: Materialized views + aggregations + exports.
- **RBAC**: Permissions and role scores define scope and action limits.
- **Sync**: Offline batching with conflict detection/resolution.

## Hierarchy Model
Every hierarchical entity has an `ltree` path. Example:
```
org.234.kw.iln.ile.001
```
- `org.234`: nation
- `kw`: state
- `iln`: region
- `ile`: group
- `001`: location

### Display ID Sample (Kwara)
`DCM-234-KW-ILN-ILE-001` means: General church brand ID → Nigeria → Kwara State → Ilorin Region → Ilorin East Group → Living Spring Church (Lajolo Polygate area).

Fellowships are the leaf level under locations.

## Scope Enforcement (Row-Level Control)
- All scoped queries include `path <@ :scope_path`.
- This enforces row-level access from the user’s scope downwards.
- Users can only read/update data in their subtree.

## Users and Workers
- **Worker** must exist before **User** can be created.
- User stores denormalized data from worker (name, phone, location, path) for fast access.
- Deleting a worker soft-deletes the linked user.

## Programs and Events
- Program Domains (category) → Program Types → Program Events.
- Counts, Offerings, Attendance, Records link to Program Events for date/type context.

## Data Flow (Counts/Offerings/Attendance)
1. Client posts data linked to an event + location + path.
2. Data stored with `path` and `client_id` for idempotency.
3. Reports query materialized views or aggregate tables.

## Tradeoffs
- Some exports are built on large result sets; use date filters.
- Sync conflict resolution is conservative and rule-based.
