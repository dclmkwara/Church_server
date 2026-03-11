# Data Flow

## Ingestion
- Workers and users are created separately.
- Counts, offerings, attendance, and records are linked to program events.

## Reporting
- Reporting uses materialized views for performance.
- Exports available in CSV, Excel, PDF.

## Sync
- Batch sync supports offline clients with client IDs.
- Conflict detection and resolution is supported with basic rules.
