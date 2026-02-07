# Quick Start Guide

Get your DCLM backend up and running in 5 minutes.

---

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 16+ (or Supabase account)
- Git

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/dclm-backend.git
cd dclm-backend
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dclm

# Security
SECRET_KEY=your-secret-key-min-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Application
DEBUG=True
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Start the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at: `http://localhost:8000`

---

## Verify Installation

### Check API Documentation

Open your browser to:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Test Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Create First Admin User

Run the admin creation script:

```bash
python scripts/create_admin.py
```

Follow the prompts to create your first administrator account.

---

## Next Steps

- [Read the Architecture Guide](ARCHITECTURE.md)
- [Explore the API Documentation](API_DOCUMENTATION.md)
- [Learn about Security & Access Control](SECURITY.md)
- [Set up for Production](DEPLOYMENT.md)

---

## Common Issues

### Database Connection Error

**Error:** `could not connect to server`

**Solution:** Ensure PostgreSQL is running and credentials in `.env` are correct.

### Import Errors

**Error:** `ModuleNotFoundError`

**Solution:** Ensure virtual environment is activated and dependencies installed:
```bash
pip install -r requirements.txt
```

### Migration Errors

**Error:** `Target database is not up to date`

**Solution:** Run migrations:
```bash
alembic upgrade head
```

---

## Development Tools

### Run with Auto-Reload

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Tests

```bash
pytest
```

### Check Code Quality

```bash
# Linting
ruff check .

# Formatting
black .

# Type checking
mypy app/
```

---

**You're all set! Start building with DCLM.**
