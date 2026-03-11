# API Documentation

Route-by-route details with request/response fields, errors, and diagnosis guidance.

## Base
- Base URL: `/api/v1`
- Auth: Bearer JWT (except `/public/*`, `/health`, `/`)
- Content-Type: `application/json`

## Common Errors
- `400` invalid input or business rule
- `401` missing/invalid token
- `403` permission or scope violation
- `404` not found
- `409` conflict
- `422` validation error

---

## Schemas (Fields Summary)
- **UserCreate**: `worker_id, email, password, roles[]`
- **UserResponse**: `user_id, worker_id, location_id, name, phone, email, is_active, roles[], path, approval_status`
- **WorkerCreate/Response**: `location_id, name, phone, email, unit, status, path, worker_id`
- **ProgramDomain/Type/Event**: `name, slug, domain_id, date, path, title`
- **CountCreate/Response**: demographics + `event_id, location_id, total, status`
- **OfferingCreate/Response**: `event_id, location_id, amount, payment_method, fund_type, status`
- **AttendanceCreate/Response**: `event_id, location_id, worker_id, status, reason`
- **RecordCreate/Response**: `event_id, location_id, record_type, name, gender, phone, details`
- **AnnouncementCreate/Response**: region fields + items[]
- **MediaGallery/MediaItem**: gallery meta + item file fields
- **SyncBatchRequest**: lists of counts/offerings/records/attendance/fellowship

---

## Authentication (`/auth`)

### POST `/auth/login`
- Purpose: Authenticate by email/password.
- Request: `{ email, password }`
- Response: `{ access_token, refresh_token, token_type }`
- Errors: `401` invalid credentials; `403` inactive/approval pending.
- Diagnosis: check approval status and role assignment.

### POST `/auth/refresh`
- Purpose: Refresh JWT.
- Request: `{ refresh_token }`
- Response: `{ access_token, refresh_token, token_type }`
- Errors: `401` invalid/expired refresh token.

### GET `/auth/me`
- Purpose: Current user profile.
- Response: `UserResponse`
- Errors: `401` missing token.

---

## Users (`/users`)

### GET `/users/`
- Purpose: List users in scope.
- Request: Query `skip, limit, scope_path`.
- Response: `List[UserResponse]`
- Errors: `403` scope violation.
- Diagnosis: scope_path must be descendant of current user path.

### POST `/users/`
- Purpose: Create user linked to worker.
- Request: `UserCreate`.
- Response: `UserResponse`.
- Errors: `400` email exists; `404` worker not found.
- Diagnosis: create worker first, use worker UUID.

### POST `/users/auto-create`
- Purpose: Auto-create user from worker email.
- Request: `{ email }`.
- Response: `{ user: UserResponse, temporary_password }`.
- Errors: `404` worker not found; `400` user already exists.

### GET `/users/state-region`
- Purpose: Return state/region from user path.
- Response: `{ state, region }`.

### POST `/users/verify-password`
- Purpose: Verify current user password.
- Request: `{ password }`.
- Response: `{ verified }`.
- Errors: `401` invalid token.

### GET `/users/{user_id}`
- Purpose: Get user by UUID.
- Response: `UserResponse`.
- Errors: `404` not found; `403` outside scope.

### PUT `/users/{user_id}`
- Purpose: Update user.
- Request: `UserUpdate`.
- Response: `UserResponse`.
- Errors: `404` not found; `403` outside scope.

### POST `/users/{user_id}/assign-roles`
- Purpose: Replace roles.
- Request: `{ role_ids }`.
- Response: `UserResponse`.
- Errors: `403` role score too high; `400` invalid role IDs.

### GET `/users/{user_id}/details`
- Purpose: User with embedded worker.
- Response: `UserFullResponse`.

### GET `/users/search`
- Purpose: Filter users.
- Request: Query `name, email, phone, location_id, is_active, scope_path`.
- Response: `List[UserResponse]`.

### GET `/users/with-roles`
- Purpose: List users with roles.
- Response: `List[UserResponse]`.

### DELETE `/users/{user_id}`
- Purpose: Soft delete user.
- Errors: `404` not found.

---

## Workers (`/workers`)

### GET `/workers/`
- Purpose: List workers in scope.
- Request: Query `skip, limit, scope_path`.
- Response: `List[WorkerResponse]`.

### GET `/workers/search`
- Purpose: Filter workers.
- Request: Query `user_id, phone, email, name, unit, gender, status, location_id, scope_path`.
- Response: `List[WorkerResponse]`.

### POST `/workers/`
- Purpose: Create worker.
- Request: `WorkerCreate`.
- Response: `WorkerResponse`.
- Errors: `400` phone/email exists; `404` location not found.

### GET `/workers/{worker_id}`
- Purpose: Get worker by UUID.
- Response: `WorkerResponse`.
- Errors: `404` not found; `403` outside scope.

### PUT `/workers/{worker_id}`
- Purpose: Update worker.
- Request: `WorkerUpdate`.
- Response: `WorkerResponse`.

### DELETE `/workers/{worker_id}`
- Purpose: Soft delete worker (and linked user).
- Errors: `404` not found.

---

## Hierarchy

Applies to `nations`, `states`, `regions`, `groups`, `locations`, `fellowships`.

### CRUD (each level)
- Purpose: Create, list, get, update, delete each hierarchy level.
- Request: level-specific create/update schema.
- Response: level response schema.
- Errors: `404` parent not found; `403` scope violation.

### GET `/locations/{location_id}/details`
- Purpose: Location with parent chain.
- Response: `LocationDetailResponse`.

### GET `/hierarchy/tree`
- Purpose: Full hierarchy tree.

### GET `/hierarchy/search`
- Purpose: Search hierarchy by name.

---

## Programs (`/programs`)

### GET `/programs/domains`
- Purpose: List domains.
- Response: `List[ProgramDomainResponse]`.

### POST `/programs/domains`
- Purpose: Create domain.
- Request: `ProgramDomainCreate`.
- Response: `ProgramDomainResponse`.
- Errors: `400` slug exists.

### PUT `/programs/domains/{id}` / DELETE `/programs/domains/{id}`
- Purpose: Update/delete domain.
- Errors: `404` not found.

### GET `/programs/types`
- Purpose: List types (optional `domain_id`).
- Response: `List[ProgramTypeResponse]`.

### POST `/programs/types`
- Purpose: Create type.
- Request: `ProgramTypeCreate`.
- Errors: `404` domain not found; `400` slug exists.

### PUT `/programs/types/{id}` / DELETE `/programs/types/{id}`
- Purpose: Update/delete type.
- Errors: `404` not found.

### GET `/programs/events`
- Purpose: List events with filters.
- Request (query): `program_type, program_domain, title, level, location_id, date, start_month, end_month, start_year, end_year`.
- Response: `List[ProgramEventResponse]`.

### POST `/programs/events`
- Purpose: Create event.
- Request: `ProgramEventCreate`.
- Errors: `403` path outside scope; `404` type not found.

### PUT `/programs/events/{event_id}` / DELETE `/programs/events/{event_id}`
- Purpose: Update/delete event.
- Errors: `404` not found; `403` path outside scope.

---

## Counts (`/counts`)

### POST `/counts/`
- Purpose: Create count.
- Request: `CountCreate`.
- Response: `CountResponse`.

### GET `/counts/`
- Purpose: List counts in scope.
- Query: `skip, limit, scope_path`.

### GET `/counts/aggregate`
- Purpose: Aggregate by location.
- Query: `program_domain, program_type, location_id, start_date, end_date`.

### GET `/counts/aggregate-flex`
- Purpose: Aggregate by level.
- Query: `view_level` (state|region|group|location).

### GET `/counts/{id}` / PUT `/counts/{id}` / DELETE `/counts/{id}`
- Purpose: Get/update/delete count.
- Errors: `404` not found.

### POST `/counts/batch`
- Purpose: Batch create counts.
- Request: `List[CountCreate]`.
- Response: `SyncResult`.

### GET `/counts/stats`
- Purpose: Population statistics wrapper.

---

## Offerings (`/offerings`)

### POST `/offerings/`
- Purpose: Create offering.
- Request: `OfferingCreate`.
- Response: `OfferingResponse`.

### GET `/offerings/`
- Purpose: List offerings.
- Query: `fund_type, location_id, start_date, end_date, amount`.

### GET `/offerings/{id}` / PUT `/offerings/{id}` / DELETE `/offerings/{id}`
- Purpose: Get/update/delete offering.
- Errors: `404` not found.

### POST `/offerings/batch`
- Purpose: Batch create offerings.
- Request: `List[OfferingCreate]`.
- Response: `SyncResult`.

### GET `/offerings/stats`
- Purpose: Aggregate offering stats.

---

## Tithes (`/tithes`)

Same as offerings, with fixed `fund_type="tithe"`.

---

## Attendance (`/attendance`)

- `GET /attendance/workers` list workers for location.
- `POST /attendance/` create attendance (`WorkerAttendanceCreate`).
- `GET /attendance/` list attendance.
- `GET /attendance/{id}` get attendance.
- `PUT /attendance/{id}` update attendance.
- `POST /attendance/batch` batch create.
- `GET /attendance/stats` aggregate.
- `DELETE /attendance/{id}` soft delete.

---

## Records (`/records`, `/newcomers`, `/converts`)

- `POST /records/` create record (`RecordCreate`).
- `GET /records/` list records.
- `GET /records/{id}` get record.
- `PUT /records/{id}` update.
- `POST /records/batch` batch create.
- `DELETE /records/{id}` delete.

`/newcomers` and `/converts` mirror `/records` with fixed `record_type`.

---

## Fellowship Activities (`/fellowships`)

Members
- `POST /fellowships/members`
- `GET /fellowships/members`
- `PUT /fellowships/members/{id}`
- `DELETE /fellowships/members/{id}`

Attendance
- `POST /fellowships/attendance`
- `GET /fellowships/attendance`
- `PUT /fellowships/attendance/{id}`
- `DELETE /fellowships/attendance/{id}`

Offerings
- `POST /fellowships/offerings`
- `GET /fellowships/offerings`
- `PUT /fellowships/offerings/{id}`
- `DELETE /fellowships/offerings/{id}`

Testimonies
- `POST /fellowships/testimonies`
- `GET /fellowships/testimonies`
- `PUT /fellowships/testimonies/{id}`
- `DELETE /fellowships/testimonies/{id}`

Prayer Requests
- `POST /fellowships/prayer-requests`
- `GET /fellowships/prayer-requests`
- `PUT /fellowships/prayer-requests/{id}`
- `DELETE /fellowships/prayer-requests/{id}`

Attendance Summaries
- `POST /fellowships/attendance-summaries`
- `GET /fellowships/attendance-summaries`
- `PUT /fellowships/attendance-summaries/{id}`
- `DELETE /fellowships/attendance-summaries/{id}`

---

## Announcements / Information

- `POST /announcements/` create
- `GET /announcements/` list
- `GET /announcements/{id}` get
- `PUT /announcements/{id}` update
- `POST /announcements/{id}/deactivate` deactivate
- `DELETE /announcements/{id}` delete

Information routes mirror announcements.

---

## Media (`/media`)

Galleries
- `POST /media/galleries` create
- `GET /media/galleries` list
- `GET /media/galleries/{id}` get
- `DELETE /media/galleries/{id}` delete

Items
- `POST /media/items` create
- `GET /media/items` list
- `GET /media/items/{id}` get
- `DELETE /media/items/{id}` delete

---

## Reports (`/reports`)

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

## Statistics (`/statistics`)

- `GET /statistics/read-population/`
- `GET /statistics/church-statistics/`
- `GET /statistics/get-user-statistics/`

---

## Sync (`/sync`)

- `POST /sync/batch` batch upload (SyncBatchRequest).
- `GET /sync/changes?since=ISO-8601` incremental changes.
- `GET /sync/conflicts` list conflicts.
- `POST /sync/resolve` resolve by `conflict_id` and `resolution`.

---

## Approvals (`/approvals`)

- Transfer: `POST /transfers`, `GET /transfers`, `POST /transfers/{id}/approve`, `POST /transfers/{id}/reject`
- Status change: `POST /status-changes`, `GET /status-changes`, `POST /status-changes/{id}/approve`, `POST /status-changes/{id}/reject`

---

## RBAC (`/rbac`)

- Permissions: `GET/POST/PUT/DELETE /permissions`
- Roles: `GET/POST/PUT/DELETE /roles`
- Role Scores: `GET/POST/PUT/DELETE /role-scores`
- Assign permissions: `POST /roles/{id}/permissions`, `DELETE /roles/{id}/permissions`
- Available roles: `GET /roles/available`

---

## Recovery (`/recovery`)

- `POST /request-reset`
- `POST /verify-token`
- `POST /reset-password`
- `POST /set-recovery-question`
- `GET /read-recovery-question`
- `PATCH /update-recovery-question`

---

## System (`/system`)

- `GET /system/meta`
- `GET /system/metrics`
- `POST /system/seed`

---

## Public (`/public`)

- Events: `GET /public/events`, `GET /public/events/{id}`
- Locations: `GET /public/locations`, `GET /public/locations/nearby`
- Galleries: `GET /public/galleries`, `GET /public/galleries/{id}`
- Announcements: `GET /public/announcements`
- Forms: `POST /public/workers/register`, `POST /public/contact`, `POST /public/prayer-request`
- App Versions: `GET /public/app-version`, `GET /public/app-versions`

---

## WebSocket

- `GET /ws` with JWT query param or header.

