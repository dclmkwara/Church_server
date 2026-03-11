# Route Details (Exhaustive Examples)

This page provides route-by-route request/response fields, errors, and diagnosis guidance.

## Base
- Base URL: `/api/v1`
- Auth: Bearer JWT (except `/public/*`, `/health`, `/`)
- Content-Type: `application/json`

## Common Error Patterns
- `400`: invalid input or failed business rule
- `401`: missing/invalid token
- `403`: permission or scope violation
- `404`: entity not found
- `409`: duplicate or conflict
- `422`: schema validation error

---

## Authentication

### POST `/auth/login`
Purpose: Authenticate by email + password.

Request
```json
{ "email": "admin@example.com", "password": "Secret123" }
```

Response
```json
{ "access_token": "<jwt>", "refresh_token": "<jwt>", "token_type": "bearer" }
```

Errors: `401` invalid creds; `403` inactive or approval pending.
Diagnosis: check approval status and roles.

### POST `/auth/refresh`
Request
```json
{ "refresh_token": "<jwt>" }
```
Response
```json
{ "access_token": "<jwt>", "refresh_token": "<jwt>", "token_type": "bearer" }
```

### GET `/auth/me`
Response
```json
{ "user_id": "uuid", "worker_id": "uuid", "location_id": "001", "name": "Admin", "phone": "+234...", "email": "admin@example.com", "roles": [], "path": "org.234.kw", "approval_status": "approved" }
```

---

## Users

### GET `/users/`
Query: `skip`, `limit`, `scope_path`
Response: `List[UserResponse]`.
Errors: `403` scope violation.
Diagnosis: scope_path must be descendant of current user path.

### POST `/users/`
Request (UserCreate)
```json
{ "worker_id": "uuid", "email": "user@example.com", "password": "Secret123", "roles": [2,3] }
```
Response (UserResponse)
```json
{ "user_id": "uuid", "worker_id": "uuid", "location_id": "001", "name": "John", "phone": "+234...", "email": "user@example.com", "is_active": true, "roles": [], "path": "org.234.kw.iln.ile.001", "approval_status": "pending", "approved_by": null, "approved_at": null, "rejection_reason": null }
```
Errors: `400` email exists; `404` worker not found.
Diagnosis: create worker first; ensure worker UUID.

### POST `/users/auto-create`
Request
```json
{ "email": "worker@example.com" }
```
Response
```json
{ "user": { "user_id": "uuid", "email": "worker@example.com" }, "temporary_password": "john" }
```
Errors: `404` worker not found; `400` user exists.

### GET `/users/state-region`
Response
```json
{ "state": "kw", "region": "iln" }
```

### POST `/users/verify-password`
Request
```json
{ "password": "Secret123" }
```
Response
```json
{ "verified": true }
```

### GET `/users/{user_id}`
Response: `UserResponse`.
Errors: `404` not found; `403` outside scope.

### PUT `/users/{user_id}`
Request (UserUpdate)
```json
{ "email": "new@example.com", "password": "NewSecret123", "is_active": false, "roles": [2] }
```
Response: `UserResponse`.

### POST `/users/{user_id}/assign-roles`
Request
```json
{ "role_ids": [1,2] }
```
Response: `UserResponse`.
Errors: `403` role score too high; `400` invalid role IDs.

### GET `/users/{user_id}/details`
Response: `UserFullResponse` with embedded worker.

### GET `/users/search`
Query: `name, email, phone, location_id, is_active, scope_path, skip, limit`.
Response: `List[UserResponse]`.

### GET `/users/with-roles`
Response: `List[UserResponse]`.

### DELETE `/users/{user_id}`
Response: `null`.

---

## Workers

### GET `/workers/`
Query: `skip, limit, scope_path`.
Response: `List[WorkerResponse]`.

### GET `/workers/search`
Query: `user_id, phone, email, name, unit, gender, status, location_id, scope_path`.
Response: `List[WorkerResponse]`.

### POST `/workers/`
Request
```json
{ "location_id": "001", "location_name": "Ilorin East", "church_type": "DLBC", "state": "Kwara", "region": "Ilorin North", "group": "Ilorin East", "name": "Jane Doe", "gender": "Female", "phone": "+234...", "email": "jane@example.com", "unit": "Choir", "status": "Active" }
```
Response
```json
{ "id": 1, "worker_id": "uuid", "location_id": "001", "name": "Jane Doe", "phone": "+234...", "path": "org.234.kw.iln.ile.001", "created_at": "2026-03-11T00:00:00Z" }
```
Errors: `400` phone/email exists; `404` location not found.

### GET `/workers/{worker_id}`
Response: `WorkerResponse`.
Errors: `404` not found; `403` outside scope.

### PUT `/workers/{worker_id}`
Request (WorkerUpdate)
```json
{ "unit": "Usher", "status": "Inactive" }
```
Response: `WorkerResponse`.

### DELETE `/workers/{worker_id}`
Response: `null`.

---

## Hierarchy

Applies to `nations`, `states`, `regions`, `groups`, `locations`, `fellowships`.

### Common Fields
- `id` or `<level>_id`
- `name`
- `path`
- `parent_id` (except nation)

### CRUD (each level)
- `POST /<level>/` create
- `GET /<level>/` list
- `GET /<level>/{id}` get
- `PUT /<level>/{id}` update
- `DELETE /<level>/{id}` delete

Errors: `403` scope violation; `404` parent not found.

### GET `/locations/{location_id}/details`
Response: Location with parent chain and metadata.

### GET `/hierarchy/tree`
Response: tree nodes with children.

### GET `/hierarchy/search`
Query: `q`
Response: list of matching nodes.

---

## Programs

### Domains
- `GET /programs/domains`
- `POST /programs/domains`
- `PUT /programs/domains/{id}`
- `DELETE /programs/domains/{id}`

### Types
- `GET /programs/types?domain_id=`
- `POST /programs/types`
- `PUT /programs/types/{id}`
- `DELETE /programs/types/{id}`

### Events
- `GET /programs/events` filters: `program_type, program_domain, title, level, location_id, date, start_month, end_month, start_year, end_year`.
- `GET /programs/events/{event_id}`
- `POST /programs/events`
- `PUT /programs/events/{event_id}`
- `DELETE /programs/events/{event_id}`

Example Create
```json
{ "program_type_id": 1, "date": "2026-03-10", "path": "org.234.kw.iln.ile.001", "title": "Sunday Service" }
```

Errors: `403` path outside scope; `404` type not found.

---

## Counts

### POST `/counts/`
Request (CountCreate)
```json
{ "event_id": "uuid", "location_id": "001", "adult_male": 10, "adult_female": 12, "youth_male": 6, "youth_female": 7, "boys": 3, "girls": 4, "note": "" }
```
Response (CountResponse)
```json
{ "id": "uuid", "event_id": "uuid", "location_id": "001", "total": 42, "status": "pending", "path": "org.234.kw.iln.ile.001", "entered_by_id": "uuid" }
```

### GET `/counts/`
Query: `skip, limit, scope_path`.
Response: `List[CountResponse]`.

### GET `/counts/aggregate`
Query: `program_domain, program_type, location_id, start_date, end_date`.
Response: list of aggregate rows per location.

### GET `/counts/aggregate-flex`
Query: `view_level` (state|region|group|location).
Response: aggregates grouped by ltree subpath.

### GET `/counts/{id}` / PUT `/counts/{id}` / DELETE `/counts/{id}`
Response: CountResponse (GET/PUT), `null` (DELETE).

### POST `/counts/batch`
Request
```json
[ { "event_id": "uuid", "location_id": "001", "adult_male": 10 } ]
```
Response
```json
{ "synced": 1, "duplicates": 0, "errors": 0, "details": [ { "status": "synced" } ] }
```

### GET `/counts/stats`
Query: `program_domain, program_type, location_id, start_month, end_month, start_year, end_year`.
Response: statistics object.

---

## Offerings

### POST `/offerings/`
Request
```json
{ "event_id": "uuid", "location_id": "001", "amount": 15000.00, "payment_method": "cash", "fund_type": "offering" }
```
Response
```json
{ "id": "uuid", "amount": 15000.00, "fund_type": "offering", "status": "pending" }
```

### GET `/offerings/`
Query: `fund_type, location_id, start_date, end_date, amount`.
Response: `List[OfferingResponse]`.

### GET/PUT/DELETE `/offerings/{id}`
Response: `OfferingResponse` (GET/PUT), `null` (DELETE).

### POST `/offerings/batch`
Request
```json
[ { "event_id": "uuid", "location_id": "001", "amount": 15000, "payment_method": "cash" } ]
```
Response: `SyncResult`.

### GET `/offerings/stats`
Query: `start_date, end_date, fund_type`.
Response: `{ count, total_amount }`.

---

## Tithes

Same as offerings with fixed `fund_type="tithe"` under `/tithes`.

---

## Attendance

### POST `/attendance/`
Request
```json
{ "event_id": "uuid", "location_id": "001", "worker_id": "uuid", "status": "present" }
```
Response
```json
{ "id": "uuid", "worker_id": "uuid", "status": "present", "worker_name": "Jane Doe" }
```

### GET `/attendance/workers`
Query: `location_id`.
Response: list of workers.

### GET/PUT/DELETE `/attendance/{id}`
Response: `WorkerAttendanceResponse` (GET/PUT), `null` (DELETE).

### POST `/attendance/batch`
Request: `List[WorkerAttendanceCreate]`.
Response: `SyncResult`.

### GET `/attendance/stats`
Query: `start_date, end_date`.
Response: `{ count, present, absent, late, excused }`.

---

## Records / Newcomers / Converts

### POST `/records/`
Request
```json
{ "event_id": "uuid", "location_id": "001", "record_type": "newcomer", "name": "Visitor", "gender": "Male", "phone": "+234...", "details": { "occupation": "Engineer" } }
```
Response
```json
{ "id": "uuid", "record_type": "newcomer", "status": "pending" }
```

`/newcomers` and `/converts` mirror `/records` with fixed `record_type`.

---

## Fellowship Activities

Members
- `POST /fellowships/members` (FellowshipMemberCreate)
- `GET /fellowships/members`
- `PUT /fellowships/members/{id}`
- `DELETE /fellowships/members/{id}`

Attendance
- `POST /fellowships/attendance` (FellowshipAttendanceCreate)
- `GET /fellowships/attendance`
- `PUT /fellowships/attendance/{id}`
- `DELETE /fellowships/attendance/{id}`

Offerings
- `POST /fellowships/offerings` (FellowshipOfferingCreate)
- `GET /fellowships/offerings`
- `PUT /fellowships/offerings/{id}`
- `DELETE /fellowships/offerings/{id}`

Testimonies
- `POST /fellowships/testimonies` (TestimonyCreate)
- `GET /fellowships/testimonies`
- `PUT /fellowships/testimonies/{id}`
- `DELETE /fellowships/testimonies/{id}`

Prayer Requests
- `POST /fellowships/prayer-requests` (PrayerRequestCreate)
- `GET /fellowships/prayer-requests`
- `PUT /fellowships/prayer-requests/{id}`
- `DELETE /fellowships/prayer-requests/{id}`

Attendance Summaries
- `POST /fellowships/attendance-summaries` (AttendanceSummaryCreate)
- `GET /fellowships/attendance-summaries`
- `PUT /fellowships/attendance-summaries/{id}`
- `DELETE /fellowships/attendance-summaries/{id}`

---

## Announcements / Information

### POST `/announcements/`
Request
```json
{ "region_id": "KW-ILN", "region_name": "Ilorin North", "date": "2026-03-10", "items": [ { "title": "Reminder", "text": "Service starts 8am" } ] }
```
Response
```json
{ "id": "uuid", "region_name": "Ilorin North", "items": [ { "id": 1, "title": "Reminder" } ] }
```

### GET `/announcements/`
Query: `region_id, date, is_active`.
Response: list of announcements.

### GET/PUT/DELETE `/announcements/{id}`

### POST `/announcements/{id}/deactivate`
Deactivates announcement.

Information routes mirror announcements.

---

## Media

Galleries
- `POST /media/galleries` (MediaGalleryCreate)
- `GET /media/galleries`
- `GET /media/galleries/{id}`
- `DELETE /media/galleries/{id}`

Items
- `POST /media/items` (MediaItemCreate)
- `GET /media/items`
- `GET /media/items/{id}`
- `DELETE /media/items/{id}`

---

## Reports

- `GET /reports/summary`
- `GET /reports/financial`
- `GET /reports/attendance`
- `GET /reports/timeseries` (metric, interval)
- `GET /reports/by-level` (metric, level)
- `GET /reports/anomalies`
- `GET /reports/growth-rate`
- `GET /reports/export/csv` (report_type)
- `POST /reports/export/excel` (report_type)
- `POST /reports/export/pdf` (report_type)
- `POST /reports/refresh`

---

## Statistics

- `GET /statistics/read-population/`
- `GET /statistics/church-statistics/`
- `GET /statistics/get-user-statistics/`

---

## Sync

- `POST /sync/batch` (SyncBatchRequest)
- `GET /sync/changes?since=ISO-8601`
- `GET /sync/conflicts`
- `POST /sync/resolve` (conflict_id, resolution)

---

## Approvals

- Transfer: `POST /approvals/transfers`, `GET /approvals/transfers`, `POST /approvals/transfers/{id}/approve`, `POST /approvals/transfers/{id}/reject`
- Status: `POST /approvals/status-changes`, `GET /approvals/status-changes`, `POST /approvals/status-changes/{id}/approve`, `POST /approvals/status-changes/{id}/reject`

---

## RBAC

- Permissions: `GET/POST/PUT/DELETE /rbac/permissions`
- Roles: `GET/POST/PUT/DELETE /rbac/roles`
- Role Scores: `GET/POST/PUT/DELETE /rbac/role-scores`
- Assign permissions: `POST /rbac/roles/{id}/permissions`, `DELETE /rbac/roles/{id}/permissions`
- Available roles: `GET /rbac/roles/available`

---

## Recovery

- `POST /recovery/request-reset`
- `POST /recovery/verify-token`
- `POST /recovery/reset-password`
- `POST /recovery/set-recovery-question`
- `GET /recovery/read-recovery-question`
- `PATCH /recovery/update-recovery-question`

---

## System

- `GET /system/meta`
- `GET /system/metrics`
- `POST /system/seed`

---

## Public

- `GET /public/events`
- `GET /public/events/{id}`
- `GET /public/locations`
- `GET /public/locations/nearby`
- `GET /public/galleries`
- `GET /public/galleries/{id}`
- `GET /public/announcements`
- `POST /public/workers/register`
- `POST /public/contact`
- `POST /public/prayer-request`
- `GET /public/app-version`
- `GET /public/app-versions`

---

## WebSocket

- `GET /ws` with JWT query param or header.

