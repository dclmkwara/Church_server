# Setup Guide

Complete installation and configuration guide for DCLM backend.

---

## System Requirements

### Minimum Requirements
- **OS:** Windows 10+, Ubuntu 20.04+, macOS 11+
- **Python:** 3.11 or higher
- **RAM:** 4GB minimum, 8GB recommended
- **Storage:** 10GB free space
- **Database:** PostgreSQL 16+

### Recommended Setup
- **Python:** 3.11.7
- **PostgreSQL:** 16.1
- **RAM:** 16GB
- **CPU:** 4+ cores

---

## Installation Steps

### 1. Install Python

Download and install Python 3.11+ from [python.org](https://python.org)

Verify installation:
```bash
python --version
# Should show: Python 3.11.x or higher
```

### 2. Install PostgreSQL

**Option A: Local PostgreSQL**
- Download from [postgresql.org](https://postgresql.org)
- Install with default settings
- Remember your postgres password

**Option B: Supabase (Recommended)**
- Create account at [supabase.com](https://supabase.com)
- Create new project
- Copy connection string from Settings → Database

### 3. Clone Repository

```bash
git clone https://github.com/your-org/dclm-backend.git
cd dclm-backend
```

### 4. Set Up Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 5. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (optional)
pip install -r requirements-dev.txt
```

### 6. Configure Environment Variables

Create `.env` file:
```bash
cp .env.example .env
```

Edit `.env`:
```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dclm

# Security
SECRET_KEY=generate-a-secure-random-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# Application
APP_NAME=DCLM Server
DEBUG=True
API_V1_PREFIX=/api/v1

# CORS (adjust for production)
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]
```

**Generate SECRET_KEY:**
```python
import secrets
print(secrets.token_urlsafe(32))
```

### 7. Initialize Database

```bash
# Run migrations
alembic upgrade head
```

### 8. Create Admin User

```bash
python scripts/create_admin.py
```

### 9. Start Development Server

```bash
uvicorn app.main:app --reload
```

Server will start at: `http://localhost:8000`

---

## Verification

### 1. Check API Documentation
Visit: `http://localhost:8000/docs`

### 2. Test Authentication

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@dclm.org&password=your-password"
```

### 3. Verify Database Connection

```bash
python -c "from app.db.session import engine; print('Database connected!')"
```

---

## Production Setup

### 1. Update Environment Variables

```env
DEBUG=False
BACKEND_CORS_ORIGINS=["https://yourdomain.com"]
```

### 2. Use Production Server

```bash
# Install gunicorn
pip install gunicorn

# Run with workers
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### 3. Set Up Reverse Proxy

Use Nginx or Caddy to proxy requests to your FastAPI app.

**Nginx example:**
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Enable HTTPS

Use Let's Encrypt for free SSL certificates:
```bash
certbot --nginx -d api.yourdomain.com
```

---

## Docker Setup (Optional)

### Using Docker Compose

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## Troubleshooting

See [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues and solutions.

---

## Next Steps

- [Architecture Overview](ARCHITECTURE.md)
- [API Documentation](API_DOCUMENTATION.md)
- [Deployment Guide](DEPLOYMENT.md)
