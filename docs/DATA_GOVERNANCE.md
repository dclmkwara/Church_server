# Data Governance and Row-Level Control

## ltree Design
- Each scoped entity stores `path` (ltree).
- Access is enforced with `path <@ :scope_path`.

## Example Path (Kwara)
Display ID: `DCM-234-KW-ILN-ILE-001`  
Meaning: General church brand ID → Nigeria → Kwara State → Ilorin Region → Ilorin East Group → Living Spring Church (Lajolo Polygate area).

## Location-to-Top Access
- A user at location scope sees that location and all descendant entities.
- Group/Region/State/Nation levels see broader subtrees.

## Role Score Power
- Higher score = broader scope and ability to assign lower roles.
- Users cannot assign roles with score >= their own max score.

## Soft Delete
- Most deletes are soft: `is_deleted=true`, `operation=DELETE`.
- Queries generally filter by `is_deleted=false`.

## Audit Fields
- `created_at`, `last_modify` for change tracking.

## Sync Idempotency
- `client_id` is used to dedupe offline submissions.

## Materialized Views
- Reports rely on materialized views for performance.
- Use `/reports/refresh` to refresh views.
