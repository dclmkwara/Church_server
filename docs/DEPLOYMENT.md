# Deploying DCLM API to FastAPI Cloud with Supabase

## Prerequisites

1. A FastAPI Cloud account
2. This repo pushed to GitHub, or the FastAPI Cloud CLI available locally
3. A Supabase project

## Project Entry Point

The app entry point is declared in `pyproject.toml`:

```toml
[tool.fastapi]
entrypoint = "app.main:app"
```

FastAPI Cloud should deploy the backend as `app.main:app`.

## Environment Variables

Set these in FastAPI Cloud before the first production deploy:

| Variable | Value |
|----------|-------|
| `APP_NAME` | `DCLM Server` |
| `DEBUG` | `false` |
| `SECRET_KEY` | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
| `DATABASE_URL` | Supabase transaction pooler URL, for example `postgresql+asyncpg://postgres.PROJECT:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require` |
| `SYNC_DATABASE_URL` | Optional psycopg2 URL for migrations |
| `DB_POOL_SIZE` | `5` |
| `DB_MAX_OVERFLOW` | `10` |
| `DB_POOL_RECYCLE_SECONDS` | `3600` |
| `BACKEND_CORS_ORIGINS` | JSON array of allowed frontend origins |

If the password contains `#`, encode it as `%23` when possible. The app also normalizes raw passwords before parsing, but encoded URLs are safer in dashboards and shells.

## Supabase Setup

1. Create a Supabase project.
2. Copy the Transaction pooler connection string from Supabase Database settings.
3. Use port `6543` for the pooler.
4. Keep `sslmode=require` on the URL.
5. The migration bootstrap creates the `ltree` extension and schema on a fresh database.

## Deploy

From the project root:

```bash
fastapi deploy
```

Or connect the GitHub repo in the FastAPI Cloud dashboard and select `app.main:app` as the application entry point.

## Migrations

Run migrations against the production Supabase database before opening the app to users:

```bash
python -m alembic upgrade head
```

The Alembic environment uses sync `psycopg2` for migrations while runtime traffic remains async with `asyncpg`.

## Initial Data

After migrations, seed safe metadata only:

```bash
python scripts/seed_admin_bootstrap.py --metadata-only
```

Do not run the full starter bootstrap against production unless you intentionally want it to create the starter pastor accounts. If you use it, pass a strong unique password:

```bash
python scripts/seed_admin_bootstrap.py --password "use-a-strong-unique-password"
```

## Verify

```text
https://your-fastapi-cloud-domain/health
https://your-fastapi-cloud-domain/docs
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `getaddrinfo failed` | Supabase project may be paused, or the host in `DATABASE_URL` is wrong. |
| `relation does not exist` | Run `python -m alembic upgrade head`. |
| `prepared statement already exists` | Use the transaction pooler URL; prepared statement cache is disabled automatically for Supabase pooler hosts. |
| CORS errors | Add the frontend URL to `BACKEND_CORS_ORIGINS`. |
