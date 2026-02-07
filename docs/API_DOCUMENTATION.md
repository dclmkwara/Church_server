# DCLM API Documentation

**Version:** 1.0.0  
**Base URL:** `/api/v1`  
**Total Endpoints:** 111  
**Authentication:** JWT Bearer Token

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Users & Workers](#2-users--workers)
3. [RBAC (Roles, Permissions, Scores)](#3-rbac)
4. [Hierarchy](#4-hierarchy)
5. [Data Collection](#5-data-collection)
6. [Programs & Events](#6-programs--events)
7. [Fellowship Activities](#7-fellowship-activities)
8. [Media Management](#8-media-management)
9. [Public API](#9-public-api)
10. [Reports & Analytics](#10-reports--analytics)
11. [System & Utilities](#11-system--utilities)
12. [Error Handling](#12-error-handling)
13. [Authentication Guide](#13-authentication-guide)

---

## 1. Authentication

### 1.1 Login

**Endpoint:** `POST /auth/login`  
**Authentication:** None (public)  
**Description:** Authenticate user and receive JWT tokens

**Request Body:**
```json
Content-Type: application/x-www-form-urlencoded

username=+2349012345678&password=SecurePass123!
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Token Claims:**
```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "phone": "+2349012345678",
  "role": "GroupPastor",
  "score": 4,
  "home_path": "org.234.kw.iln.ile.001",
  "scope_path": "org.234.kw.iln.ile",
  "exp": 1706025600,
  "iat": 1706022000
}
```

**Errors:**
- `400` - Invalid credentials
- `401` - Account pending approval / rejected

---

### 1.2 Refresh Token

**Endpoint:** `POST /auth/refresh`  
**Authentication:** None  
**Description:** Get new access token using refresh token

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:**
- `401` - Invalid/expired refresh token
- `404` - User not found

---

### 1.3 Get Current User

**Endpoint:** `GET /auth/me`  
**Authentication:** Required  
**Description:** Get authenticated user's profile

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:** `200 OK`
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "worker_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+2349012345678",
  "location_id": "001",
  "is_active": true,
  "approval_status": "approved",
  "roles": [
    {
      "id": 1,
      "role_name": "GroupPastor",
      "score_value": 4,
      "permissions": [...]
    }
  ],
  "path": "org.234.kw.iln.ile.001",
  "created_at": "2026-01-20T10:30:00Z"
}
```

---

## 2. Users & Workers

### 2.1 List Users

**Endpoint:** `GET /users/`  
**Authentication:** Required  
**Description:** List users within scope (filtered by role score)

**Query Parameters:**
- `skip` (int, default: 0) - Pagination offset
- `limit` (int, default: 100) - Max results

**Response:** `200 OK`
```json
[
  {
    "user_id": "...",
    "name": "John Doe",
    "phone": "+2349012345678",
    "location_id": "001",
    "is_active": true,
    "approval_status": "approved",
    "roles": [...]
  }
]
```

---

### 2.2 Create User

**Endpoint:** `POST /users/`  
**Authentication:** Required  
**Permission:** `users:create`  
**Description:** Create new user (admin only)

**Request Body:**
```json
{
  "worker_id": "660e8400-e29b-41d4-a716-446655440001",
  "password": "SecurePass123!",
  "role_ids": [1, 2]
}
```

**Response:** `201 Created`
```json
{
  "user_id": "...",
  "worker_id": "...",
  "name": "John Doe",
  "phone": "+2349012345678",
  "is_active": true,
  "approval_status": "pending"
}
```

---

### 2.3 Worker Self-Registration

**Endpoint:** `POST /users/register`  
**Authentication:** None (public)  
**Description:** Worker registers for user account (requires approval)

**Request Body:**
```json
{
  "phone": "+2349012345678",
  "password": "SecurePass123!",
  "email": "worker@example.com"
}
```

**Response:** `201 Created`
```json
{
  "user_id": "...",
  "approval_status": "pending",
  "message": "Account created. Awaiting admin approval."
}
```

---

### 2.4 List Pending Approvals

**Endpoint:** `GET /users/pending`  
**Authentication:** Required  
**Permission:** `users:approve`  
**Description:** List users awaiting approval

**Response:** `200 OK`
```json
[
  {
    "user_id": "...",
    "name": "John Doe",
    "phone": "+2349012345678",
    "created_at": "2026-01-20T10:30:00Z",
    "approval_status": "pending"
  }
]
```

---

### 2.5 Approve User

**Endpoint:** `POST /users/{user_id}/approve`  
**Authentication:** Required  
**Permission:** `users:approve`  
**Description:** Approve pending user account

**Response:** `200 OK`
```json
{
  "user_id": "...",
  "approval_status": "approved",
  "approved_by": "...",
  "approved_at": "2026-01-20T11:00:00Z"
}
```

---

### 2.6 Reject User

**Endpoint:** `POST /users/{user_id}/reject`  
**Authentication:** Required  
**Permission:** `users:approve`

**Request Body:**
```json
{
  "reason": "Incomplete worker registration"
}
```

**Response:** `200 OK`

---

### 2.7 Bulk Approve

**Endpoint:** `POST /users/bulk-approve`  
**Authentication:** Required  
**Permission:** `users:approve`

**Request Body:**
```json
{
  "user_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response:** `200 OK`
```json
{
  "approved": 3,
  "failed": 0
}
```

---

### 2.8 List Workers

**Endpoint:** `GET /workers`  
**Authentication:** Required  
**Description:** List workers within scope

**Query Parameters:**
- `skip`, `limit` - Pagination
- `location_id` (optional) - Filter by location
- `unit` (optional) - Filter by unit (e.g., "Ushering")

**Response:** `200 OK`
```json
[
  {
    "worker_id": "...",
    "user_id": "KW/2349012345678",
    "name": "John Doe",
    "phone": "+2349012345678",
    "email": "john@example.com",
    "location_id": "001",
    "location_name": "Ilorin East",
    "unit": "Ushering",
    "status": "Active"
  }
]
```

---

### 2.9 Register Worker

**Endpoint:** `POST /workers`  
**Authentication:** Required  
**Permission:** `workers:create`

**Request Body:**
```json
{
  "name": "John Doe",
  "phone": "+2349012345678",
  "email": "john@example.com",
  "gender": "Male",
  "location_id": "001",
  "unit": "Ushering",
  "address": "123 Main St",
  "occupation": "Engineer",
  "marital_status": "Single"
}
```

**Response:** `201 Created`

---

## 3. RBAC

### 3.1 List Permissions

**Endpoint:** `GET /rbac/permissions`  
**Authentication:** Required  
**Description:** List all permissions

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "permission": "users:create",
    "name": "Create Users",
    "description": "Can create new user accounts"
  },
  {
    "id": 2,
    "permission": "counts:read",
    "name": "Read Counts",
    "description": "Can view count records"
  }
]
```

---

### 3.2 Create Permission

**Endpoint:** `POST /rbac/permissions`  
**Authentication:** Required  
**Permission:** Superadmin only

**Request Body:**
```json
{
  "permission": "reports:export",
  "name": "Export Reports",
  "description": "Can export reports to CSV/Excel"
}
```

---

### 3.3 List Roles

**Endpoint:** `GET /rbac/roles`  
**Authentication:** Required

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "role_name": "GroupPastor",
    "description": "Group level pastor",
    "score_id": 4,
    "score_value": 4,
    "permissions": [
      {
        "id": 1,
        "permission": "users:create",
        "name": "Create Users"
      }
    ]
  }
]
```

---

### 3.4 Create Role

**Endpoint:** `POST /rbac/roles`  
**Authentication:** Required  
**Permission:** Superadmin only

**Request Body:**
```json
{
  "role_name": "RegionalPastor",
  "description": "Regional level pastor",
  "score_id": 5,
  "permission_ids": [1, 2, 3, 4]
}
```

---

### 3.5 Update Role

**Endpoint:** `PUT /rbac/roles/{role_id}`  
**Authentication:** Required  
**Permission:** Superadmin only

**Request Body:**
```json
{
  "role_name": "RegionalPastor",
  "description": "Updated description",
  "permission_ids": [1, 2, 3, 4, 5]
}
```

---

### 3.6 List Role Scores

**Endpoint:** `GET /rbac/scores`  
**Authentication:** Required  
**Description:** List all role score levels (1-9)

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "score": 1,
    "score_name": "Worker",
    "description": "Location level worker/usher"
  },
  {
    "id": 4,
    "score": 4,
    "score_name": "GroupPastor",
    "description": "Group level pastor"
  },
  {
    "id": 9,
    "score": 9,
    "score_name": "GlobalAdmin",
    "description": "Highest privilege (GS, Top Engineer)"
  }
]
```

---

## 4. Hierarchy

### 4.1 Get Hierarchy Tree

**Endpoint:** `GET /hierarchy/tree`  
**Authentication:** Required  
**Description:** Get complete hierarchy tree (scoped to user's access)

**Response:** `200 OK`
```json
{
  "nation": {
    "nation_id": "234",
    "country_name": "Nigeria",
    "path": "org.234",
    "states": [
      {
        "state_id": "KW",
        "state_name": "Kwara",
        "path": "org.234.kw",
        "regions": [...]
      }
    ]
  }
}
```

---

### 4.2 List Locations

**Endpoint:** `GET /locations`  
**Authentication:** Required  
**Description:** List locations within scope

**Query Parameters:**
- `skip`, `limit` - Pagination
- `church_type` (optional) - Filter: "DLBC", "DLCF", "DLSO"

**Response:** `200 OK`
```json
[
  {
    "location_id": "001",
    "location_name": "Ilorin East",
    "church_type": "DLBC",
    "address": "123 Main St",
    "path": "org.234.kw.iln.ile.001"
  }
]
```

---

### 4.3 Create Location

**Endpoint:** `POST /locations`  
**Authentication:** Required  
**Permission:** `locations:create`

**Request Body:**
```json
{
  "location_id": "002",
  "group_id": "ILE",
  "location_name": "Ilorin West",
  "church_type": "DLBC",
  "address": "456 Oak Ave"
}
```

---

### 4.4 List Fellowships

**Endpoint:** `GET /fellowships`  
**Authentication:** Required

**Query Parameters:**
- `location_id` (optional) - Filter by location

**Response:** `200 OK`
```json
[
  {
    "fellowship_id": "F001",
    "fellowship_name": "Victory Fellowship",
    "location_id": "001",
    "leader_in_charge": "Jane Doe",
    "leader_contact": "+2349087654321",
    "path": "org.234.kw.iln.ile.001.f001"
  }
]
```

---

### 4.5 Create Fellowship

**Endpoint:** `POST /fellowships`  
**Authentication:** Required  
**Permission:** `fellowships:create`

**Request Body:**
```json
{
  "fellowship_id": "F002",
  "location_id": "001",
  "fellowship_name": "Grace Fellowship",
  "fellowship_address": "789 Elm St",
  "leader_in_charge": "Jane Doe",
  "leader_contact": "+2349087654321"
}
```

---

## 5. Data Collection

### 5.1 Create Count

**Endpoint:** `POST /counts`  
**Authentication:** Required  
**Permission:** `counts:create`  
**Description:** Submit population count (with idempotency)

**Request Body:**
```json
{
  "program_event_id": "uuid-of-event",
  "adult_male": 150,
  "adult_female": 200,
  "youth_male": 50,
  "youth_female": 60,
  "boys": 30,
  "girls": 40,
  "client_id": "client-generated-uuid",
  "ts_utc": "2026-01-20T10:00:00Z"
}
```

**Response:** `201 Created`
```json
{
  "id": "server-uuid",
  "program_event_id": "...",
  "adult_male": 150,
  "total": 530,
  "client_id": "...",
  "created_by": "...",
  "created_at": "2026-01-20T10:00:05Z"
}
```

**Idempotency:** If `client_id` already exists, returns existing record with `200 OK`

---

### 5.2 List Counts

**Endpoint:** `GET /counts`  
**Authentication:** Required  
**Description:** List counts within scope

**Query Parameters:**
- `skip`, `limit` - Pagination
- `start_date`, `end_date` (optional) - Date range filter
- `program_event_id` (optional) - Filter by event

**Response:** `200 OK`
```json
[
  {
    "id": "...",
    "program_event_id": "...",
    "adult_male": 150,
    "adult_female": 200,
    "total": 530,
    "date": "2026-01-20",
    "created_by": "...",
    "path": "org.234.kw.iln.ile.001"
  }
]
```

---

### 5.3 Get Count

**Endpoint:** `GET /counts/{count_id}`  
**Authentication:** Required

**Response:** `200 OK`
```json
{
  "id": "...",
  "program_event_id": "...",
  "adult_male": 150,
  "adult_female": 200,
  "youth_male": 50,
  "youth_female": 60,
  "boys": 30,
  "girls": 40,
  "total": 530,
  "date": "2026-01-20",
  "created_by": "...",
  "created_at": "2026-01-20T10:00:05Z"
}
```

---

### 5.4 Update Count

**Endpoint:** `PUT /counts/{count_id}`  
**Authentication:** Required  
**Permission:** `counts:update`

**Request Body:**
```json
{
  "adult_male": 155,
  "adult_female": 205
}
```

---

### 5.5 Create Offering

**Endpoint:** `POST /offerings`  
**Authentication:** Required  
**Permission:** `offerings:create`

**Request Body:**
```json
{
  "program_event_id": "uuid-of-event",
  "amount": 50000.00,
  "currency": "NGN",
  "client_id": "client-generated-uuid",
  "ts_utc": "2026-01-20T10:00:00Z"
}
```

**Response:** `201 Created`

---

### 5.6 List Offerings

**Endpoint:** `GET /offerings`  
**Authentication:** Required

**Query Parameters:**
- `skip`, `limit` - Pagination
- `start_date`, `end_date` (optional)

---

### 5.7 Create Record (Newcomer/Convert)

**Endpoint:** `POST /records`  
**Authentication:** Required  
**Permission:** `records:create`

**Request Body:**
```json
{
  "program_event_id": "uuid-of-event",
  "record_type": "newcomer",
  "details": {
    "name": "John Smith",
    "phone": "+2349012345678",
    "address": "123 Main St",
    "notes": "Interested in baptism"
  },
  "client_id": "client-generated-uuid",
  "ts_utc": "2026-01-20T10:00:00Z"
}
```

**Response:** `201 Created`

---

### 5.8 Create Worker Attendance

**Endpoint:** `POST /attendance`  
**Authentication:** Required  
**Permission:** `attendance:create`

**Request Body:**
```json
{
  "program_event_id": "uuid-of-event",
  "worker_id": "worker-uuid",
  "status": "present",
  "client_id": "client-generated-uuid",
  "ts_utc": "2026-01-20T10:00:00Z"
}
```

---

## 6. Programs & Events

### 6.1 List Program Domains

**Endpoint:** `GET /programs/domains`  
**Authentication:** Required

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "slug": "regular_service",
    "name": "Regular Service",
    "description": "Weekly church services"
  },
  {
    "id": 2,
    "slug": "crusade",
    "name": "Crusade",
    "description": "Evangelistic crusades"
  }
]
```

---

### 6.2 Create Program Domain

**Endpoint:** `POST /programs/domains`  
**Authentication:** Required  
**Permission:** Superadmin only

**Request Body:**
```json
{
  "slug": "retreat",
  "name": "Retreat",
  "description": "Annual retreats"
}
```

---

### 6.3 List Program Types

**Endpoint:** `GET /programs/types`  
**Authentication:** Required

**Query Parameters:**
- `domain_id` (optional) - Filter by domain

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "domain_id": 1,
    "slug": "sunday_worship",
    "name": "Sunday Worship Service",
    "description": "Main Sunday service"
  }
]
```

---

### 6.4 Create Program Type

**Endpoint:** `POST /programs/types`  
**Authentication:** Required  
**Permission:** Superadmin only

**Request Body:**
```json
{
  "domain_id": 1,
  "slug": "bible_study",
  "name": "Bible Study",
  "description": "Weekly Bible study"
}
```

---

### 6.5 List Program Events

**Endpoint:** `GET /programs/events`  
**Authentication:** Required  
**Description:** List scheduled events within scope

**Query Parameters:**
- `skip`, `limit` - Pagination
- `start_date`, `end_date` (optional)
- `program_type_id` (optional)

**Response:** `200 OK`
```json
[
  {
    "id": "event-uuid",
    "program_type_id": 1,
    "date": "2026-01-26",
    "title": "Sunday Service",
    "path": "org.234.kw.iln.ile.001"
  }
]
```

---

### 6.6 Create Program Event

**Endpoint:** `POST /programs/events`  
**Authentication:** Required  
**Permission:** `events:create`

**Request Body:**
```json
{
  "program_type_id": 1,
  "date": "2026-01-26",
  "title": "Special Sunday Service",
  "location_id": "001"
}
```

---

## 7. Fellowship Activities

### 7.1 Register Fellowship Member

**Endpoint:** `POST /fellowships/members`  
**Authentication:** Required

**Request Body:**
```json
{
  "fellowship_id": "F001",
  "name": "Jane Smith",
  "phone": "+2349087654321",
  "email": "jane@example.com",
  "address": "456 Oak Ave",
  "gender": "Female",
  "marital_status": "Single"
}
```

---

### 7.2 List Fellowship Members

**Endpoint:** `GET /fellowships/members`  
**Authentication:** Required

**Query Parameters:**
- `fellowship_id` (required) - Fellowship to list members for

**Response:** `200 OK`
```json
[
  {
    "id": "...",
    "fellowship_id": "F001",
    "name": "Jane Smith",
    "phone": "+2349087654321",
    "is_active": true
  }
]
```

---

### 7.3 Submit Fellowship Attendance

**Endpoint:** `POST /fellowships/attendance`  
**Authentication:** Required

**Request Body:**
```json
{
  "fellowship_id": "F001",
  "date": "2026-01-20",
  "member_id": "member-uuid",
  "status": "present"
}
```

---

### 7.4 Submit Fellowship Offering

**Endpoint:** `POST /fellowships/offerings`  
**Authentication:** Required

**Request Body:**
```json
{
  "fellowship_id": "F001",
  "date": "2026-01-20",
  "amount": 5000.00,
  "currency": "NGN"
}
```

---

### 7.5 Create Testimony

**Endpoint:** `POST /fellowships/testimonies`  
**Authentication:** Required

**Request Body:**
```json
{
  "fellowship_id": "F001",
  "member_id": "member-uuid",
  "testimony": "God healed me from...",
  "date": "2026-01-20"
}
```

---

### 7.6 List Testimonies

**Endpoint:** `GET /fellowships/testimonies`  
**Authentication:** Required

**Query Parameters:**
- `fellowship_id` (required)

---

### 7.7 Create Prayer Request

**Endpoint:** `POST /fellowships/prayers`  
**Authentication:** Required

**Request Body:**
```json
{
  "fellowship_id": "F001",
  "member_id": "member-uuid",
  "request": "Pray for my family...",
  "is_urgent": false
}
```

---

### 7.8 List Prayer Requests

**Endpoint:** `GET /fellowships/prayers`  
**Authentication:** Required

**Query Parameters:**
- `fellowship_id` (required)

---

## 8. Media Management

### 8.1 Create Media Gallery

**Endpoint:** `POST /media/galleries`  
**Authentication:** Required  
**Permission:** `media:create`

**Request Body:**
```json
{
  "title": "Easter Retreat 2026",
  "description": "Photos from our annual Easter retreat",
  "location_id": "001",
  "slug": "easter-retreat-2026",
  "event_id": "event-uuid"
}
```

**Response:** `201 Created`
```json
{
  "id": "gallery-uuid",
  "title": "Easter Retreat 2026",
  "slug": "easter-retreat-2026",
  "path": "org.234.kw.iln.ile.001",
  "created_at": "2026-01-20T10:00:00Z"
}
```

---

### 8.2 List Media Galleries

**Endpoint:** `GET /media/galleries`  
**Authentication:** Required  
**Description:** List galleries within scope

**Query Parameters:**
- `skip`, `limit` - Pagination

---

### 8.3 Add Media Item

**Endpoint:** `POST /media/items`  
**Authentication:** Required  
**Permission:** `media:create`  
**Description:** Add media item metadata (file already uploaded to storage)

**Request Body:**
```json
{
  "gallery_id": "gallery-uuid",
  "file_path": "galleries/easter-2026/IMG_001.jpg",
  "file_name": "IMG_001.jpg",
  "file_type": "image/jpeg",
  "file_size": 2048576,
  "caption": "Opening ceremony",
  "is_cover": true
}
```

---

### 8.4 List Gallery Items

**Endpoint:** `GET /media/galleries/{gallery_id}/items`  
**Authentication:** Required

**Response:** `200 OK`
```json
[
  {
    "id": "item-uuid",
    "gallery_id": "gallery-uuid",
    "file_path": "galleries/easter-2026/IMG_001.jpg",
    "file_name": "IMG_001.jpg",
    "file_type": "image/jpeg",
    "caption": "Opening ceremony",
    "is_cover": true
  }
]
```

---

## 9. Public API

### 9.1 Get Public Events

**Endpoint:** `GET /public/events`  
**Authentication:** None (public)  
**Description:** List upcoming public events

**Query Parameters:**
- `skip`, `limit` - Pagination
- `from_date` (optional, default: today)

**Response:** `200 OK`
```json
[
  {
    "id": "event-uuid",
    "title": "Easter Retreat 2026",
    "date": "2026-04-05",
    "type_name": "Retreat"
  }
]
```

---

### 9.2 Get Public Locations

**Endpoint:** `GET /public/locations`  
**Authentication:** None (public)

**Query Parameters:**
- `skip`, `limit` - Pagination
- `search` (optional) - Search by name

**Response:** `200 OK`
```json
[
  {
    "id": "001",
    "name": "Ilorin East",
    "type": "DLBC",
    "address": "123 Main St"
  }
]
```

---

### 9.3 Get Public Galleries

**Endpoint:** `GET /public/galleries`  
**Authentication:** None (public)

**Response:** `200 OK`
```json
[
  {
    "id": "gallery-uuid",
    "title": "Easter Retreat 2026",
    "description": "Photos from our annual Easter retreat",
    "slug": "easter-retreat-2026",
    "created_at": "2026-01-20T10:00:00Z"
  }
]
```

---

## 10. Reports & Analytics

### 10.1 Get Summary Report

**Endpoint:** `GET /reports/summary`  
**Authentication:** Required  
**Description:** Get summary statistics within scope

**Query Parameters:**
- `start_date`, `end_date` (optional)

**Response:** `200 OK`
```json
{
  "total_counts": 50,
  "total_attendance": 25000,
  "total_offerings": 5000000.00,
  "total_newcomers": 150,
  "total_converts": 75,
  "period": {
    "start": "2026-01-01",
    "end": "2026-01-31"
  }
}
```

---

### 10.2 Get Financial Summary

**Endpoint:** `GET /reports/financial`  
**Authentication:** Required  
**Permission:** `reports:financial`

**Query Parameters:**
- `month` (required) - Format: "2026-01"

**Response:** `200 OK`
```json
{
  "month": "2026-01",
  "total_offerings": 5000000.00,
  "total_tithes": 2000000.00,
  "by_location": [
    {
      "location_id": "001",
      "location_name": "Ilorin East",
      "total": 500000.00
    }
  ]
}
```

---

### 10.3 Export CSV

**Endpoint:** `POST /reports/export/csv`  
**Authentication:** Required  
**Permission:** `reports:export`

**Request Body:**
```json
{
  "report_type": "counts",
  "start_date": "2026-01-01",
  "end_date": "2026-01-31"
}
```

**Response:** `200 OK`
```
Content-Type: text/csv
Content-Disposition: attachment; filename="counts_2026-01.csv"

date,location,adult_male,adult_female,total
2026-01-05,Ilorin East,150,200,530
...
```

---

### 10.4 Get Population Analytics

**Endpoint:** `GET /statistics/read-population`  
**Authentication:** Required

**Response:** `200 OK`
```json
{
  "total_population": 25000,
  "demographics": {
    "adult_male": 8000,
    "adult_female": 10000,
    "youth_male": 3000,
    "youth_female": 3500,
    "boys": 250,
    "girls": 250
  },
  "growth_rate": 5.2
}
```

---

### 10.5 Get Church Statistics

**Endpoint:** `GET /statistics/church-statistics`  
**Authentication:** Required

**Response:** `200 OK`
```json
{
  "total_locations": 50,
  "total_groups": 10,
  "total_regions": 3,
  "total_workers": 500,
  "total_fellowships": 200
}
```

---

## 11. System & Utilities

### 11.1 Get System Metadata

**Endpoint:** `GET /system/meta`  
**Authentication:** Required

**Response:** `200 OK`
```json
{
  "program_domains": [...],
  "program_types": [...],
  "church_types": ["DLBC", "DLCF", "DLSO"],
  "units": ["Ushering", "Choir", "Technical", ...],
  "version": "1.0.0"
}
```

---

### 11.2 Batch Sync

**Endpoint:** `POST /sync/batch`  
**Authentication:** Required  
**Description:** Batch upload offline records

**Request Body:**
```json
{
  "counts": [
    {
      "program_event_id": "...",
      "adult_male": 150,
      "client_id": "uuid1",
      "ts_utc": "2026-01-20T10:00:00Z"
    }
  ],
  "offerings": [...],
  "records": [...],
  "attendance": [...]
}
```

**Response:** `200 OK`
```json
{
  "counts": {
    "created": 5,
    "duplicates": 2,
    "errors": 0
  },
  "offerings": {...},
  "id_mappings": {
    "uuid1": "server-uuid1",
    "uuid2": "server-uuid2"
  }
}
```

---

### 11.3 Poll Notifications

**Endpoint:** `GET /notifications/poll`  
**Authentication:** Required

**Query Parameters:**
- `since` (required) - ISO timestamp

**Response:** `200 OK`
```json
{
  "counts": [
    {
      "id": "...",
      "created_at": "2026-01-20T10:05:00Z",
      "location": "Ilorin East"
    }
  ],
  "offerings": [...],
  "prayers": [...]
}
```

---

### 11.4 Request Password Reset

**Endpoint:** `POST /recovery/request-reset`  
**Authentication:** None (public)

**Request Body:**
```json
{
  "phone": "+2349012345678"
}
```

**Response:** `200 OK`
```json
{
  "message": "Reset token sent (mock email)",
  "token": "reset-token-123"
}
```

---

### 11.5 Verify Reset Token

**Endpoint:** `POST /recovery/verify-token`  
**Authentication:** None

**Request Body:**
```json
{
  "token": "reset-token-123"
}
```

**Response:** `200 OK`

---

### 11.6 Reset Password

**Endpoint:** `POST /recovery/reset-password`  
**Authentication:** None

**Request Body:**
```json
{
  "token": "reset-token-123",
  "new_password": "NewSecurePass123!"
}
```

---

## 12. Error Handling

### Standard Error Response

All errors return JSON with this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `200` | OK | Successful GET/PUT/DELETE |
| `201` | Created | Successful POST (resource created) |
| `400` | Bad Request | Invalid input, validation error |
| `401` | Unauthorized | Missing/invalid token, pending approval |
| `403` | Forbidden | Insufficient permissions |
| `404` | Not Found | Resource doesn't exist |
| `409` | Conflict | Duplicate resource (e.g., phone already exists) |
| `422` | Unprocessable Entity | Validation error (Pydantic) |
| `500` | Internal Server Error | Server error |

### Common Error Scenarios

**Invalid Token:**
```json
Status: 403
{
  "detail": "Could not validate credentials"
}
```

**Insufficient Permissions:**
```json
Status: 403
{
  "detail": "Operation not permitted. Required: users:create"
}
```

**Validation Error:**
```json
Status: 422
{
  "detail": [
    {
      "loc": ["body", "phone"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## 13. Authentication Guide

### Step 1: Login

```bash
curl -X POST "http://api.example.com/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=+2349012345678&password=SecurePass123!"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Step 2: Use Access Token

```bash
curl -X GET "http://api.example.com/api/v1/auth/me" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Step 3: Refresh When Expired

```bash
curl -X POST "http://api.example.com/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
```

### Token Expiration

- **Access Token:** 60 minutes (configurable)
- **Refresh Token:** 7 days (configurable)

### Scope-Based Data Filtering

All authenticated requests automatically filter data based on the user's `scope_path` from their JWT token:

- **Score 1-3** (Worker/Location Pastor): See only their location's data
- **Score 4** (Group Pastor): See all locations in their group
- **Score 5** (Regional Pastor): See all groups in their region
- **Score 6** (State Pastor): See all regions in their state
- **Score 7** (National Admin): See all states in their nation
- **Score 8-9** (Continental/Global): See all data

This is enforced at the **database level** via Row-Level Security (RLS) and cannot be bypassed.

---

## Appendix: Quick Reference

### Base URL
```
Production: https://api.dclm.org/api/v1
Development: http://localhost:8000/api/v1
```

### Authentication Header
```
Authorization: Bearer {access_token}
```

### Pagination
Most list endpoints support:
- `skip` (default: 0)
- `limit` (default: 100, max: 1000)

### Date Formats
- **ISO 8601:** `2026-01-20T10:30:00Z`
- **Date Only:** `2026-01-20`

### Idempotency
Data collection endpoints (`counts`, `offerings`, `records`, `attendance`) support idempotency via `client_id`. Submitting the same `client_id` twice returns the existing record.

---

**End of Documentation**  
**Version:** 1.0.0  
**Last Updated:** 2026-01-24
