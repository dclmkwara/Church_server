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

Population/count submissions are recorded without a separate approval step. This allows timely reporting while supervisors can review or correct submitted records within their scope. Financial submissions follow their separate approval/correction workflow and must not be treated as approved totals until approved.

For large services, two or more ushers may submit separate counts for the same location and event when each covers a different section or row. These are **complementary partial counts**: keep each submission as its own source record and sum the sections for the location total. Do not deduplicate distinct ushers' submissions by location/event. Idempotency applies to a retry of the same client submission key, not to separate usher submissions.

This workflow is intended to avoid a count approval bottleneck and to:

1. Avoid bureaucratic delays (a pastor doesn't need to approve every Sunday count)
2. Prevent data bottlenecks at the Group/Region level
3. Keep the data flow fast for the mobile apps

**Instead of approval gating, integrity is ensured by:**
- Linking count entries to a specific `ProgramEvent` with a verified date and type
- Recording the `entered_by_id` for every entry
- Making edits traceable through `updated_at` timestamps
- Allowing supervisors to flag or correct incorrect entries within their scope
- The anomaly detection report (`GET /reports/anomalies`) identifies unusually high or low values

Where report routes apply the hierarchical path filter, totals roll up the submitted count records under that scope. Report-by-report filtering and aggregation still require verification; this is not a guarantee that every query or dashboard applies the same scope.

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
| A user's maximum hierarchy scope comes from current roles and home path | Recomputed in protected request dependencies |
| Level 8 continental data access | Broad root envelope plus resolved nation paths within the user's home continent |
| Route query visibility | Enforced through application-level filters where implemented; verify each route before relying on this policy |
| Database row-level security | Not installed; application scope checks are not PostgreSQL RLS |

---

## 8. Soft Delete Policy

Selected entities use soft deletion (`is_deleted = true`). The behavior is not universal across all tables or delete operations, so do not treat this as a complete retention or audit guarantee. For models that support it:

- Records remain in the source table unless another retention process removes them
- Recovery must be verified per model and may require database backup or operator action
- Reporting routes exclude deleted records where the filter is implemented; verify each report before relying on it

---

## 9. Offline Sync & Idempotency Policy

When clients retry supported batch submissions, the server uses idempotency keys to avoid replaying the same submission. This does not establish that every mobile workflow works offline or that every write endpoint supports idempotency.

**Idempotency mechanism:**
1. A client supplies an idempotency key on a supported submission route
2. The server checks the key within that route's idempotency scope
3. A recognized retry can return the recorded prior result
4. A new key is processed as a new submission

Client-side persistence while offline, coverage across all write routes, and all batch failure/retry outcomes have not been verified here.

**Result:** A repeated request with the same key can be recognized on supported routes. Distinct submissions, including separate ushers' partial counts, remain distinct records.

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
