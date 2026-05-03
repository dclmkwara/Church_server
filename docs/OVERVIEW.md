# DCLM Church Management System — Overview

> **Deeper Life Bible Church (DCLM) Management System**
> A modern, async-first, hierarchical church management platform.

---

## What Is This System?

The DCLM Church Management System is a **production-ready REST API backend** built to power three separate applications for Deeper Life Bible Church:

1. **Usher/Worker Mobile App** — Data collection (attendance counts, offerings, newcomers/converts) with full offline support.
2. **Fellowship Leaders App** — House fellowship management (members, attendance, offerings, testimonies, prayer requests).
3. **Admin/Pastors Web Dashboard** — Full administrative control for church leadership at all governance levels.

The backend exposes a **versioned REST API** at `/api/v1/` and is the single source of truth for all church data, user access, and governance workflows.

---

## Who Should Read This Documentation?

| Reader | What to focus on |
|---|---|
| **Church Leadership (non-technical)** | [Executive Summary](../COMPREHENSIVE_PROJECT_REVIEW.md) — explains what the system does in plain language |
| **Developers integrating with this API** | [API Documentation](API_DOCUMENTATION.md), [Authentication](AUTHENTICATION.md), [Route Details](ROUTE_DETAILS.md) |
| **Developers contributing to the codebase** | [Architecture](ARCHITECTURE.md), [Tech Stack](TECH_STACK.md), [Setup Guide](SETUP.md), [Database Schema](DATABASE_SCHEMA.md) |
| **System administrators** | [Deployment](DEPLOYMENT.md), [Security](SECURITY.md), [Troubleshooting](TROUBLESHOOTING.md) |

---

## The Church Hierarchy

Every record in the system is mapped to a level in the church's organizational hierarchy. This is the foundation of the entire access control and data aggregation system.

```
Organization (DCLM — Global)
    └── Nation         (e.g., Nigeria — code: 234)
        └── State      (e.g., Kwara State — code: KW)
            └── Region (e.g., Ilorin North — code: ILN)
                └── Group (e.g., Ilorin East — code: ILE)
                    └── Location/Branch (e.g., GRA DLBC — code: 001)
                        └── Fellowship (e.g., House Fellowship F001)
```

**Branch Types:**
| Code | Full Name | Description |
|---|---|---|
| DLBC | Deeper Life Bible Church | Main church building / adult congregation |
| DLCF | Deeper Life Children's Fellowship | Children's branch |
| DLSO | Deeper Life School Outreach | School-based outreach branch |

---

## Governance Levels & Role Scores

Access in the system is controlled by a **score** (1–9) attached to each user role:

| Score | Level Name | Jurisdiction |
|---|---|---|
| 1 | Usher / Field Worker | Own branch — data entry only (mobile app) |
| 2 | Senior Usher / Fellowship Leader | Own branch — includes fellowship module |
| 3 | Location/Branch Pastor | Full branch control (workers, users, data) |
| 4 | Group Pastor | All branches in the group |
| 5 | Regional Pastor | All groups in the region |
| 6 | State Overseer | All regions in the state |
| 7 | National Admin | Entire national church |
| 8 | Continental Leader | Multiple nations |
| 9 | General Overseer / System Admin | Full unrestricted access |

> **Key rule:** A user's role score determines both what data they can see AND what actions they can perform. Higher score = broader scope.

---

## Hierarchical ID Format

Every location has a unique human-readable ID built from its position in the hierarchy:

```
DCM-234-KW-ILN-ILE-001-F001
│    │   │   │   │   │   └── Fellowship code
│    │   │   │   │   └────── Location number (001)
│    │   │   │   └────────── Group code (ILE = Ilorin East)
│    │   │   └────────────── Region code (ILN = Ilorin North)
│    │   └────────────────── State code (KW = Kwara)
│    └────────────────────── Nation code (234 = Nigeria)
└─────────────────────────── Church code (DCM)
```

This ID is used in API responses and forms the basis of the `ltree` path used for hierarchical queries.

---

## Core Technical Concepts

### 1. ltree Paths

The backend uses PostgreSQL's `ltree` extension to store all hierarchical relationships as paths. This enables:

- **Scope queries**: `WHERE path <@ 'org.234.KW.ILN'` — find all data under Ilorin Region
- **Ancestor queries**: `WHERE 'org.234.KW.ILN.ILE.001' <@ path` — find all location's ancestors
- **GIST indexing**: All ancestor/descendant queries are O(log n), not O(n) full table scans

Example paths:
```
org.234             # Nigeria (national level)
org.234.KW          # Kwara State
org.234.KW.ILN      # Ilorin North Region
org.234.KW.ILN.ILE      # Ilorin East Group
org.234.KW.ILN.ILE.001  # GRA DLBC branch
org.234.KW.ILN.ILE.001.F001  # House Fellowship F001
```

### 2. JWT Token Claims

Every API call (except public endpoints) requires a JWT Bearer token. The token contains:

| Claim | Description | Example |
|---|---|---|
| `sub` | User's UUID | `"550e8400-..."` |
| `email` | User's email address | `"pastor@example.com"` |
| `role` | User's highest role name | `"GroupPastor"` |
| `score` | Role score (1-9) | `4` |
| `home_path` | User's physical location path | `"org.234.KW.ILN.ILE.001"` |
| `scope_path` | Access scope path (derived from score) | `"org.234.KW.ILN.ILE"` |

The `scope_path` is auto-set at login based on role score:
- Score 3 (Location Pastor) → scope = `home_path` (own branch only)
- Score 4 (Group Pastor) → scope = one level up (all branches in group)
- Score 5 (Region Pastor) → scope = two levels up (all groups in region)
- And so on...

### 3. Soft Deletes

No records are ever permanently deleted from the database. Instead, a boolean `is_deleted` flag is set. This ensures:
- Full audit trail for every record
- Recovery from accidental deletions
- Historical reporting accuracy

### 4. Offline Sync

The mobile apps can operate without internet connectivity. Each record created offline is given a unique `client_id` (UUID). When the device reconnects, the batch sync endpoint (`POST /api/v1/sync/batch`) uploads all pending records. The server checks the `idempotency_keys` table to avoid duplicates.

---

## Quick API Reference

| Category | Base Path | Auth Required |
|---|---|---|
| Authentication | `/api/v1/auth/` | No (login/refresh) |
| Users | `/api/v1/users/` | Yes |
| Workers | `/api/v1/workers/` | Yes |
| Hierarchy | `/api/v1/hierarchy/` | Yes |
| Counts | `/api/v1/counts/` | Yes |
| Offerings | `/api/v1/offerings/` | Yes |
| Tithes | `/api/v1/tithes/` | Yes |
| Attendances | `/api/v1/attendance/` | Yes |
| Records | `/api/v1/records/` | Yes |
| Newcomers | `/api/v1/newcomers/` | Yes |
| Converts | `/api/v1/converts/` | Yes |
| Fellowships | `/api/v1/fellowships/` | Yes |
| Announcements | `/api/v1/announcements/` | Yes |
| Programs | `/api/v1/programs/` | Yes |
| Approvals | `/api/v1/approvals/` | Yes |
| Reports | `/api/v1/reports/` | Yes |
| RBAC | `/api/v1/rbac/` | Yes |
| Sync | `/api/v1/sync/` | Yes |
| Media | `/api/v1/media/` | Yes |
| Public | `/api/v1/public/` | **No** |
| System | `/api/v1/system/` | Yes (high score) |

---

## Live API Documentation

The server auto-generates interactive API documentation you can use to test endpoints:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`
