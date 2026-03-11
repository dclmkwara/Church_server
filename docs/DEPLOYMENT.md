# Deploying DCLM API to Render

## Prerequisites

1. A [Render](https://render.com) account
2. This repo pushed to GitHub (public or private)
3. A Supabase project **or** a Render PostgreSQL database

---

## Option A: One-Click Deploy (Render Blueprint)

1. Push this repo to GitHub.
2. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**.
3. Connect your GitHub repo.
4. Render reads `render.yaml` and creates:
   - A **PostgreSQL** database (`dclm-db`)
   - A **Web Service** (`dclm-api`)
5. Render auto-injects `DATABASE_URL` and generates a `SECRET_KEY`.
6. Deployment starts automatically.

---

## Option B: Manual Setup with Supabase

### 1. Create Render Web Service

1. Go to **Render Dashboard** → **New** → **Web Service**.
2. Connect your GitHub repo.
3. Settings:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 2. Set Environment Variables

In Render → your service → **Environment**:

| Variable | Value |
|----------|-------|
| `APP_NAME` | `DCLM Server` |
| `DEBUG` | `false` |
| `SECRET_KEY` | *(generate: `openssl rand -hex 32`)* |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres` |

> **Important:** The `DATABASE_URL` must use the `postgresql+asyncpg://` prefix.
> If you paste a `postgresql://` or `postgres://` URL, the app auto-converts it.

### 3. Deploy

Click **Create Web Service**. Render builds and deploys automatically.

---

## Post-Deployment

### Verify

```
https://your-service.onrender.com/health
https://your-service.onrender.com/docs
```

### Run Migrations

SSH into Render shell or add to build command:

```bash
pip install -r requirements.txt && python -m alembic upgrade head
```

### Seed Initial Data

Hit the seed endpoint (admin only) or use the Render shell:

```bash
python -c "from app.db.init_rbac import seed_rbac; import asyncio; asyncio.run(seed_rbac())"
```

---

## Supabase Setup

1. Create a project at [supabase.com](https://supabase.com).
2. Enable the `ltree` extension: **Database** → **Extensions** → search `ltree` → Enable.
3. Copy the connection string from **Settings** → **Database** → **Connection string** → **URI**.
4. Replace `postgresql://` with `postgresql+asyncpg://` in your `.env`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `getaddrinfo failed` | Supabase project is paused. Resume it from dashboard. |
| `relation does not exist` | Run `python -m alembic upgrade head` first. |
| Port binding error | Use `$PORT` env variable (Render sets it automatically). |
| CORS errors | Add frontend URL to `BACKEND_CORS_ORIGINS` in env. |
