# Authentication & Authorization

## Overview

The DCLM Management System uses **JWT (JSON Web Token)** authentication. Every API request (except public endpoints) must include a valid Bearer token in the `Authorization` header.

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Two Tokens, Two Purposes

| Token | Lifespan | Purpose |
|---|---|---|
| **Access Token** | Short-lived (configured by `ACCESS_TOKEN_EXPIRE_MINUTES`) | Sent with every API request |
| **Refresh Token** | Long-lived | Used only to obtain a new access token when the old one expires |

Access tokens contain all the claims the server needs to authorize requests. Refresh tokens contain only the user ID.

---

## Login

### `POST /api/v1/auth/login`

Accepts standard OAuth2 form data (NOT JSON).

**Required:** The user must have an approved worker record AND an approved user account (`approval_status = 'approved'`).

**Request:**
```
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=pastor@example.com&password=SecurePass123!
```

> Note: The `username` field expects an **email address** — the name is `username` because this follows the OAuth2 specification standard.

**Success Response (200):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBl...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBl...",
    "token_type": "bearer"
}
```

**Error Responses:**
| Status | Condition | Message |
|---|---|---|
| `400` | Email or password is wrong | `"Incorrect email or password"` |
| `400` | Account is deactivated | `"Your account has been deactivated..."` |
| `401` | Account is pending approval | `"Your account is awaiting admin approval..."` |
| `401` | Account was rejected | `"Your account was rejected. Reason: ..."` |

---

## The JWT Access Token (Claims Explained)

When decoded, a valid access token contains:

```json
{
    "sub": "550e8400-e29b-41d4-a716-446655440000",
    "email": "pastor@example.com",
    "role": "GroupPastor",
    "score": 4,
    "home_path": "org.234.KW.ILN.ILE.001",
    "scope_path": "org.234.KW.ILN.ILE",
    "exp": 1777777777,
    "iat": 1777777000,
    "type": "access"
}
```

| Claim | Type | Description |
|---|---|---|
| `sub` | UUID string | The user's unique ID in the system |
| `email` | string | User's email address |
| `role` | string | Name of the user's highest-score role (e.g., `"GroupPastor"`) |
| `score` | integer | Numeric level 1–9 — drives all permission checks |
| `home_path` | ltree string | The user's physical church location path |
| `scope_path` | ltree string | The widest path this user is allowed to access |
| `exp` | unix timestamp | Token expiry |
| `iat` | unix timestamp | Token issued at |
| `type` | string | `"access"` or `"refresh"` |

**Important:** The `scope_path` is not the same as `home_path`. A Group Pastor at branch `org.234.KW.ILN.ILE.001` gets `scope_path = org.234.KW.ILN.ILE` — which covers ALL branches in his group.

---

## How Scope Paths Are Calculated

At login, the server takes the user's location path and "trims" it based on role score:

```
home_path = org.234.KW.ILN.ILE.001
score = 3 (Location Pastor) → scope = org.234.KW.ILN.ILE.001  (same — own location only)
score = 4 (Group Pastor)    → scope = org.234.KW.ILN.ILE       (one level up = group)
score = 5 (Regional Pastor) → scope = org.234.KW.ILN            (two levels up = region)
score = 6 (State Overseer)  → scope = org.234.KW               (state level)
score = 7 (National Admin)  → scope = org.234                  (national level)
score = 8–9                 → scope = org                      (everything)
```

When this user makes a request, all database queries filter with: `WHERE path <@ 'org.234.KW.ILN.ILE'` — using PostgreSQL's ltree descendant-path operator.

---

## Token Refresh

When the access token expires, the client uses the refresh token to get a new access token **without re-entering their password**.

### `POST /api/v1/auth/refresh`

**Request (JSON):**
```json
{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Success Response (200):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

> On refresh, the server **reloads the user's roles from the database** before issuing a new token. This means any role changes made by an admin are reflected in the next refresh.

**Error Responses:**
| Status | Condition |
|---|---|
| `401` | Invalid token or wrong type |
| `404` | User no longer exists |
| `400` | User account deactivated |

---

## Get Current User Profile

### `GET /api/v1/auth/me`

Returns the full profile of the currently authenticated user.

**Request:**
```
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

**Success Response (200):**
```json
{
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "worker_id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "John Adebayo",
    "email": "john@example.com",
    "phone": "+2348012345678",
    "location_id": "001",
    "is_active": true,
    "approval_status": "approved",
    "path": "org.234.KW.ILN.ILE.001",
    "roles": [
        {
            "id": 5,
            "role_name": "GroupPastor",
            "score": {
                "score": 4,
                "score_name": "Group Level"
            }
        }
    ],
    "created_at": "2026-01-20T10:30:00Z"
}
```

---

## Permission System

Permissions follow the format `resource:action` (e.g., `workers:create`, `counts:read`).

Permissions are attached to **Roles**, and Roles are assigned to **Users**.

When a route requires a permission, the `PermissionChecker` dependency validates that the current user's roles include that permission. If not, the request is rejected with `403 Forbidden`.

**Common permissions:**

| Permission | Who typically has it |
|---|---|
| `workers:read` | Level 3+ |
| `workers:create` | Level 3+ |
| `workers:approve` | Level 3+ |
| `users:read` | Level 3+ |
| `users:create` | Level 3+ |
| `counts:read` | Level 1+ |
| `counts:create` | Level 1+ |
| `offerings:create` | Level 1+ |
| `announcements:create` | Level 5+ (Regional Pastor) |
| `reports:read` | Level 6+ |
| `rbac:manage` | Level 9 only |

The full permission seeding is in `app/db/init_rbac.py`.

---

## Security Best Practices Implemented

1. **bcrypt password hashing** — passwords are never stored in plain text
2. **JWT HS256 signing** — tokens are signed with a secret key from `.env`
3. **Scope isolation** — all queries are scoped to the user's ltree path
4. **Soft deletes** — nothing is permanently removed, full audit trail maintained
5. **Approval gate** — accounts cannot login until explicitly approved by a pastor
6. **Role score enforcement** — a user can only assign roles with a score lower than their own

---

## Password Recovery

Password recovery is handled via security questions (not email) for areas with unreliable internet. See `POST /api/v1/recovery/` routes for details.

Recovery flow:
1. `POST /api/v1/recovery/request-reset` — initiate with phone number
2. `POST /api/v1/recovery/verify-token` — verify recovery token
3. `POST /api/v1/recovery/reset-password` — set new password
