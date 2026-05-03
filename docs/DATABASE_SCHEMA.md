# Database Schema

## Overview

The database is **PostgreSQL 16** with the `ltree` extension enabled. All models use **UUID primary keys** (except a few reference tables that use auto-increment integers). All major tables include soft-delete (`is_deleted`) and full timestamps (`created_at`, `updated_at`).

---

## Core Design Principles

| Principle | Implementation |
|---|---|
| Hierarchical data | `ltree` path columns with GIST indexing on every major table |
| Soft deletes | `is_deleted BOOLEAN DEFAULT FALSE` on all data tables |
| Audit trail | `created_at`, `updated_at` on all tables; `entered_by_id` FK on data tables |
| Idempotent sync | `client_id UUID` on data tables submitted from mobile apps |
| Flexible metadata | `JSONB` columns for sparse/flexible data (newcomer details, review audits) |
| No circular FKs | `User` references `Worker`, never the other way around |

---

## Table Reference

### 👤 User & Authentication Tables

#### `workers`
Primary registry of all church workers. A worker record MUST exist before a user account can be created.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | Internal auto-increment ID |
| `worker_id` | UUID UNIQUE | External worker UUID |
| `user_id` | VARCHAR UNIQUE | Human-readable ID (e.g., `W-001`) |
| `location_id` | VARCHAR FK → locations | Required, cannot be null |
| `location_name` | VARCHAR | Denormalized for quick access |
| `church_type` | VARCHAR | `DLBC`, `DLCF`, or `DLSO` |
| `state` | VARCHAR | Denormalized state name |
| `region` | VARCHAR | Denormalized region name |
| `group` | VARCHAR | Denormalized group name |
| `name` | VARCHAR | Full name |
| `gender` | VARCHAR | `Male` or `Female` |
| `phone` | VARCHAR UNIQUE | Phone number (required) |
| `email` | VARCHAR UNIQUE | Email address (required) |
| `address` | VARCHAR | Physical address (optional) |
| `occupation` | VARCHAR | Occupation (optional) |
| `marital_status` | VARCHAR | `Single`, `Married`, `Widowed`, `Divorced` |
| `unit` | VARCHAR | Serving unit (Ushering, Choir, etc.) |
| `status` | VARCHAR | `Active`, `Inactive`, or `Suspended` |
| `approval_status` | VARCHAR | `approved`, `pending_verification`, or `rejected` |
| `approved_by` | UUID FK → users | Admin who approved |
| `approved_at` | TIMESTAMPTZ | When approved |
| `rejection_reason` | VARCHAR | If rejected, the reason |
| `path` | LTREE | Hierarchical path (from location) |
| `is_deleted` | BOOLEAN | Soft delete flag |
| `created_at` / `updated_at` | TIMESTAMPTZ | Audit timestamps |

#### `users`
Application authentication accounts — linked 1:1 to workers.

| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID PK | Matches `sub` claim in JWT |
| `worker_id` | UUID FK → workers UNIQUE | Worker this user represents |
| `password` | VARCHAR | bcrypt-hashed password |
| `is_active` | BOOLEAN | If false, login is denied |
| `approval_status` | VARCHAR | `pending`, `approved`, or `rejected` |
| `approved_by` | UUID FK → users | Self-referential |
| `approved_at` | TIMESTAMPTZ | — |
| `rejection_reason` | VARCHAR | — |
| `recovery_question_one/two` | VARCHAR | Security questions |
| `recovery_answer_one/two` | VARCHAR | Hashed answers |
| `location_id` | VARCHAR | Denormalized from worker |
| `name` | VARCHAR | Denormalized from worker |
| `phone` | VARCHAR UNIQUE | Denormalized from worker |
| `email` | VARCHAR UNIQUE | — |
| `path` | LTREE | Inherited from worker |
| `is_deleted` | BOOLEAN | Soft delete |

#### `roles`

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | — |
| `role_name` | VARCHAR UNIQUE | e.g., `GroupPastor`, `LocationUsher` |
| `description` | VARCHAR | Human-readable description |
| `score_id` | INT FK → role_scores | Links to the access level |

#### `role_scores`

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | — |
| `score` | INT UNIQUE | 1–9 (9 = highest) |
| `score_name` | VARCHAR | e.g., `"Group Level"` |
| `description` | VARCHAR | — |

#### `permissions`

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | — |
| `permission` | VARCHAR UNIQUE | Format: `resource:action` e.g., `counts:create` |
| `name` | VARCHAR | Human-readable name |
| `description` | VARCHAR | — |

#### `role_permissions` (junction)
Many-to-many between `roles` and `permissions`.

#### `user_roles` (junction)
Many-to-many between `users` and `roles`.

#### `password_reset_tokens`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | — |
| `user_id` | UUID FK → users | — |
| `token` | VARCHAR UNIQUE | Secure reset token |
| `expiration` | INT | Unix timestamp for expiry |
| `is_used` | BOOLEAN | Token consumed flag |

---

### 🏛️ Hierarchy Tables

All hierarchy tables share a common `path` (ltree) column used for hierarchical queries.

#### `nations`
| Column | Type | Notes |
|---|---|---|
| `nation_id` | VARCHAR PK | e.g., `"234"` for Nigeria |
| `continent` | VARCHAR | e.g., `"Africa"` |
| `country_name` | VARCHAR | `"Nigeria"` |
| `capital` | VARCHAR | Optional |
| `national_pastor` | VARCHAR | Optional |
| `church_hq` | VARCHAR | Optional |
| `path` | LTREE | e.g., `org.234` |

#### `states`
| Column | Type | Notes |
|---|---|---|
| `state_id` | VARCHAR PK | e.g., `"KW"` |
| `nation_id` | VARCHAR FK → nations | — |
| `state_name` | VARCHAR | e.g., `"Kwara"` |
| `state_pastor` | VARCHAR | Optional |
| `path` | LTREE | e.g., `org.234.KW` |

#### `regions`
| Column | Type | Notes |
|---|---|---|
| `region_id` | VARCHAR PK | e.g., `"ILN"` |
| `state_id` | VARCHAR FK → states | — |
| `region_name` | VARCHAR | e.g., `"Ilorin North"` |
| `regional_pastor` / `region_head` | VARCHAR | Optional |
| `path` | LTREE | e.g., `org.234.KW.ILN` |

#### `dclm_groups`
| Column | Type | Notes |
|---|---|---|
| `group_id` | VARCHAR PK | e.g., `"ILE"` |
| `region_id` | VARCHAR FK → regions | — |
| `group_name` | VARCHAR | e.g., `"Ilorin East"` |
| `group_pastor` / `group_head` | VARCHAR | Optional |
| `path` | LTREE | e.g., `org.234.KW.ILN.ILE` |

#### `locations`
| Column | Type | Notes |
|---|---|---|
| `location_id` | VARCHAR PK | e.g., `"001"` |
| `group_id` | VARCHAR FK → dclm_groups | — |
| `location_name` | VARCHAR | e.g., `"GRA DLBC"` |
| `church_type` | VARCHAR | `DLBC`, `DLCF`, or `DLSO` |
| `address` | VARCHAR | Physical address |
| `latitude` / `longitude` | FLOAT | GPS coordinates (optional) |
| `associate_cord` | VARCHAR | Coordinates string (optional) |
| `path` | LTREE | e.g., `org.234.KW.ILN.ILE.001` |

#### `fellowships`
| Column | Type | Notes |
|---|---|---|
| `fellowship_id` | VARCHAR PK | e.g., `"F001"` |
| `location_id` | VARCHAR FK → locations | — |
| `fellowship_name` | VARCHAR | — |
| `fellowship_address` | VARCHAR | Physical address |
| `leader_in_charge` | VARCHAR | Leader name |
| `leader_contact` | VARCHAR | Phone number |
| `path` | LTREE | e.g., `org.234.KW.ILN.ILE.001.F001` |

---

### 📅 Program Tables

#### `program_domains`
Top-level program category (e.g., Regular Service, Retreat, Crusade).

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | — |
| `slug` | VARCHAR UNIQUE | e.g., `regular_service` |
| `name` | VARCHAR UNIQUE | e.g., `"Regular Service"` |
| `description` | VARCHAR | Optional |

#### `program_types`
Specific service type within a domain.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | — |
| `domain_id` | INT FK → program_domains | — |
| `slug` | VARCHAR UNIQUE | e.g., `sunday_worship` |
| `name` | VARCHAR | e.g., `"Sunday Worship Service"` |

#### `program_events`
A specific scheduled instance of a program type at a particular scope/date.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `program_type_id` | INT FK → program_types | — |
| `path` | LTREE | Scope of the event (location, group, region, etc.) |
| `date` | DATE | The event date |
| `title` | VARCHAR | Optional title override |

> All `Count`, `Offering`, and `WorkerAttendance` records link to a `ProgramEvent` via `event_id`. This is the "source of truth" for date and program context.

---

### 📊 Data Collection Tables

#### `counts`
Attendance head counts per demographic for a specific event.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `client_id` | UUID | Offline sync deduplication |
| `path` | LTREE | Scope |
| `location_id` | VARCHAR | — |
| `event_id` | UUID FK → program_events | — |
| `adult_male` | INT | — |
| `adult_female` | INT | — |
| `youth_male` | INT | — |
| `youth_female` | INT | — |
| `boys` | INT | — |
| `girls` | INT | — |
| `total` | INT | Auto-calculated sum |
| `status` | VARCHAR | `pending`, `approved`, `rejected` |
| `note` | TEXT | Optional notes |
| `entered_by_id` | UUID FK → users | — |

#### `offerings`
Financial contributions (general offerings, seeds, special).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `client_id` | UUID | — |
| `path` | LTREE | — |
| `location_id` | VARCHAR | — |
| `event_id` | UUID FK → program_events | Required |
| `date` | TIMESTAMPTZ | — |
| `amount` | NUMERIC(12,2) | Up to ₦999,999,999.99 |
| `payment_method` | VARCHAR | `cash`, `bank_transfer`, `mobile_money`, `check` |
| `fund_type` | VARCHAR | `offering`, `tithe`, `seed`, `special` |
| `status` | VARCHAR | `pending`, `approved`, `rejected` |
| `note` | TEXT | — |
| `entered_by_id` | UUID FK → users | — |

#### `worker_attendance`
Per-worker attendance at programs.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `client_id` | UUID | — |
| `path` | LTREE | — |
| `location_id` | VARCHAR | — |
| `event_id` | UUID FK → program_events | — |
| `worker_id` | UUID FK → workers | — |
| `worker_name` | VARCHAR | Denormalized snapshot |
| `worker_phone` | VARCHAR | Denormalized snapshot |
| `worker_unit` | VARCHAR | Denormalized snapshot |
| `status` | VARCHAR | `present`, `absent`, `late`, `excused` |
| `reason` | TEXT | Reason if absent/excused |
| `note` | TEXT | — |
| `entered_by_id` | UUID FK → users | — |

#### `records`
Newcomer and convert registration records.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `client_id` | UUID | — |
| `path` | LTREE | — |
| `location_id` | VARCHAR | — |
| `event_id` | UUID FK → program_events | — |
| `record_type` | VARCHAR | `newcomer` or `convert` |
| `name` | VARCHAR | Required |
| `gender` | VARCHAR | `Male` or `Female` |
| `phone` | VARCHAR | Required |
| `details` | JSONB | Optional: email, address, occupation, invited_by, marital_status, salvation_type, etc. |
| `status` | VARCHAR | `pending`, `contacted`, `followed_up` |
| `note` | TEXT | — |
| `entered_by_id` | UUID FK → users | — |

---

### 🏠 Fellowship Activity Tables

#### `fellowship_members`
Persistent member registry for a specific house fellowship.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `fellowship_id` | VARCHAR FK → fellowships | — |
| `path` | LTREE | — |
| `name` | VARCHAR | — |
| `phone` | VARCHAR | Optional |
| `gender` | VARCHAR | — |
| `address` | VARCHAR | — |
| `role` | VARCHAR | `member`, `leader`, or `assistant` |
| `is_active` | BOOLEAN | — |

#### `fellowship_attendance`
Weekly head count at a fellowship meeting.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `fellowship_id` | VARCHAR FK → fellowships | — |
| `date` | DATETIME | Meeting date |
| `men` | INT | — |
| `women` | INT | — |
| `youths` | INT | — |
| `children` | INT | — |
| `total` | INT | — |
| `topic` | VARCHAR | Bible study topic |
| `entered_by_id` | UUID FK → users | — |

#### `fellowship_offerings`
Offering collected at a fellowship meeting (aggregate amount).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `fellowship_id` | VARCHAR FK → fellowships | — |
| `date` | DATETIME | — |
| `amount` | NUMERIC(12,2) | — |
| `entered_by_id` | UUID FK → users | — |

#### `fellowship_testimony`
Testimonies shared at fellowship meetings.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `fellowship_id` | VARCHAR FK → fellowships | — |
| `date` | DATETIME | — |
| `testifier_name` | VARCHAR | Optional |
| `content` | TEXT | Required |
| `note` | TEXT | Admin notes |
| `entered_by_id` | UUID FK → users | — |

#### `fellowship_prayer_request`
Prayer requests from fellowship meetings.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `fellowship_id` | VARCHAR FK → fellowships | — |
| `date` | DATETIME | — |
| `requestor_name` | VARCHAR | Optional |
| `content` | TEXT | Required |
| `status` | VARCHAR | `pending`, `prayed`, or `answered` |
| `entered_by_id` | UUID FK → users | — |

#### `fellowship_attendance_summaries`
Monthly aggregated summaries for a fellowship.

| Column | Type | Notes |
|---|---|---|
| `fellowship_id` | VARCHAR FK → fellowships | — |
| `month` | INT | 1–12 |
| `year` | INT | — |
| `total_meetings` | INT | — |
| `avg_attendance` | INT | — |
| `total_offering` | NUMERIC(12,2) | — |

---

### 📢 Announcement Tables

#### `announcements`
Weekly regional announcements with DCLM program structure.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `region_id` | VARCHAR | The publishing region |
| `region_name` | VARCHAR | — |
| `meeting` | VARCHAR | e.g., `"Tuesday Leadership"` |
| `date` | DATE | Publication date |
| `trets_topic` | VARCHAR | TRETS program topic |
| `trets_date` | DATE | TRETS date |
| `sws_topic` | VARCHAR | Sunday Worship Service topic |
| `sws_bible_reading` | VARCHAR | SWS Bible reading |
| `mbs_bible_reading` | VARCHAR | Monday Bible Study reading |
| `sts_study` | VARCHAR | School of Theology study |
| `adult_hcf_lesson` | VARCHAR | Adult HCF lesson title |
| `adult_hcf_volume` | VARCHAR | Adult HCF volume/issue |
| `youth_hcf_lesson` | VARCHAR | Youth HCF lesson |
| `youth_hcf_volume` | VARCHAR | Youth HCF volume |
| `children_hcf_lesson` | VARCHAR | Children's HCF lesson |
| `children_hcf_volume` | VARCHAR | Children's HCF volume |
| `is_active` | BOOLEAN | Published state |
| `published_at` | TIMESTAMPTZ | When published |
| `path` | LTREE | Region scope |

#### `announcement_items`
Additional custom announcement items attached to an announcement.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | — |
| `announcement_id` | UUID FK → announcements | Cascade delete |
| `title` | VARCHAR | — |
| `text` | TEXT | — |

---

### ✅ Approval Workflow Tables

#### `transfer_requests`
Worker transfer requests between locations.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `worker_id` | UUID FK → workers | — |
| `from_location_id` | VARCHAR | — |
| `to_location_id` | VARCHAR | — |
| `status` | VARCHAR | `pending`, `approved`, `rejected` |
| `reason` | VARCHAR | — |
| `requested_by` | UUID FK → users | — |
| `approved_by` | UUID FK → users | — |
| `approved_at` | TIMESTAMPTZ | — |
| `path` | LTREE | Scope |

#### `status_change_requests`
Worker status change requests (Active ↔ Inactive ↔ Suspended).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `worker_id` | UUID FK → workers | — |
| `old_status` | VARCHAR | — |
| `new_status` | VARCHAR | — |
| `status` | VARCHAR | `pending`, `approved`, `rejected` |
| `reason` | VARCHAR | — |
| `requested_by` | UUID FK → users | — |
| `approved_by` | UUID FK → users | — |
| `path` | LTREE | — |

#### `worker_removal_requests`
Multi-level escalating removal requests (Level 3 → 4 → 5 → 6).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `worker_id` | UUID FK → workers | — |
| `status` | VARCHAR | `pending`, `approved`, `rejected`, `escalated` |
| `current_level` | INT | Current governance level holding the request (3–6) |
| `reason` | TEXT | Required (min 20 chars) — initial reason |
| `reviews` | JSONB | Array of reviewer actions with timestamps, notes, level |
| `requested_by` | UUID FK → users | Level 3 submitter |
| `decided_by` | UUID FK → users | Final decision-maker |
| `decided_at` | TIMESTAMPTZ | — |
| `escalated_by` | UUID FK → users | Who escalated |
| `escalated_at` | TIMESTAMPTZ | — |
| `escalation_notes` | TEXT | Notes from the escalating pastor |
| `path` | LTREE | — |

---

### 🎬 Media Tables

#### `media_galleries`
Event photo/video collections.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `title` | VARCHAR | — |
| `description` | TEXT | — |
| `path` | LTREE | Scope |
| `event_id` | UUID FK → program_events | Optional link |

#### `media_items`
Individual media files (metadata only — files stored in Supabase Storage).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `gallery_id` | UUID FK → media_galleries | — |
| `url` | VARCHAR | Storage URL |
| `media_type` | VARCHAR | `photo` or `video` |
| `caption` | VARCHAR | Optional |

---

### 📱 System Tables

#### `app_versions`
Mobile app version management.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `platform` | VARCHAR | `android`, `ios`, `web` |
| `version_number` | VARCHAR | e.g., `"1.2.3"` |
| `release_notes` | TEXT | — |
| `download_url` | VARCHAR | — |
| `is_current` | BOOLEAN | — |
| `released_at` | TIMESTAMPTZ | — |

---

## Key Relationships Diagram

```
nations
  └── states
       └── regions
            └── dclm_groups
                 └── locations
                      ├── fellowships
                      │    ├── fellowship_members
                      │    ├── fellowship_attendance
                      │    ├── fellowship_offerings
                      │    ├── fellowship_testimony
                      │    └── fellowship_prayer_request
                      └── workers
                           └── users
                                ├── user_roles → roles → permissions
                                └── (enters) → counts, offerings, records, etc.

program_domains → program_types → program_events
                                       ├── counts (event_id)
                                       ├── offerings (event_id)
                                       └── worker_attendance (event_id)
```
