# Feature Catalog

## Core Features
- Hierarchy management (Nation → State → Region → Group → Location → Fellowship)
- Worker registration and user account management
- Role-based access control (RBAC) with score-based scope
- Program domains/types/events
- Attendance counts and worker attendance
- Offerings and tithes
- Newcomer/convert records
- Announcements and information
- Media galleries and items
- Reports and exports (CSV/Excel/PDF)
- Statistics dashboard endpoints
- Offline sync with conflict detection
- Public endpoints for events, locations, galleries, forms

## Developer Features
- Async SQLAlchemy architecture
- Consistent CRUD layer
- Route-level permission enforcement
- ltree-based hierarchical access control
- Soft delete for most records

