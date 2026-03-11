# Migration Guide

This project is a modernized rewrite of the legacy server.

## Key Changes
- Hierarchical scope handled with `ltree` instead of string prefix matching.
- Role scores and permissions are enforced consistently across routes.
- Offerings unify tithes with `fund_type`.

## Data Migration
- Use Alembic migrations in `alembic/versions`.
- Ensure `ltree` extension is installed in PostgreSQL.
