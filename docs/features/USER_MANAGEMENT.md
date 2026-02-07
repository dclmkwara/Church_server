# User Management

Complete guide to user and worker management in DCLM.

---

## Overview

The DCLM system uses a two-tier user model:
1. **Workers** - Church workers registry (primary)
2. **Users** - Application authentication accounts

**Key Principle:** Workers must be registered first before they can become application users.

---

## User Roles & Hierarchy

### Role Score System (1-9)

| Score | Role | Access Level |
|-------|------|--------------|
| 1-2 | Worker/Usher | Location only |
| 3 | Location Pastor | Location only |
| 4 | Group Pastor | All locations in group |
| 5 | Regional Pastor | All groups in region |
| 6 | State Pastor | All regions in state |
| 7 | National Admin | All states in nation |
| 8 | Continental Leader | All nations |
| 9 | Global Admin | Entire organization |

---

## Worker Registration

### API Endpoint
`POST /api/v1/workers`

### Request
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+2349012345678",
  "gender": "Male",
  "location_id": "001",
  "unit": "Ushering",
  "address": "123 Main St",
  "occupation": "Engineer",
  "marital_status": "Single"
}
```

### Response
```json
{
  "worker_id": "uuid",
  "user_id": "KW/2349012345678",
  "name": "John Doe",
  "status": "Active"
}
```

---

## User Account Creation

### Self-Registration
`POST /api/v1/users/register`

Workers can self-register for user accounts. Accounts require admin approval.

### Admin Creation
`POST /api/v1/users`

Admins can create user accounts directly.

---

## User Approval Workflow

### 1. List Pending Users
`GET /api/v1/users/pending`

### 2. Approve User
`POST /api/v1/users/{user_id}/approve`

### 3. Reject User
`POST /api/v1/users/{user_id}/reject`

```json
{
  "reason": "Incomplete worker registration"
}
```

### 4. Bulk Approve
`POST /api/v1/users/bulk-approve`

```json
{
  "user_ids": ["uuid1", "uuid2", "uuid3"]
}
```

---

## Authentication

### Login
`POST /api/v1/auth/login`

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=SecurePass123!"
```

### Response
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

### Token Claims
- `sub`: User ID
- `email`: User email
- `role`: Role name
- `score`: Role score (1-9)
- `home_path`: User's location path
- `scope_path`: Calculated access scope

---

## Role Assignment

### Assign Roles to User
`POST /api/v1/users/{user_id}/assign-roles`

```json
{
  "role_ids": [1, 2]
}
```

---

## User Deactivation

### Deactivate User
`POST /api/v1/users/{user_id}/deactivate`

### Reactivate User
`POST /api/v1/users/{user_id}/reactivate`

---

## Access Control

### Permission-Based
Routes can require specific permissions:
```python
@router.get("/sensitive-data")
async def get_data(
    current_user: User = Depends(PermissionChecker("data:read"))
):
    ...
```

### Score-Based
Higher scores can access lower-level data:
- Score 6 (State Pastor) can access all Score 1-5 data in their state
- Score 9 (Global Admin) can access everything

---

## Best Practices

1. **Always register workers first** before creating user accounts
2. **Use email for login** instead of phone numbers
3. **Assign appropriate roles** based on actual church position
4. **Review pending users regularly** to avoid account backlogs
5. **Deactivate users** instead of deleting when they leave

---

## Related Documentation

- [RBAC System](RBAC.md)
- [Security & Access Control](../SECURITY.md)
- [API Reference](../API_DOCUMENTATION.md)
