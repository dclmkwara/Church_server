# Quick Reference

This page groups common workflows and their related routes.

## 1. Set Up the Church Structure (Kwara State Branch)
- `POST /nations/`
- `POST /states/`
- `POST /regions/`
- `POST /groups/`
- `POST /locations/`
- `POST /fellowships/`

Sample display path: `DCM-234-KW-ILN-ILE-001` → General church brand ID → Nigeria → Kwara State → Ilorin Region → Ilorin East Group → Living Spring Church (Lajolo Polygate area).

## 2. Register Workers and Create User Accounts
- `POST /workers/`
- `POST /users/`
- `POST /users/auto-create`
- `POST /users/{id}/assign-roles`

## 3. Schedule Programs
- `POST /programs/domains`
- `POST /programs/types`
- `POST /programs/events`

## 4. Record Service Data
- `POST /counts/`
- `POST /offerings/`
- `POST /tithes/`
- `POST /attendance/`
- `POST /records/`

## 5. Fellowship Activities
- `POST /fellowships/members`
- `POST /fellowships/attendance`
- `POST /fellowships/offerings`
- `POST /fellowships/testimonies`
- `POST /fellowships/prayer-requests`

## 6. Announcements and Information
- `POST /announcements/`
- `POST /announcements/{id}/deactivate`

## 7. Reports and Exports
- `GET /reports/summary`
- `GET /reports/financial`
- `GET /reports/attendance`
- `GET /reports/export/csv`
- `POST /reports/export/excel`
- `POST /reports/export/pdf`

## 8. Offline Sync
- `POST /sync/batch`
- `GET /sync/changes`
- `GET /sync/conflicts`
- `POST /sync/resolve`

## 9. Public Website APIs
- `GET /public/events`
- `GET /public/locations`
- `GET /public/galleries`
- `GET /public/announcements`
- `POST /public/contact`
- `POST /public/prayer-request`

