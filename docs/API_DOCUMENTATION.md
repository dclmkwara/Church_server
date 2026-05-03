# API Documentation

## Base URL & Shared Rules

| Property | Value |
|---|---|
| Base URL | `/api/v1` |
| Auth header | `Authorization: Bearer <access_token>` |
| Content-Type | `application/json` (except login) |
| Login Content-Type | `application/x-www-form-urlencoded` |
| Response format | JSON |
| Pagination | `?skip=0&limit=100` query params |

### Common HTTP Error Codes

| Code | Meaning |
|---|---|
| `400` | Bad request — invalid input or failed business rule |
| `401` | Unauthorized — token missing, expired, or account pending approval |
| `403` | Forbidden — valid token but insufficient permission or outside scope |
| `404` | Not found — entity does not exist |
| `409` | Conflict — duplicate record (e.g., duplicate phone/email) |
| `422` | Unprocessable Entity — Pydantic schema validation failed |

---

## 🔐 Authentication — `/api/v1/auth/`

### `POST /api/v1/auth/login`
Authenticate and receive JWT tokens. Uses OAuth2 form encoding (not JSON).

**Request:** `application/x-www-form-urlencoded`
```
username=pastor@dlbc.org&password=SecurePass123!
```

**Response (200):**
```json
{
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "bearer"
}
```

**Notes:**
- `username` field receives the user's **email address**
- User must have `is_active = true` and `approval_status = 'approved'`
- JWT claims include `role`, `score`, `home_path`, and `scope_path`

**Errors:** `400` wrong credentials or account deactivated | `401` account pending or rejected

---

### `POST /api/v1/auth/refresh`
Exchange a refresh token for a new access token.

**Request (JSON):**
```json
{ "refresh_token": "eyJhbGci..." }
```

**Response (200):** Same as login response.

**Notes:** Roles and scope are **recalculated from DB** on every refresh.

---

### `GET /api/v1/auth/me`
Get the profile of the currently logged-in user.

**Response (200):**
```json
{
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "worker_id": "660e8400-...",
    "name": "John Adebayo",
    "email": "john@dlbc.org",
    "phone": "+2348012345678",
    "location_id": "001",
    "is_active": true,
    "approval_status": "approved",
    "path": "org.234.KW.ILN.ILE.001",
    "roles": [{ "id": 5, "role_name": "GroupPastor", "score": { "score": 4 } }],
    "created_at": "2026-01-20T10:30:00Z"
}
```

---

## 👷 Workers — `/api/v1/workers/`

Workers are church members who serve in any capacity. They are the primary entity that must exist before a user account can be created.

**Required permission:** `workers:read` / `workers:create`

---

### `GET /api/v1/workers/`
List all workers within the current user's scope.

**Query Params:**
| Param | Type | Default | Description |
|---|---|---|---|
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 100 | Max results |
| `scope_path` | string | user's path | Restrict to a sub-path |

**Response (200):** `Array<WorkerResponse>`

---

### `GET /api/v1/workers/search`
Search workers by multiple optional fields.

**Query Params:**
| Param | Description |
|---|---|
| `user_id` | Custom worker ID (e.g., `W-001`) |
| `phone` | Phone number |
| `email` | Email address |
| `name` | Full name (partial match) |
| `unit` | Serving unit (Ushering, Choir, etc.) |
| `gender` | `Male` or `Female` |
| `status` | `Active`, `Inactive`, or `Suspended` |
| `location_id` | Specific location |
| `scope_path` | Restrict to sub-path |

---

### `POST /api/v1/workers/`
Register a new church worker.

**Request:**
```json
{
    "location_id": "001",
    "location_name": "GRA DLBC",
    "church_type": "DLBC",
    "state": "Kwara",
    "region": "Ilorin North",
    "group": "Ilorin East",
    "name": "Adebayo Oluwaseun",
    "gender": "Male",
    "phone": "+2348012345678",
    "email": "adebayo@example.com",
    "address": "12 Cathedral Road, Ilorin",
    "occupation": "Teacher",
    "marital_status": "Married",
    "unit": "Ushering",
    "status": "Active"
}
```

**Response (201):**
```json
{
    "id": 1,
    "worker_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "W-001",
    "location_id": "001",
    "name": "Adebayo Oluwaseun",
    "phone": "+2348012345678",
    "email": "adebayo@example.com",
    "unit": "Ushering",
    "status": "Active",
    "approval_status": "pending_verification",
    "path": "org.234.KW.ILN.ILE.001",
    "created_at": "2026-03-10T08:00:00Z"
}
```

**Errors:** `400` phone/email already exists | `404` location not found

---

### `GET /api/v1/workers/{worker_id}`
Get a single worker by their UUID.

**Response (200):** `WorkerResponse`
**Errors:** `404` not found | `403` outside scope

---

### `PUT /api/v1/workers/{worker_id}`
Update worker details. Only fields provided in the request body are changed.

**Request (partial update supported):**
```json
{
    "unit": "Choir",
    "status": "Inactive",
    "address": "New Address"
}
```

---

### `DELETE /api/v1/workers/{worker_id}`
Soft-delete a worker (sets `is_deleted = true`, does not remove the record).

---

### `GET /api/v1/workers/pending`
List workers with `approval_status = 'pending_verification'` — awaiting pastor's approval.

---

### `POST /api/v1/workers/{worker_id}/approve`
Approve a worker's registration. Updates `approval_status` to `approved`.

---

### `POST /api/v1/workers/{worker_id}/reject`
Reject a worker's registration.

**Request:**
```json
{ "reason": "Cannot verify identity at this branch" }
```

---

## 👤 Users — `/api/v1/users/`

Users are authentication accounts linked 1:1 to workers. A worker must exist first.

**Required permission:** `users:read` / `users:create`

---

### `GET /api/v1/users/`
List users in scope. Same `skip`, `limit`, `scope_path` pagination as workers.

---

### `POST /api/v1/users/`
Create a user account for an existing worker.

**Request:**
```json
{
    "worker_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "adebayo@example.com",
    "password": "SecurePass123!",
    "roles": [1, 2]
}
```

**Notes:** Password is auto-hashed. User inherits `location_id` and `path` from the worker.

---

### `POST /api/v1/users/auto-create`
Create a user account automatically for a worker using just the worker's email. System sets a temporary password.

**Request:**
```json
{ "email": "adebayo@example.com" }
```

**Response:**
```json
{
    "user": { "user_id": "...", "email": "adebayo@example.com" },
    "temporary_password": "Adebayo@2026"
}
```

---

### `GET /api/v1/users/{user_id}`
Get user by UUID.

---

### `PUT /api/v1/users/{user_id}`
Update user (email, password, roles, is_active).

---

### `POST /api/v1/users/{user_id}/assign-roles`
Assign one or more roles to a user.

**Request:**
```json
{ "role_ids": [3, 5] }
```

**Notes:** You cannot assign a role with a score >= your own score.

---

### `DELETE /api/v1/users/{user_id}`
Soft-delete a user account.

---

### `GET /api/v1/users/search`
Search users by name, email, phone, location, active status, and scope.

---

## ✅ User Approvals — `/api/v1/user-approval/`

This module handles the two-step approval workflow for user accounts (distinct from worker registration approval).

---

### `GET /api/v1/user-approval/pending`
List users with `approval_status = 'pending'` in the requesting admin's scope.

**Response:** `Array<UserApprovalResponse>` — includes linked worker details.

---

### `POST /api/v1/user-approval/{user_id}/approve`
Approve a user's app access request.

**Request:**
```json
{ "notes": "Confirmed active worker at GRA branch." }
```

**Notes:** Sets `approval_status = 'approved'` and records `approved_by` and `approved_at`.

---

### `POST /api/v1/user-approval/{user_id}/reject`
Reject a user's app access request with a mandatory reason.

**Request:**
```json
{ "reason": "Worker record could not be verified." }
```

---

### `POST /api/v1/user-approval/{user_id}/deactivate`
Deactivate an active user account (suspends access without deletion).

---

### `POST /api/v1/user-approval/{user_id}/reactivate`
Reactivate a previously deactivated account.

---

## 🏛️ Hierarchy — `/api/v1/hierarchy/`

Manage the church's organizational structure. Separate CRUD endpoints exist for each level: `nations`, `states`, `regions`, `groups`, `locations`, `fellowships`.

**Required permission:** `hierarchy:read` / `hierarchy:manage`

---

### Pattern for Each Level
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/{level}/` | Create a new node |
| `GET` | `/api/v1/{level}/` | List all nodes |
| `GET` | `/api/v1/{level}/{id}` | Get a single node |
| `PUT` | `/api/v1/{level}/{id}` | Update a node |
| `DELETE` | `/api/v1/{level}/{id}` | Soft-delete a node |

Supported `{level}` values: `nations`, `states`, `regions`, `groups`, `locations`, `fellowships`

---

### `GET /api/v1/hierarchy/tree`
Returns the full hierarchy as a nested tree structure.

**Response:**
```json
[
    {
        "id": "234",
        "name": "Nigeria",
        "type": "nation",
        "path": "org.234",
        "children": [
            {
                "id": "KW",
                "name": "Kwara",
                "type": "state",
                "path": "org.234.KW",
                "children": [...]
            }
        ]
    }
]
```

---

### `GET /api/v1/hierarchy/search`
Search hierarchy nodes by name or code.

**Query Params:**
| Param | Description |
|---|---|
| `q` | Search query (name match) |

---

### `GET /api/v1/locations/{location_id}/details`
Get a location with its full parent chain.

**Response:**
```json
{
    "location_id": "001",
    "location_name": "GRA DLBC",
    "church_type": "DLBC",
    "path": "org.234.KW.ILN.ILE.001",
    "group": { "group_name": "Ilorin East" },
    "region": { "region_name": "Ilorin North" },
    "state": { "state_name": "Kwara" },
    "nation": { "country_name": "Nigeria" },
    "fellowships": [...]
}
```

---

## 📅 Programs — `/api/v1/programs/`

Programs provide the metadata backbone for all data collection. A `ProgramEvent` is what ties a `Count`, `Offering`, or `WorkerAttendance` to a specific date and program type.

### Domains

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/programs/domains` | List all program domains |
| `POST` | `/api/v1/programs/domains` | Create a domain |
| `PUT` | `/api/v1/programs/domains/{id}` | Update a domain |
| `DELETE` | `/api/v1/programs/domains/{id}` | Delete a domain |

**Example Domain:**
```json
{ "id": 1, "slug": "regular_service", "name": "Regular Service" }
```

### Types

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/programs/types` | List types (filter by `?domain_id=`) |
| `POST` | `/api/v1/programs/types` | Create a type |
| `PUT` | `/api/v1/programs/types/{id}` | Update |
| `DELETE` | `/api/v1/programs/types/{id}` | Delete |

**Example Types:**
```json
[
    { "id": 1, "slug": "sunday_worship", "name": "Sunday Worship Service", "domain_id": 1 },
    { "id": 2, "slug": "monday_bible_study", "name": "Monday Bible Study", "domain_id": 1 },
    { "id": 3, "slug": "thursday_revival", "name": "Thursday Revival Hour", "domain_id": 1 }
]
```

### Events

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/programs/events` | List events (many filters) |
| `GET` | `/api/v1/programs/events/{event_id}` | Get a single event |
| `POST` | `/api/v1/programs/events` | Create an event |
| `PUT` | `/api/v1/programs/events/{event_id}` | Update |
| `DELETE` | `/api/v1/programs/events/{event_id}` | Soft-delete |

**Create Event Request:**
```json
{
    "program_type_id": 1,
    "date": "2026-03-10",
    "path": "org.234.KW.ILN.ILE.001",
    "title": "Sunday Service — 10 March 2026"
}
```

**Event Filters:**
| Param | Description |
|---|---|
| `program_type` | Filter by type ID |
| `program_domain` | Filter by domain ID |
| `title` | Title search |
| `location_id` | Specific location |
| `date` | Exact date |
| `start_month` / `end_month` | Month range |
| `start_year` / `end_year` | Year range |

---

## 📊 Counts — `/api/v1/counts/`

Attendance head counts (Adult Male/Female, Youth Male/Female, Boys/Girls).

**Required permission:** `counts:create` / `counts:read`

---

### `POST /api/v1/counts/`
Submit a new attendance count.

**Request:**
```json
{
    "event_id": "uuid-of-program-event",
    "location_id": "001",
    "adult_male": 124,
    "adult_female": 98,
    "youth_male": 45,
    "youth_female": 37,
    "boys": 22,
    "girls": 19,
    "note": "Regular Sunday service count"
}
```

**Response (201):**
```json
{
    "id": "uuid",
    "event_id": "uuid-of-program-event",
    "location_id": "001",
    "adult_male": 124,
    "adult_female": 98,
    "youth_male": 45,
    "youth_female": 37,
    "boys": 22,
    "girls": 19,
    "total": 345,
    "status": "pending",
    "path": "org.234.KW.ILN.ILE.001",
    "entered_by_id": "user-uuid",
    "created_at": "2026-03-10T09:15:00Z"
}
```

---

### `GET /api/v1/counts/`
List counts in scope (paginated).

**Query Params:** `skip`, `limit`, `scope_path`

---

### `GET /api/v1/counts/aggregate`
Get aggregated totals grouped by location.

**Query Params:**
| Param | Description |
|---|---|
| `program_domain` | Filter by domain slug |
| `program_type` | Filter by type slug |
| `location_id` | Specific location |
| `start_date` / `end_date` | Date range (`YYYY-MM-DD`) |

**Response:**
```json
[
    {
        "location_id": "001",
        "location_name": "GRA DLBC",
        "total_adult_male": 680,
        "total_adult_female": 520,
        "total_youth_male": 230,
        "total_youth_female": 190,
        "total_boys": 110,
        "total_girls": 105,
        "grand_total": 1835,
        "count_entries": 5
    }
]
```

---

### `GET /api/v1/counts/aggregate-flex`
Flexible aggregation grouped by any hierarchy level.

**Query Params:**
| Param | Values | Description |
|---|---|---|
| `view_level` | `state`, `region`, `group`, `location` | Grouping level |

**Response:** Same format as `/aggregate` but grouped at the requested level.

---

### `GET /api/v1/counts/stats`
Statistical summary for a period.

**Response:**
```json
{
    "total_entries": 47,
    "total_adults": 8240,
    "total_youth": 3150,
    "total_children": 1890,
    "grand_total": 13280,
    "avg_per_service": 282.5,
    "period": { "start": "2026-01-01", "end": "2026-03-10" }
}
```

---

### `POST /api/v1/counts/batch`
Submit multiple count records at once (for offline sync).

**Request:**
```json
[
    {
        "event_id": "uuid",
        "location_id": "001",
        "adult_male": 124,
        "client_id": "offline-generated-uuid"
    }
]
```

**Response:**
```json
{
    "synced": 3,
    "duplicates": 1,
    "errors": 0,
    "details": [
        { "client_id": "uuid", "status": "synced", "server_id": "uuid" },
        { "client_id": "uuid", "status": "duplicate" }
    ]
}
```

---

### `GET /api/v1/counts/{id}` — Get a single count
### `PUT /api/v1/counts/{id}` — Update a count
### `DELETE /api/v1/counts/{id}` — Soft-delete a count

---

## 💰 Offerings — `/api/v1/offerings/`

Tracks financial contributions (excluding tithes, which have their own endpoint).

**Required permission:** `offerings:create` / `offerings:read`

---

### `POST /api/v1/offerings/`
Record a new financial offering.

**Request:**
```json
{
    "event_id": "uuid-of-program-event",
    "location_id": "001",
    "amount": 87500.00,
    "payment_method": "cash",
    "fund_type": "offering",
    "note": "Regular Sunday offering"
}
```

**`payment_method` values:** `cash`, `bank_transfer`, `mobile_money`, `check`
**`fund_type` values:** `offering`, `tithe`, `seed`, `special`

**Response (201):**
```json
{
    "id": "uuid",
    "event_id": "uuid",
    "location_id": "001",
    "amount": 87500.00,
    "payment_method": "cash",
    "fund_type": "offering",
    "status": "pending",
    "path": "org.234.KW.ILN.ILE.001",
    "entered_by_id": "uuid",
    "created_at": "2026-03-10T09:15:00Z"
}
```

---

### `GET /api/v1/offerings/`
List offerings with optional filters.

**Query Params:** `fund_type`, `location_id`, `start_date`, `end_date`, `amount`, `skip`, `limit`

---

### `GET /api/v1/offerings/stats`
Aggregate financial stats for a period.

**Response:**
```json
{
    "count": 24,
    "total_amount": 2150000.00,
    "by_fund_type": {
        "offering": 1800000.00,
        "seed": 350000.00
    }
}
```

### `POST /api/v1/offerings/batch` — Bulk upload (offline sync)
### `GET /api/v1/offerings/{id}` / `PUT /api/v1/offerings/{id}` / `DELETE /api/v1/offerings/{id}`

---

## 🧾 Tithes — `/api/v1/tithes/`

Mirrors the offerings endpoints exactly, but with fixed `fund_type = "tithe"`. All the same query params and response shapes apply.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/tithes/` | Record a tithe |
| `GET` | `/api/v1/tithes/` | List tithes |
| `GET` | `/api/v1/tithes/stats` | Aggregate stats |
| `POST` | `/api/v1/tithes/batch` | Batch sync |
| `GET/PUT/DELETE` | `/api/v1/tithes/{id}` | Single record |

---

## 🪑 Worker Attendance — `/api/v1/attendance/`

Tracks per-worker attendance at programs.

---

### `POST /api/v1/attendance/`
Record attendance for one worker at one event.

**Request:**
```json
{
    "event_id": "uuid-of-program-event",
    "location_id": "001",
    "worker_id": "worker-uuid",
    "status": "present",
    "reason": null,
    "note": null
}
```

**`status` values:** `present`, `absent`, `late`, `excused`

---

### `GET /api/v1/attendance/workers`
Get list of workers for attendance marking at a location.

**Query Params:** `location_id`, `scope_path`

---

### `GET /api/v1/attendance/stats`
Statistics for worker attendance.

**Response:**
```json
{
    "count": 120,
    "present": 98,
    "absent": 15,
    "late": 5,
    "excused": 2,
    "attendance_rate": "81.67%"
}
```

### `POST /api/v1/attendance/batch` — Bulk upload
### `GET/PUT/DELETE /api/v1/attendance/{id}` — Single record

---

## 👋 Newcomers & Converts — `/api/v1/records/`, `/api/v1/newcomers/`, `/api/v1/converts/`

All three endpoint groups share the same schema. `/newcomers/` and `/converts/` automatically set `record_type` for you.

---

### `POST /api/v1/records/`
Register a newcomer or convert.

**Request:**
```json
{
    "event_id": "uuid",
    "location_id": "001",
    "record_type": "newcomer",
    "name": "Blessing Ihejirika",
    "gender": "Female",
    "phone": "+2347012345678",
    "details": {
        "email": "blessing@example.com",
        "address": "5 Unity Road, Ilorin",
        "occupation": "Nurse",
        "marital_status": "Single",
        "invited_by": "Adebayo Oluwaseun",
        "social_group": "working_class"
    }
}
```

For converts, add to `details`:
```json
{
    "salvation_type": "first_time",
    "status_address": "University area"
}
```

---

### `GET /api/v1/records/`
List records with optional filters.

**Query Params:** `record_type` (`newcomer` or `convert`), `scope_path`, `skip`, `limit`

---

### `PATCH /api/v1/records/{id}/follow-up`
Update the follow-up status of a newcomer/convert record.

**Request:**
```json
{ "status": "contacted", "note": "Called and spoke with them. Will attend next Sunday." }
```

**`status` values:** `pending`, `contacted`, `followed_up`

---

## 🏠 Fellowship Activities — `/api/v1/fellowships/`

Full CRUD for all house fellowship operations.

### Members

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/fellowships/members` | Add a fellowship member |
| `GET` | `/api/v1/fellowships/members` | List members (filter by `fellowship_id`) |
| `PUT` | `/api/v1/fellowships/members/{id}` | Update member details |
| `DELETE` | `/api/v1/fellowships/members/{id}` | Remove member |

**Member Create Request:**
```json
{
    "fellowship_id": "F001",
    "name": "Grace Adesola",
    "phone": "+2348099887766",
    "gender": "Female",
    "address": "12 Chapel Close",
    "role": "member"
}
```

### Attendance

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/fellowships/attendance` | Record weekly attendance |
| `GET` | `/api/v1/fellowships/attendance` | List attendance records |
| `PUT` | `/api/v1/fellowships/attendance/{id}` | Update |
| `DELETE` | `/api/v1/fellowships/attendance/{id}` | Delete |

**Attendance Create Request:**
```json
{
    "fellowship_id": "F001",
    "date": "2026-03-10T18:00:00Z",
    "men": 8,
    "women": 12,
    "youths": 4,
    "children": 3,
    "total": 27,
    "topic": "The Power of Prayer (Matthew 7:7-8)"
}
```

### Offerings
Same pattern — `POST /api/v1/fellowships/offerings` with `fellowship_id`, `date`, `amount`.

### Testimonies
`POST /api/v1/fellowships/testimonies` with `fellowship_id`, `date`, `testifier_name`, `content`.

### Prayer Requests
`POST /api/v1/fellowships/prayer-requests` — includes `status` field (`pending`, `prayed`, `answered`).
`PATCH /api/v1/fellowships/prayer-requests/{id}` — update status only.

### Attendance Summaries
`POST /api/v1/fellowships/attendance-summaries` — monthly aggregated summary per fellowship.

---

## 📢 Announcements — `/api/v1/announcements/`

Regional weekly announcements. **Required role score:** Level 5 (Regional Pastor) or above.

---

### `POST /api/v1/announcements/`
Create a new weekly announcement.

**Request:**
```json
{
    "region_id": "ILN",
    "region_name": "Ilorin North",
    "date": "2026-03-15",
    "meeting": "Tuesday Leadership Meeting",
    "sws_topic": "Walking in the Spirit",
    "sws_bible_reading": "Romans 8:1-14",
    "mbs_bible_reading": "Psalm 119:1-16",
    "trets_topic": "Evangelism Strategy Workshop",
    "trets_date": "2026-03-20",
    "sts_study": "The Book of Romans — Chapter 5",
    "adult_hcf_lesson": "Faith That Works",
    "adult_hcf_volume": "Vol 14, No 2",
    "youth_hcf_lesson": "Standing Firm in Faith",
    "youth_hcf_volume": "Vol 8, No 2",
    "children_hcf_lesson": "God's Promises",
    "children_hcf_volume": "Vol 5, No 2",
    "items": [
        { "title": "Special Notice", "text": "Zone-wide prayer vigil on Saturday, 8pm–10pm" },
        { "title": "Congratulations", "text": "To Bro. Emmanuel Okafor on his new appointment" }
    ]
}
```

**Field Reference:**
| Field | Full Name | Description |
|---|---|---|
| `sws_topic` / `sws_bible_reading` | Sunday Worship Service | — |
| `mbs_bible_reading` | Monday Bible Study | — |
| `trets_topic` / `trets_date` | TRETS (Thursday Revival & Evangelism Training) | — |
| `sts_study` | School of Theology & Scripture | — |
| `adult/youth/children_hcf_lesson` | Home Caring Fellowship | Lesson title + volume number |
| `items` | Extra announcement items | Dynamic list |

---

### `GET /api/v1/announcements/`
List announcements.

**Query Params:** `region_id`, `date`, `is_active`

---

### `POST /api/v1/announcements/{id}/deactivate`
Mark an announcement as inactive (takes it off public display).

---

### `GET/PUT/DELETE /api/v1/announcements/{id}` — Single record

---

## ✅ Approvals & Workflows — `/api/v1/approvals/`

Three distinct approval workflows live here.

---

### Transfer Requests

#### `POST /api/v1/approvals/transfers`
Request a worker's transfer to a different location.

**Request:**
```json
{
    "worker_id": "uuid",
    "to_location_id": "002",
    "reason": "Worker has moved residence to GRA area."
}
```

#### `GET /api/v1/approvals/transfers`
List transfer requests in scope.

**Query Params:** `status` (`pending`, `approved`, `rejected`), `skip`, `limit`

#### `POST /api/v1/approvals/transfers/{request_id}/approve`
Approve a transfer. The worker's `location_id` and `path` are updated automatically.

#### `POST /api/v1/approvals/transfers/{request_id}/reject`
Reject with optional reason query param.

---

### Status Change Requests

#### `POST /api/v1/approvals/status-changes`
Request a worker's status to be changed.

**Request:**
```json
{
    "worker_id": "uuid",
    "new_status": "Suspended",
    "reason": "Worker has been inactive for 3+ months despite multiple contacts."
}
```

**Status values:** `Active`, `Inactive`, `Suspended`

#### `GET /api/v1/approvals/status-changes`
List in scope with optional `?status=` filter.

#### `POST /api/v1/approvals/status-changes/{request_id}/approve`
Approve — updates worker's `status` field.

#### `POST /api/v1/approvals/status-changes/{request_id}/reject`

---

### Worker Removal Requests (Escalation Workflow)

This is the most complex workflow. A removal request starts at Level 3 (Location Pastor) and travels up to Level 6 (State Overseer) if escalated.

**Escalation flow:**
```
Level 3 (Location Pastor) → submits request
    Level 4 (Group Pastor) → APPROVE (soft-deletes worker) | REJECT | ESCALATE to Level 5
        Level 5 (Regional Pastor) → APPROVE | REJECT | ESCALATE to Level 6
            Level 6 (State Overseer) → APPROVE | REJECT (final)
```

Every action (escalation or final decision) is recorded in the `reviews` JSONB array with timestamp, actor, and notes.

#### `POST /api/v1/approvals/removals`
Submit a removal request (Level 3 Pastor only).

**Request:**
```json
{
    "worker_id": "uuid",
    "reason": "Worker Emmanuel Okafor has relocated to Lagos and has not attended or communicated in over 6 months despite multiple attempts at contact."
}
```

**Note:** Reason must be at least **20 characters**.

#### `GET /api/v1/approvals/removals`
List removal requests.

**Query Params:** `status` (`pending`, `approved`, `rejected`, `escalated`), `current_level` (3, 4, 5, or 6), `skip`, `limit`

**Response includes:**
```json
{
    "id": "uuid",
    "worker_id": "uuid",
    "status": "escalated",
    "current_level": 5,
    "reason": "Worker has relocated...",
    "reviews": [
        {
            "level": 4,
            "reviewer_id": "uuid",
            "action": "escalate",
            "notes": "Cannot confirm locally. Escalating to region for final decision.",
            "at": "2026-03-12T10:30:00Z"
        }
    ],
    "requested_by": "uuid"
}
```

#### `POST /api/v1/approvals/removals/{request_id}/approve`
Approve — soft-deletes the worker.

**Request:**
```json
{ "notes": "Confirmed removal after investigation." }
```

#### `POST /api/v1/approvals/removals/{request_id}/reject`
Reject the request.

**Request:**
```json
{ "notes": "Worker has been contacted and will resume attendance." }
```

#### `POST /api/v1/approvals/removals/{request_id}/escalate`
Escalate to the next level. Notes are **required** (minimum 10 characters).

**Request:**
```json
{ "notes": "Requires oversight from regional level given the circumstances." }
```

---

## 📈 Reports — `/api/v1/reports/`

Analytics and exportable reports. **Required role score:** Level 6+

---

| Endpoint | Description |
|---|---|
| `GET /api/v1/reports/summary` | Summary stats (attendance, offerings, workers) for a scope and period |
| `GET /api/v1/reports/financial` | Financial breakdown by fund type and period |
| `GET /api/v1/reports/attendance` | Worker attendance report with period and scope filters |
| `GET /api/v1/reports/timeseries` | Trend data; params: `metric` (attendance/offerings), `interval` (daily/weekly/monthly) |
| `GET /api/v1/reports/by-level` | Stats grouped by hierarchy level; params: `metric`, `level` (state/region/group/location) |
| `GET /api/v1/reports/anomalies` | Detect unusually high or low entries compared to historical average |
| `GET /api/v1/reports/growth-rate` | Month-over-month percentage changes |
| `GET /api/v1/reports/export/csv` | Download CSV export; param: `report_type` |
| `POST /api/v1/reports/export/excel` | Download Excel export |
| `POST /api/v1/reports/export/pdf` | Download PDF export |
| `POST /api/v1/reports/refresh` | Force refresh of materialized analytics views |

**Common query params for report endpoints:**
`scope_path`, `start_date`, `end_date`, `start_month`, `end_month`, `start_year`, `end_year`, `program_type`, `location_id`

---

## 🔑 RBAC — `/api/v1/rbac/`

Manage roles, permissions, and role score levels. **Required role score:** Level 9 (System Admin) for destructive operations.

| Endpoint | Description |
|---|---|
| `GET /api/v1/rbac/permissions` | List all permissions |
| `POST /api/v1/rbac/permissions` | Create a permission |
| `PUT /api/v1/rbac/permissions/{id}` | Update |
| `DELETE /api/v1/rbac/permissions/{id}` | Delete |
| `GET /api/v1/rbac/roles` | List all roles |
| `GET /api/v1/rbac/roles/available` | Roles assignable by current user (score < own score) |
| `POST /api/v1/rbac/roles` | Create a role |
| `PUT /api/v1/rbac/roles/{id}` | Update |
| `DELETE /api/v1/rbac/roles/{id}` | Delete |
| `POST /api/v1/rbac/roles/{id}/permissions` | Assign permissions to a role |
| `DELETE /api/v1/rbac/roles/{id}/permissions` | Remove permissions from a role |
| `GET /api/v1/rbac/role-scores` | List all role scores |
| `POST /api/v1/rbac/role-scores` | Create a role score level |

---

## 🔄 Offline Sync — `/api/v1/sync/`

Used by mobile apps to synchronize offline data when connectivity is restored.

### `POST /api/v1/sync/batch`
Upload multiple records of mixed types in a single request.

**Request:**
```json
{
    "counts": [...],
    "offerings": [...],
    "records": [...],
    "attendance": [...]
}
```

**Response:**
```json
{
    "counts": { "synced": 3, "duplicates": 1, "errors": 0 },
    "offerings": { "synced": 2, "duplicates": 0, "errors": 0 },
    ...
}
```

---

### `GET /api/v1/sync/changes`
Fetch changes since a given timestamp (for incremental sync).

**Query Params:** `since=2026-03-01T00:00:00Z`

---

### `GET /api/v1/sync/conflicts`
List records that have sync conflicts (client version vs server version).

### `POST /api/v1/sync/resolve`
Resolve a sync conflict.

**Request:**
```json
{ "conflict_id": "uuid", "resolution": "use_server" }
```

**`resolution` values:** `use_server`, `use_client`, `merge`

---

## 🖼️ Media — `/api/v1/media/`

### Galleries

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/media/galleries` | Create a gallery |
| `GET` | `/api/v1/media/galleries` | List galleries |
| `GET` | `/api/v1/media/galleries/{id}` | Get gallery with items |
| `DELETE` | `/api/v1/media/galleries/{id}` | Delete gallery |

### Items

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/media/items` | Add a media item to a gallery |
| `GET` | `/api/v1/media/items` | List items (filter by `gallery_id`) |
| `GET` | `/api/v1/media/items/{id}` | Get single item |
| `DELETE` | `/api/v1/media/items/{id}` | Remove item |

---

## 🌐 Public Endpoints — `/api/v1/public/`

**No authentication required.** These endpoints power the public-facing church website.

| Endpoint | Description |
|---|---|
| `GET /api/v1/public/events` | List upcoming church events |
| `GET /api/v1/public/events/{id}` | Get event details |
| `GET /api/v1/public/locations` | List all church branches |
| `GET /api/v1/public/locations/nearby` | Find nearby branches (requires `lat` & `lng` query params) |
| `GET /api/v1/public/galleries` | List public media galleries |
| `GET /api/v1/public/galleries/{id}` | Gallery with all images |
| `GET /api/v1/public/announcements` | Public announcements |
| `POST /api/v1/public/workers/register` | Public worker self-registration form |
| `POST /api/v1/public/contact` | Contact form submission |
| `POST /api/v1/public/prayer-request` | Public prayer request submission |
| `GET /api/v1/public/app-version` | Current mobile app version info |
| `GET /api/v1/public/app-versions` | All app versions (all platforms) |

---

## 🔔 Notifications — `/api/v1/notifications/`

### `GET /api/v1/notifications/poll`
Returns pending items the current user needs to act on (for notification badge count).

**Response:**
```json
{
    "pending_worker_registrations": 2,
    "pending_user_approvals": 1,
    "pending_removal_requests": 1,
    "total": 4
}
```

---

## 🔐 Password Recovery — `/api/v1/recovery/`

Password recovery using security questions (no email required).

| Endpoint | Description |
|---|---|
| `POST /api/v1/recovery/request-reset` | Initiate password reset by phone number |
| `POST /api/v1/recovery/verify-token` | Verify security question answers |
| `POST /api/v1/recovery/reset-password` | Set new password with valid reset token |
| `POST /api/v1/recovery/set-recovery-question` | Set security questions for account |
| `GET /api/v1/recovery/read-recovery-question` | Get current security question text (for display) |
| `PATCH /api/v1/recovery/update-recovery-question` | Update security questions |

---

## 🖥️ System — `/api/v1/system/`

System administration endpoints. **High score required.**

| Endpoint | Description |
|---|---|
| `GET /api/v1/system/meta` | System metadata (app name, version, environment) |
| `GET /api/v1/system/metrics` | Runtime metrics (request counts, DB pool status) |
| `POST /api/v1/system/seed` | Trigger RBAC seed (populate roles, permissions, role scores) |

---

## 📡 WebSocket — `/api/v1/ws`

Real-time updates for the admin dashboard.

**Connect:**
```
ws://server:8000/api/v1/ws?token=<access_token>
```

**Events received:**
```json
{ "event": "new_count_submitted", "data": { "location": "GRA DLBC", "total": 345 } }
{ "event": "new_worker_registered", "data": { "name": "Emmanuel Okafor" } }
{ "event": "approval_needed", "data": { "type": "user_account", "count": 2 } }
```

---

## 📊 Statistics — `/api/v1/statistics/`

| Endpoint | Description |
|---|---|
| `GET /api/v1/statistics/read-population/` | Population count stats in scope |
| `GET /api/v1/statistics/church-statistics/` | Overall church growth statistics |
| `GET /api/v1/statistics/get-user-statistics/` | User and worker stats in scope |

---

## 📱 App Version — `/api/v1/app-version/`

| Endpoint | Description |
|---|---|
| `GET /api/v1/app-version/` | List all app versions |
| `POST /api/v1/app-version/` | Create a new version entry |
| `PUT /api/v1/app-version/{id}` | Update version info |
| `PATCH /api/v1/app-version/{id}/set-current` | Mark as the current/latest version |
| `DELETE /api/v1/app-version/{id}` | Delete version entry |
