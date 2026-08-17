# DCLM Church Management System — Documentation Index

## For Church Leadership

| Document | Description |
|---|---|
| [System Overview](OVERVIEW.md) | What the system is, who uses it, the church hierarchy, and a map of all features |
| [Executive Summary](../COMPREHENSIVE_PROJECT_REVIEW.md) | Non-technical summary of the entire system for pastors and leadership |

---

## For Developers Integrating with the API

| Document | Description |
|---|---|
| [Overview & Quick Reference](OVERVIEW.md) | API base URL, authentication summary, all endpoint categories |
| [Authentication & Authorization](AUTHENTICATION.md) | Login flow, JWT claims, scope paths, permissions, recovery |
| [API Documentation](API_DOCUMENTATION.md) | Every endpoint with request/response examples and error codes |
| [Permissions Matrix](PERMISSIONS_MATRIX.md) | Who can do what — role scores, permission strings, approval chains |
| [Data Governance](DATA_GOVERNANCE.md) | Data flows, approval policies, offline sync, soft-delete rules |

---

## For Developers Contributing to the Codebase

| Document | Description |
|---|---|
| [Architecture](ARCHITECTURE.md) | System design, directory structure, request lifecycle, database connections |
| [Scaling Decision](SCALING_DECISION.md) | Current decision on modular monolith vs microservices, and the active performance-first scaling roadmap |
| [Database Schema](DATABASE_SCHEMA.md) | All tables, columns, types, foreign keys, and relationships |
| [Setup Guide](SETUP.md) | Installation, virtual env, database setup, Alembic migrations, first admin |
| [Tech Stack](TECH_STACK.md) | All technologies used — why they were chosen and how they're used |
| [Deployment](DEPLOYMENT.md) | Cloud deployment to FastAPI Cloud + Supabase PostgreSQL |
| [Security](SECURITY.md) | Security implementation details, bcrypt, JWT, RLS, CORS |
| [Troubleshooting](TROUBLESHOOTING.md) | Common errors and their fixes |

---

## Feature-Specific Documentation

| Document | Description |
|---|---|
| [Data Flow](DATA_FLOW.md) | How data moves through the system, from mobile entry to reports |
| [Role Scores Seed](ROLE_SCORES_SEED.md) | The 9 role scores and their initial seeded values |
| [Permissions Seed](PERMISSIONS_SEED.md) | Initial permission strings and their assignments to roles |
| [Comprehensive Analysis](COMPREHENSIVE_ANALYSIS.md) | Deep-dive analysis comparing old and new system design decisions |

---

## Mobile & Website Docs

| Document | Description |
|---|---|
| [Mobile Apps](mobile/) | API usage guide for mobile app developers |
| [Public Website](website/) | Public endpoint reference for the church website |

---

## Quick Start

**To run locally in 5 steps:**

```bash
# 1. Clone and enter
git clone <repo-url> && cd Church_server

# 2. Create and activate virtual environment
python -m venv .venv && .venv\Scripts\activate  # Windows
# OR: source .venv/bin/activate                  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up .env (copy example and edit)
cp .env.example .env

# 5. Database + start server
python scripts/setup_db.py --skip-create-db
uvicorn app.main:app --reload --port 8000
```

**Then visit:** http://localhost:8000/docs

---

## API Base URL

| Environment | URL |
|---|---|
| Local dev | `http://localhost:8000/api/v1` |
| Production | `https://your-fastapi-cloud-domain/api/v1` |

All endpoints (except `/public/*`, `/health`, `/`) require:
```
Authorization: Bearer <access_token>
```
