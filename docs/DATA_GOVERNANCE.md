# Data Governance & Workflow Policies

## Overview

This document describes how data flows through the system, who is responsible for each type of data, and the policies that govern approvals, escalations, and data integrity.

---

## 1. Worker Data Policy

### Registration Flow

```
New Worker (public)
    │  POST /api/v1/public/workers/register (no auth)
    │
    ▼
workers table (approval_status = 'pending_verification')
    │
    ▼
Notification sent to Location Pastor (Level 3)
    │
    ├── Approve → approval_status = 'approved' (worker can now request app access)
    └── Reject  → approval_status = 'rejected' + rejection_reason stored
```

### Worker Status Management

A worker's `status` field tracks their active participation:
| Status | Meaning |
|---|---|
| `Active` | Currently serving in their unit |
| `Inactive` | No longer active but not removed |
| `Suspended` | Temporarily suspended — account blocked |

**Direct suspension:** A Location Pastor (Level 3) can directly suspend a worker by updating their status — this does NOT require a formal request.

**Formal removal:** If a pastor wants to permanently remove a worker from the system, they must submit a `WorkerRemovalRequest` through the escalation chain.

---

## 2. User Account Policy

### Access Request Flow

```
Approved Worker
    │  POST /api/v1/users/ (admin creates on their behalf)
    │  OR worker uses the public app to register
    │
    ▼
users table (approval_status = 'pending', is_active = true)
    │
    ▼
Notification → Location Pastor or Admin
    │
    ├── Approve → approval_status = 'approved' → user can now LOGIN
    └── Reject  → approval_status = 'rejected' + reason stored
```

**Key rules:**
- A worker must have `approval_status = 'approved'` before a user account is created for them
- A user must have `approval_status = 'approved'` and `is_active = true` to be able to login
- Deactivating a user (`is_active = false`) immediately blocks their login without deleting records

---

## 3. Data Entry Policy (Counts, Offerings, Records)

Data submitted through the counting and recording modules (via mobile apps or web) is **automatically accepted** upon submission. There is **no approval gate** for count data — this was a deliberate design decision to:

1. Avoid bureaucratic delays (a pastor doesn't need to approve every Sunday count)
2. Prevent data bottlenecks at the Group/Region level
3. Keep the data flow fast for the mobile apps

**Instead of approval gating, integrity is ensured by:**
- Linking every data entry to a specific `ProgramEvent` with a verified date and type
- Recording the `entered_by_id` for every entry
- Making edits traceable through `updated_at` timestamps
- Allowing supervisors to flag or delete incorrect entries within their scope
- The anomaly detection report (`GET /reports/anomalies`) identifies unusually high or low values

**The ltree path is the single source of aggregation:** when a Group Pastor views data, the system automatically aggregates all counts from every location under their group path — no manual forwarding or WhatsApp communication is needed.

---

## 4. Worker Removal Escalation Policy

### Why a Multi-Level Process?

Worker removal is irreversible (soft-delete renders the worker inactive). The multi-level escalation process ensures:
- No pastor can unilaterally remove a fellow worker without oversight
- The removal request includes a documented, timestamped reason
- Every review action is recorded in the `reviews` JSONB audit trail
- A rejected request can be re-submitted later if circumstances change

### Escalation Rules

| Level | Role | Can Do |
|---|---|---|
| 3 | Location Pastor | Submit removal request (cannot approve their own request) |
| 4 | Group Pastor | Approve (triggers soft-delete), Reject (returns to Level 3), or Escalate to Level 5 |
| 5 | Regional Pastor | Approve, Reject, or Escalate to Level 6 |
| 6 | State Overseer | Approve or Reject (this is the final level — no further escalation) |

**Minimum reason requirement:** The initial reason must be at least 20 characters.
**Minimum escalation notes:** Escalation notes must be at least 10 characters.

### Approval Action Audit Trail (`reviews` JSONB)

Every action taken on a removal request is recorded in the `reviews` array:
```json
[
    {
        "level": 4,
        "reviewer_id": "group-pastor-uuid",
        "action": "escalate",
        "notes": "Cannot verify locally. Escalating for regional oversight.",
        "at": "2026-03-12T10:30:00Z"
    },
    {
        "level": 5,
        "reviewer_id": "region-pastor-uuid",
        "action": "approve",
        "notes": "Worker has relocated. Removal justified.",
        "at": "2026-03-14T09:15:00Z"
    }
]
```

---

## 5. Announcement Policy

### Who Can Publish Announcements?

Only **Regional Pastors (Level 5)** or above can create and publish announcements. Announcements are always scoped to a Region — they apply to **all branches in that region**.

### Announcement Lifecycle

```
Regional Pastor drafts announcement
    │  POST /api/v1/announcements/
    │
    ▼
announcement saved (is_active = true by default)
    │
    ▼
Visible in GET /api/v1/announcements/ for all users in that region
    │
    ├── Can be edited: PUT /api/v1/announcements/{id}
    └── Can be deactivated: POST /api/v1/announcements/{id}/deactivate
        (is_active = false → no longer shown publicly)
```

---

## 6. Financial Data Policy

Offerings and tithes are tracked **per-event** (not per-individual). The record captures:
- Total aggregate amount collected
- Payment method breakdown (cash, transfer, mobile money, cheque)
- Fund type (offering, tithe, seed, special)
- The specific program event it was collected at

**No individual tithe tracking:** The system does not track individual contributions — all financial records are congregation-level aggregates per event.

---

## 7. Data Scope & Visibility Policy

| Rule | Enforcement |
|---|---|
| A user can only READ data within their scope | `WHERE path <@ scope_path` filter on every query |
| A user can only CREATE data for locations in their scope | Validated in CRUD layer |
| A user's scope is auto-derived from their role score at login | `create_admin_access_id()` in `app/core/security.py` |
| A user can specify a narrower scope than their default | `?scope_path=` query param accepted but validated |
| A user cannot specify a scope path that's outside their default | Server validates scope_path against user's token scope |

---

## 8. Soft Delete Policy

**No data is ever permanently deleted** from the system. All deletions set `is_deleted = true`. This means:

- All historical records are preserved for auditing and reporting
- A deleted record can be recovered by a system admin
- Reporting queries always exclude `is_deleted = true` records by default
- The soft-delete pattern is applied to: `workers`, `users`, `counts`, `offerings`, `records`, `attendance`, `fellowship_*`, `announcements`, and `program_events`

---

## 9. Offline Sync & Idempotency Policy

When mobile apps submit data after being offline, the server must handle duplicate submissions gracefully.

**Idempotency mechanism:**
1. The mobile app generates a `client_id` (UUID) for each record **before** storing it offline
2. When syncing, the record is submitted with its `client_id`
3. The server checks if a record with that `client_id` already exists
4. If found → the server returns the existing record (marked as "duplicate" in sync response)
5. If not found → the server stores the new record and returns it (marked as "synced")

**Result:** Even if a sync runs multiple times (e.g., due to network drops mid-sync), no duplicate records are created.

---

## 10. System-Level Access Controls Summary

| Action | Who Requires It |
|---|---|
| Create/manage hierarchy nodes | Level 6+ (State Overseer) ensures structural changes are authorized |
| Seed RBAC (roles/permissions) | Level 9 (System Admin) only |
| Access reports and analytics exports | Level 6+ |
| Create announcements | Level 5 (Regional Pastor)+ |
| Approve user accounts and workers | Level 3+ (within their scope) |
| Review/escalate removal requests | Level 4+ |
| Ultimate approval on removals | Level 6 (State Overseer) |
| System metrics and health | Level 7+ |
| Manage app versions | Level 9 |
