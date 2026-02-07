# Technology Stack & Tools

**DCLM Church Management System**  
**Version:** 1.0.0

---

## Backend Stack

### Core Framework
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Language** | Python | 3.11+ | Primary programming language |
| **Web Framework** | FastAPI | Latest | Async web framework |
| **ASGI Server** | Uvicorn | Latest | Production server |

### Database & ORM
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Database** | PostgreSQL | 16+ | Primary data store |
| **Database Provider** | Supabase | Latest | Managed PostgreSQL + Storage |
| **ORM** | SQLAlchemy | 2.x | Async ORM |
| **Driver** | asyncpg | Latest | Async PostgreSQL driver |
| **Migrations** | Alembic | Latest | Database migrations |
| **Extensions** | ltree | Built-in | Hierarchical queries |

### Authentication & Security
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **JWT** | PyJWT | Latest | Token generation/verification |
| **Password Hashing** | passlib[bcrypt] | Latest | Secure password storage |
| **OAuth2** | FastAPI OAuth2 | Built-in | OAuth2 password flow |

### Validation & Serialization
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Validation** | Pydantic | 2.x | Data validation |
| **Serialization** | Pydantic | 2.x | JSON serialization |

### Background Jobs
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Scheduler** | APScheduler | Latest | Background task scheduling |
| **Jobs** | Custom | - | Materialized view refresh |

### HTTP Client
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **HTTP Client** | httpx | Latest | Async HTTP requests |

### Testing
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Test Framework** | pytest | Latest | Unit/integration tests |
| **Async Testing** | pytest-asyncio | Latest | Async test support |
| **Coverage** | pytest-cov | Latest | Code coverage |
| **Fixtures** | pytest fixtures | Built-in | Test data setup |

### Development Tools
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Linting** | ruff | Latest | Fast Python linter |
| **Formatting** | black | Latest | Code formatting |
| **Type Checking** | mypy | Latest | Static type checking |
| **Pre-commit** | pre-commit | Latest | Git hooks |

---

## Frontend Stack (Planned)

### Mobile Applications

#### Usher Mobile App
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | KivyMD / Flutter | Cross-platform mobile |
| **State Management** | Provider / Bloc | State management |
| **Local Storage** | SQLite / Hive | Offline data storage |
| **HTTP Client** | http / dio | API communication |

#### Fellowship Leaders App
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | KivyMD / Flutter | Cross-platform mobile |
| **State Management** | Provider / Bloc | State management |
| **Local Storage** | SQLite / Hive | Offline data storage |

### Web Applications

#### Admin/Pastors App
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | FastStrap (FastHTML) | Python-based web framework |
| **Styling** | Bootstrap 5 | UI components |
| **Charts** | Chart.js | Data visualization |

#### Public Website
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | FastStrap / FastHTML | Static site generation |
| **Styling** | Bootstrap 5 | Responsive design |
| **Media** | Supabase Storage | Image/video hosting |

---

## Infrastructure

### Hosting & Deployment
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Database** | Supabase | Managed PostgreSQL |
| **File Storage** | Supabase Storage | Media files |
| **Backend Hosting** | VPS / Cloud | API server |
| **Containerization** | Docker | Application packaging |
| **Orchestration** | Docker Compose | Multi-container apps |

### Monitoring & Logging (Planned)
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Logging** | Python logging | Application logs |
| **Monitoring** | Prometheus | Metrics collection |
| **Alerting** | Grafana | Visualization & alerts |

### Caching (Future)
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Cache** | Redis | Query result caching |
| **Session Store** | Redis | Session management |

---

## Python Dependencies

### Production Dependencies
```txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0
alembic>=1.12.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
httpx>=0.25.0
apscheduler>=3.10.0
```

### Development Dependencies
```txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
black>=23.11.0
ruff>=0.1.6
mypy>=1.7.0
pre-commit>=3.5.0
```

---

## Database Extensions

### PostgreSQL Extensions
```sql
-- Hierarchical queries
CREATE EXTENSION IF NOT EXISTS ltree;

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Full-text search (future)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

## Environment Variables

### Required
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Security
SECRET_KEY=your-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# Application
APP_NAME=DCLM Church Management
API_V1_PREFIX=/api/v1
DEBUG=False
```

### Optional
```bash
# Email (future)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Redis (future)
REDIS_URL=redis://localhost:6379/0

# Monitoring (future)
SENTRY_DSN=your-sentry-dsn
```

---

## Version Requirements

### Minimum Versions
- **Python:** 3.11+
- **PostgreSQL:** 16+
- **Node.js:** 18+ (for frontend)
- **Docker:** 20.10+ (optional)

### Recommended Versions
- **Python:** 3.11.7
- **PostgreSQL:** 16.1
- **Node.js:** 20.11.0

---

## Development Tools

### IDE Recommendations
- **VS Code** with extensions:
  - Python
  - Pylance
  - SQLTools
  - Docker
  - GitLens

### Database Tools
- **pgAdmin 4** - GUI for PostgreSQL
- **DBeaver** - Universal database tool
- **Supabase Studio** - Web-based database UI

### API Testing
- **Swagger UI** - Built-in at `/docs`
- **ReDoc** - Built-in at `/redoc`
- **Postman** - API testing
- **HTTPie** - CLI HTTP client

---

## Installation Commands

### Backend Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -r requirements-dev.txt

# Set up pre-commit hooks
pre-commit install
```

### Database Setup
```bash
# Run migrations
python -m alembic upgrade head

# Create initial admin user (custom script)
python scripts/create_admin.py
```

### Run Development Server
```bash
# With auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# With specific workers
uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000
```

---

## Docker Setup

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db

  db:
    image: postgres:16
    environment:
      - POSTGRES_USER=dclm
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=dclm
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Performance Benchmarks

### Expected Performance
- **Concurrent Users:** 1000+
- **Response Time:** <100ms (avg)
- **Database Queries:** <50ms (avg)
- **Throughput:** 10,000+ req/min

### Optimization Techniques
- Async I/O for non-blocking operations
- Connection pooling (asyncpg)
- Database indexing (GIST on ltree)
- Query optimization (eager loading)
- Materialized views for aggregates
- Table partitioning for historical data

---

## Security Measures

### Application Security
- JWT token authentication
- bcrypt password hashing (12 rounds)
- Row-Level Security (RLS) at database
- Input validation (Pydantic)
- SQL injection prevention (parameterized queries)
- CORS configuration
- Rate limiting (planned)

### Database Security
- SSL/TLS connections
- RLS policies on all tables
- Audit logging
- Encrypted backups (Supabase)

---

## Upgrade Path

### Python Version Upgrade
```bash
# Check current version
python --version

# Upgrade to 3.11+
# (OS-specific instructions)

# Recreate virtual environment
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Dependency Updates
```bash
# Update all dependencies
pip install --upgrade -r requirements.txt

# Check for outdated packages
pip list --outdated

# Update specific package
pip install --upgrade fastapi
```

---

**Last Updated:** January 24, 2026  
**Maintained By:** DCLM Development Team
