# Permissions Seed Script

This script scans the codebase for permission strings (e.g., `PermissionChecker("counts:read")`) and inserts them into the `permissions` table.

## Run
From the project root:
```
python scripts/seed_permissions.py
```

## What It Does
- Finds all permission strings used in the code.
- Creates missing permissions.
- Updates name/description if changed.
