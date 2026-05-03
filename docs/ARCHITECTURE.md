# System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DCLM Church Management System                │
├──────────────┬──────────────────────────┬───────────────────────┤
│  Mobile App  │   Fellowship Leaders App │  Admin Web Dashboard  │
│  (Ushers)    │   (House Fellowships)    │  (Pastors & Admins)   │
│  Level 1-2   │   Level 2                │  Level 3-9            │
└──────┬───────┴──────────────┬───────────┴──────────┬────────────┘
       │                      │                       │
       └──────────────────────┼───────────────────────┘
                              │   REST API (HTTPS)
                              ▼
              ┌───────────────────────────────┐
              │     FastAPI Backend Server     │
              │   - 30 route modules           │
              │   - JWT Auth middleware         │
              │   - PermissionChecker deps     │
              │   - Async SQLAlchemy ORM       │
              └──────────────┬────────────────┘
                             │
              ┌──────────────▼────────────────┐
              │      PostgreSQL Database       │
              │   - ltree extension (paths)    │
              │   - JSONB (flexible data)      │
              │   - Soft deletes (is_deleted)  │
              │   - UUID primary keys          │
              └──────────────┬────────────────┘
                             │
              ┌──────────────▼────────────────┐
              │   Background Services          │
              │   - APScheduler (jobs)         │
              │   - Notification polling       │
              │   - WebSocket (live updates)    │
              └───────────────────────────────┘
```

---

## Project Directory Structure

```
Church_server/
├── app/
│   ├── main.py                  # FastAPI app creation, router mounting, startup/shutdown
│   ├── Dockerfile               # Container configuration
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── deps.py          # Shared dependencies (auth, db, permissions)
│   │       └── routes/          # One file per domain (30 route files)
│   │           ├── auth.py          # Login, token refresh, /me
│   │           ├── users.py         # User CRUD, role assignment
│   │           ├── workers.py       # Worker CRUD, search, approval
│   │           ├── hierarchy.py     # CRUD for Nation/State/Region/Group/Location/Fellowship
│   │           ├── counts.py        # Attendance count entry and aggregation
│   │           ├── offerings.py     # Offering/financial data entry
│   │           ├── tithes.py        # Tithe-specific financial data
│   │           ├── attendance.py    # Worker attendance tracking
│   │           ├── records.py       # Newcomer/convert records (combined)
│   │           ├── newcomers.py     # Newcomers endpoint (mirrors records)
│   │           ├── converts.py      # Converts endpoint (mirrors records)
│   │           ├── fellowship_activities.py  # Fellowship CRUD (members, attendance, offerings, etc.)
│   │           ├── announcements.py # Regional announcements
│   │           ├── information.py   # Legacy information/announcement alias
│   │           ├── programs.py      # Program domains, types, events
│   │           ├── approvals.py     # Transfers, status changes, worker removal (escalation)
│   │           ├── user_approval.py # User account approval/rejection workflow
│   │           ├── reports.py       # Analytics, summaries, exports
│   │           ├── statistics.py    # Population and user statistics
│   │           ├── rbac.py          # Role, Permission, RoleScore management
│   │           ├── sync.py          # Offline batch sync, conflict resolution
│   │           ├── media.py         # Media galleries and items
│   │           ├── public.py        # Public (unauthenticated) endpoints
│   │           ├── recovery.py      # Password reset / security questions
│   │           ├── notifications.py # Notification polling
│   │           ├── websocket.py     # WebSocket connection for live updates
│   │           ├── system.py        # System meta, seed, health, metrics
│   │           ├── app_version.py   # Mobile app version management
│   │           └── ...
│   │
│   ├── core/
│   │   ├── config.py            # Settings (env vars, timeouts, token TTL)
│   │   ├── security.py          # JWT creation/verification, bcrypt, scope calculator
│   │   └── logging_config.py    # Structured logging setup
│   │
│   ├── db/
│   │   ├── base.py              # SQLAlchemy declarative base
│   │   ├── session.py           # Async session factory
│   │   └── init_rbac.py         # Seed script for roles, permissions, role scores
│   │
│   ├── models/                  # SQLAlchemy ORM models (one file per domain)
│   │   ├── core.py              # Shared mixins: TimestampMixin, SoftDeleteMixin, LTreePathMixin
│   │   ├── user.py              # Worker, User, Role, Permission, RoleScore, PasswordResetToken
│   │   ├── location.py          # Nation, State, Region, Group, Location, Fellowship
│   │   ├── programs.py          # ProgramDomain, ProgramType, ProgramEvent
│   │   ├── counts.py            # Count
│   │   ├── offerings.py         # Offering
│   │   ├── attendance.py        # WorkerAttendance
│   │   ├── records.py           # Record (newcomers + converts)
│   │   ├── fellowship_activities.py  # FellowshipMember, FellowshipAttendance, FellowshipOffering, Testimony, PrayerRequest, AttendanceSummary
│   │   ├── announcement.py      # Announcement, AnnouncementItem
│   │   ├── approvals.py         # TransferRequest, StatusChangeRequest, WorkerRemovalRequest
│   │   ├── media.py             # MediaGallery, MediaItem
│   │   ├── audit.py             # AuditLog
│   │   └── app_version.py       # AppVersion
│   │
│   ├── schemas/                 # Pydantic v2 request/response schemas (one file per domain)
│   │   ├── user.py              # UserCreate, UserResponse, WorkerCreate, WorkerResponse, Token, etc.
│   │   ├── location.py          # NationCreate, StateCreate, ..., LocationCreate, etc.
│   │   ├── counts.py            # CountCreate, CountResponse, CountStats, etc.
│   │   ├── offerings.py         # OfferingCreate, OfferingResponse
│   │   ├── attendance.py        # WorkerAttendanceCreate, WorkerAttendanceResponse
│   │   ├── records.py           # RecordCreate, RecordResponse, RecordDetails
│   │   ├── announcements.py     # AnnouncementCreate, AnnouncementResponse, AnnouncementItemCreate
│   │   ├── approvals.py         # TransferRequestCreate, RemovalRequestCreate, RemovalActionPayload, etc.
│   │   └── ...
│   │
│   ├── crud/                    # Database operation layer (one file per domain)
│   │   ├── crud_user.py         # User + Worker CRUD
│   │   ├── crud_approvals.py    # Transfer, StatusChange, WorkerRemoval CRUD
│   │   └── ...
│   │
│   ├── services/
│   │   ├── report_service.py    # Business logic for analytics and reports
│   │   └── notification_service.py  # Notification polling logic
│   │
│   └── utils/
│       ├── common.py            # Shared helpers
│       └── time_utils.py        # Timezone and date utilities
│
├── alembic/                     # Database migrations
│   ├── env.py
│   └── versions/                # Migration files (timestamped)
│
├── docs/                        # This documentation
├── scripts/
│   └── setup_db.py              # One-shot database initialization script
├── requirements.txt
├── pyproject.toml               # FastAPI Cloud entrypoint configuration
├── .fastapicloudignore          # Files excluded from FastAPI Cloud uploads
└── .env.example                 # Sample environment configuration
```

---

## Request Lifecycle

```
Client Request
    │
    ▼
FastAPI Router
    │
    ▼
Dependency Injection
    ├── deps.get_db()                → Provides AsyncSession from pool
    ├── deps.get_current_active_user() → Decodes JWT, loads User from DB
    └── deps.PermissionChecker("counts:create") → Checks if user's role has this permission
    │
    ▼
Route Handler Function
    │
    ▼
CRUD Layer (crud/)
    │  - Validates entity existence
    │  - Applies scope filtering (ltree paths)
    │  - Executes async DB queries (SQLAlchemy)
    │
    ▼
Database (PostgreSQL via asyncpg)
    │
    ▼
Pydantic Schema Serialization → Response
```

---

## Authentication Flow

```
1. Client sends: POST /api/v1/auth/login
   { "username": "email@example.com", "password": "pass" }

2. Server:
   a. Looks up user by email
   b. Verifies password with bcrypt
   c. Checks is_active = True and approval_status = 'approved'
   d. Finds user's highest role score
   e. Calculates scope_path from home_path + score
   f. Creates JWT access token (short-lived) + refresh token (long-lived)

3. Client receives: { "access_token": "...", "refresh_token": "...", "token_type": "bearer" }

4. Client sends every subsequent request with:
   Authorization: Bearer <access_token>

5. When access token expires:
   POST /api/v1/auth/refresh { "refresh_token": "..." }
   → New access token issued, scope recalculated
```

---

## Scope Path Calculation

The scope path is derived from the user's `home_path` (their physical location's ltree path) and their role score:

| Role Score | Scope = | Example |
|---|---|---|
| 1–3 (Location level) | `home_path` (own location) | `org.234.KW.ILN.ILE.001` |
| 4 (Group Pastor) | Parent group path | `org.234.KW.ILN.ILE` |
| 5 (Region Pastor) | Parent region path | `org.234.KW.ILN` |
| 6 (State Overseer) | State path | `org.234.KW` |
| 7 (National Admin) | Nation path | `org.234` |
| 8–9 (Continental/Global) | Root path | `org` |

All data queries then filter with `path <@ scope_path` (ltree descendant operator).

---

## Data Integrity Guarantees

| Guarantee | Mechanism |
|---|---|
| No orphaned users | `Worker` must exist before creating `User` |
| No orphaned workers | `Location` FK enforced with `RESTRICT` on delete |
| Soft deletes everywhere | `is_deleted` flag on all major tables |
| Audit trail | `created_at`, `updated_at`, `created_by` on all records |
| Idempotent sync | `client_id` UUID + idempotency check on batch sync |
| Optimistic locking | `version` integer on critical tables |
| Scope isolation | ltree `<@` operator + GIST indexing |

---

## Database Connection

The system uses **asyncpg** as the PostgreSQL driver with **SQLAlchemy 2.x async** ORM. Connection pooling is handled by SQLAlchemy's built-in pool. The database URL is configured in `.env` as `DATABASE_URL`.

For local development: `postgresql+asyncpg://user:password@localhost:5433/dclm`
For production (Supabase): use the Supabase transaction pooler URL with `sslmode=require`.
