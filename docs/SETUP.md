# Developer Setup Guide

## Prerequisites

| Tool | Version Required | Purpose |
|---|---|---|
| Python | 3.11 or higher | Backend runtime |
| PostgreSQL or Supabase | 14 or higher with `ltree` | Primary database |
| Git | Any recent version | Version control |
| pip | Latest | Python package manager |

## Local Setup

```bash
git clone <repository-url>
cd Church_server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI runs at `http://localhost:8000/docs`.

## Environment

Required variables:

```ini
APP_NAME="DCLM Server"
DEBUG=false
SECRET_KEY=replace-with-a-64-character-random-hex-secret
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/dclm_db
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

For Supabase, use the transaction pooler URL with `sslmode=require`. If your password contains `#`, encode it as `%23` where possible.

## Database

Run migrations:

```bash
python -m alembic upgrade head
```

Seed safe metadata only:

```bash
python scripts/seed_admin_bootstrap.py --metadata-only
```

The full bootstrap script creates starter hierarchy records, workers, and users. Only run it intentionally, and pass a strong password:

```bash
python scripts/seed_admin_bootstrap.py --password "use-a-strong-unique-password"
```

## FastAPI Cloud Deployment

The app is configured for FastAPI Cloud:

- `pyproject.toml` declares `app.main:app`
- `.fastapicloudignore` excludes local-only files
- Supabase remains the production database

Set production env vars in FastAPI Cloud, run migrations against Supabase, seed metadata, then deploy:

```bash
fastapi deploy
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full production checklist.

## Tests

```bash
pytest
python -m compileall app alembic scripts tests
```

## Common Issues

| Error | Likely Cause | Fix |
|---|---|---|
| `asyncpg.InvalidPasswordError` | Wrong database password | Check `DATABASE_URL`; encode `#` as `%23` if needed |
| `Connection refused` | Database unavailable or wrong host/port | Start Postgres or verify Supabase URL |
| `relation does not exist` | Migrations not applied | Run `python -m alembic upgrade head` |
| `ModuleNotFoundError: No module named 'app'` | Wrong working directory or inactive venv | Run commands from `Church_server` root |
| `422 Unprocessable Entity` on login | JSON sent to form login endpoint | Use form-urlencoded login payload |
