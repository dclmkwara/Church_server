# Permissions Reference Matrix

## Permissions by Feature & Level

This table shows which role scores have access to each operation. A `✅` means the role level can perform this action; `❌` means it cannot. This is enforced both by the `PermissionChecker` dependency and by ltree scope filtering.

---

## How Permissions Work

1. **Route-level:** Routes use `Depends(deps.PermissionChecker("resource:action"))` to check that the user's roles include the required permission string.
2. **Data-level:** Even if the permission check passes, all data queries apply `WHERE path <@ scope_path` to ensure a user can only see/modify data within their hierarchy.
3. **Role-level:** When assigning roles, a user cannot assign a role whose score is >= their own score.

---

## Permission String Reference

| Permission String | Description |
|---|---|
| `workers:read` | View worker records |
| `workers:create` | Register new workers |
| `workers:update` | Edit worker details |
| `workers:delete` | Soft-delete a worker |
| `workers:approve` | Approve or reject worker registrations |
| `users:read` | View user accounts |
| `users:create` | Create user accounts |
| `users:update` | Update user accounts |
| `users:delete` | Deactivate user accounts |
| `users:approve` | Approve or reject user app access requests |
| `counts:read` | View attendance counts |
| `counts:create` | Submit new counts |
| `counts:update` | Edit existing counts |
| `counts:delete` | Remove a count entry |
| `offerings:read` | View offering records |
| `offerings:create` | Record new offerings |
| `offerings:update` | Edit offerings |
| `offerings:delete` | Remove an offering record |
| `attendance:read` | View worker attendance |
| `attendance:create` | Mark worker attendance |
| `attendance:update` | Edit attendance records |
| `records:read` | View newcomer/convert records |
| `records:create` | Register newcomers/converts |
| `records:update` | Update follow-up status |
| `fellowships:read` | View fellowship data |
| `fellowships:create` | Enter fellowship data |
| `fellowships:manage` | Full fellowship CRUD management |
| `announcements:read` | View announcements |
| `announcements:create` | Publish regional announcements |
| `announcements:update` | Edit existing announcements |
| `approvals:read` | View approval requests |
| `approvals:create` | Submit transfer/removal requests |
| `approvals:approve` | Approve/reject/escalate approval requests |
| `hierarchy:read` | View location hierarchy |
| `hierarchy:manage` | Create/update hierarchy nodes |
| `reports:read` | Access reports and analytics |
| `rbac:manage` | Full RBAC management |
| `system:admin` | System administration |

---

## Access Level Matrix

| Permission | Level 1–2 | Level 3 | Level 4 | Level 5 | Level 6 | Level 7 | Level 8–9 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `counts:create` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `counts:read` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `counts:update` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `counts:delete` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `offerings:create` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `offerings:read` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `offerings:update` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `records:create` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `records:read` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `attendance:create` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `workers:read` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `workers:create` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `workers:approve` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `users:read` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `users:create` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `users:approve` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `fellowships:manage` | ✅ (own) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `approvals:create` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `approvals:approve` | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `announcements:read` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `announcements:create` | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| `hierarchy:manage` | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `reports:read` | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `rbac:manage` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `system:admin` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

> Note: All permissions are **additionally** filtered by scope. Even if Level 4 has `counts:read`, they can only see counts from branches under their group — the ltree filter handles this automatically.

---

## Approval Workflow Roles

### Worker Removal Escalation Chain

| Action | Who Can Do It |
|---|---|
| Submit removal request | Level 3 (Location Pastor) |
| First review (Approve/Reject/Escalate) | Level 4 (Group Pastor) |
| Second review | Level 5 (Regional Pastor) |
| Final decision | Level 6 (State Overseer) |

### Transfer Requests

| Action | Level Required |
|---|---|
| Submit a transfer request | Level 3+ |
| Approve/reject a transfer | Level 4+ (within scope) |

### User Account Approvals

| Action | Level Required |
|---|---|
| Approve/reject user app access | Level 3+ (within their location scope) |

### Worker Registration Approvals

| Action | Level Required |
|---|---|
| Approve/reject worker registration | Level 3+ (within their location scope) |

---

## Officials Appointment Rules

| Appointer Level | Can Appoint Roles Scored |
|---|---|
| Level 4 (Group Pastor) | 1, 2, 3 (Location Usher, Senior Usher, LocationPastor) |
| Level 5 (Regional Pastor) | 1, 2, 3, 4 (all below + GroupPastor) |
| Level 6 (State Overseer) | 1-5 — is the ONLY one who can appoint a StateAdmin |
| Level 9 (System Admin) | All scores |

> General rule: You can only assign roles with a score **strictly less than** your own score.
