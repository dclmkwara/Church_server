# Database Schema

## Hierarchy
- `nations`, `states`, `regions`, `groups`, `locations`, `fellowships`
- Each has `path` (ltree) and foreign keys to parent levels.

## Users & Roles
- `workers`: profile data
- `users`: auth accounts linked to workers
- `roles`, `permissions`, `role_scores`

## Programs
- `program_domains`
- `program_types`
- `program_events`

## Data Collection
- `counts`
- `offerings`
- `worker_attendance`
- `records`

## Media & Announcements
- `media_galleries`, `media_items`
- `announcements`

## Fellowship Activities
- `fellowship_members`
- `fellowship_attendance`
- `fellowship_offerings`
- `fellowship_testimony`
- `fellowship_prayer_request`
- `fellowship_attendance_summaries`

## Approvals
- `transfer_requests`
- `status_change_requests`

## Reports
- Materialized views: `mv_daily_counts_by_location`, `mv_monthly_financial_summary`, `mv_attendance_trends`
