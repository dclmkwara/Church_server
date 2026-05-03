# DCLM Church Management System - Documentation

**Version:** 1.3.0  
**Last Updated:** February 10, 2026  
**Status:** Production Ready — 124 API Endpoints

---

## 📚 Documentation Navigation

### Getting Started

- [🚀 Quick Start Guide](#quick-start)
- [📋 System Overview](#system-overview)
- [🎯 Project Goals](#project-goals)

### Architecture & Design

- [🏗️ System Architecture](./ARCHITECTURE.md)
- [🗄️ Database Schema](./DATABASE_SCHEMA.md)
- [🔐 Security & Access Control](./SECURITY.md)
- [📊 Data Flow](./DATA_FLOW.md)

### API Documentation

- [📖 Complete API Reference](./API_DOCUMENTATION.md)
- [🔑 Authentication Guide](./AUTHENTICATION.md)
- [🛣️ Route Catalog (124 endpoints)](./ROUTE_CATALOG.md)

### Development Guides

- [⚙️ Setup & Installation](./SETUP.md)
- [🛠️ Tools & Technologies](./TECH_STACK.md)
- [🧪 Testing Guide](./TESTING.md)
- [🚀 Deployment Guide](./DEPLOYMENT.md)

### Features & Modules

- [👥 User Management](./features/USER_MANAGEMENT.md)
- [🏢 Hierarchy System](./features/HIERARCHY.md)
- [📝 Data Collection](./features/DATA_COLLECTION.md)
- [🤝 Fellowship Features](./features/FELLOWSHIP.md)
- [📸 Media Management](./features/MEDIA.md)
- [🌐 Public API](./features/PUBLIC_API.md)
- [📊 Reports & Analytics](./features/REPORTS.md)

### Mobile Applications

- [📱 Usher Mobile App](./mobile/USHER_APP.md) *(Coming Soon)*
- [📱 Fellowship Leaders App](./mobile/FELLOWSHIP_APP.md) *(Coming Soon)*
- [💻 Admin/Pastors App](./mobile/ADMIN_APP.md) *(Coming Soon)*

### Public Website

- [🌐 Public Website Features](./website/PUBLIC_SITE.md) *(Coming Soon)*
- [🎨 Design System](./website/DESIGN_SYSTEM.md) *(Coming Soon)*

### Migration & Upgrade

- [🔄 Migration from Old System](./MIGRATION_GUIDE.md)
- [📈 Feature Comparison](./FEATURE_COMPARISON.md)
- [⚠️ Breaking Changes](./BREAKING_CHANGES.md)

### Reference

- [📚 Glossary](./GLOSSARY.md)
- [❓ FAQ](./FAQ.md)
- [🐛 Troubleshooting](./TROUBLESHOOTING.md)
- [📞 Support](./SUPPORT.md)

---

## 🚀 Quick Start

### Prerequisites

```bash
- Python 3.11+
- PostgreSQL 16+
- Node.js 18+ (for frontend)
```

### Backend Setup

```bash
# Clone repository
git clone https://github.com/your-org/dclm-backend.git
cd dclm-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# Run migrations
python -m alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

### Access API Documentation

```
Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
```

---

## 📋 System Overview

### What is DCLM?

The **Deeper Life Church Management (DCLM) System** is a comprehensive church management platform designed to:

- **Manage** hierarchical church structure (6 levels: Nation → State → Region → Group → Location → Fellowship)
- **Track** attendance, offerings, and newcomer records
- **Support** offline data collection with automatic synchronization
- **Enable** fellowship activities (members, testimonies, prayers)
- **Provide** real-time analytics and reports
- **Facilitate** communication between pastors and members
- **Publish** events and media to public website

### Key Features

✅ **Hierarchical Organization** - 6-level church structure with ltree-based queries  
✅ **Role-Based Access Control** - 9-level score system (Worker → Global Admin)  
✅ **Offline-First** - Mobile apps work without internet, sync when online  
✅ **Row-Level Security** - Database-enforced data isolation  
✅ **Media Management** - Photo/video galleries for events  
✅ **Public API** - Endpoints for public website integration  
✅ **Real-Time Analytics** - Population, financial, and attendance insights  
✅ **Audit Logging** - Complete action history for accountability

---

## 🎯 Project Goals

### Primary Objectives

1. **Replace Legacy System**
   - Migrate from synchronous to async architecture
   - Improve query performance with ltree indexing
   - Add database-level security (RLS)

2. **Enable Offline Operations**
   - Support mobile apps in low-connectivity areas
   - Implement idempotency for duplicate prevention
   - Provide conflict resolution mechanisms

3. **Scale for Growth**
   - Handle 1000+ concurrent users
   - Support unlimited data growth via partitioning
   - Optimize with materialized views

4. **Improve Developer Experience**
   - Separate concerns (models, CRUD, services, routes)
   - Provide comprehensive API documentation
   - Enable easy testing and deployment

---

## 📊 System Statistics

| Metric | Value |
|--------|-------|
| **Total API Endpoints** | 124 |
| **Database Tables** | 30+ |
| **Supported Hierarchy Levels** | 6 |
| **Role Score Levels** | 9 |
| **Authentication Method** | JWT (Bearer Token) |
| **Database** | PostgreSQL 16 (Supabase) |
| **ORM** | SQLAlchemy 2.x (Async) |
| **API Framework** | FastAPI |
| **Python Version** | 3.11+ |

---

## 🏗️ Architecture Highlights

### Async-First Design

- Non-blocking I/O for 10x+ concurrency
- asyncpg driver for PostgreSQL
- Async SQLAlchemy ORM

### ltree Hierarchy

- O(log n) ancestor/descendant queries
- GIST indexing for performance
- Path-based scoping (e.g., `org.234.kw.iln.ile.001`)

### Row-Level Security (RLS)

- Database-enforced access control
- Scope injection via session variables
- Cannot be bypassed at application level

### Table Partitioning

- Yearly partitions for `counts`, `offerings`, `attendance`
- Automatic partition creation
- Improved query performance on historical data

### Score-Based Access Control

```
Score 1-2: Worker/Usher     → Location only
Score 3:   Location Pastor  → Location only
Score 4:   Group Pastor     → All locations in group
Score 5:   Regional Pastor  → All groups in region
Score 6:   State Pastor     → All regions in state
Score 7:   National Admin   → All states in nation
Score 8:   Continental      → All nations
Score 9:   Global Admin     → Entire organization
```

---

## 🛠️ Technology Stack

### Backend

- **Language:** Python 3.11+
- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.x (async)
- **Database:** PostgreSQL 16 (Supabase)
- **Driver:** asyncpg
- **Validation:** Pydantic v2
- **Authentication:** PyJWT
- **Password Hashing:** bcrypt
- **Migrations:** Alembic
- **Scheduler:** APScheduler
- **Testing:** pytest + pytest-asyncio

### Frontend (Planned)

- **Usher App:** KivyMD / Flutter
- **Fellowship App:** KivyMD / Flutter
- **Admin App:** FastStrap (FastHTML)
- **Public Website:** FastStrap / FastHTML

### Infrastructure

- **Database:** Supabase (PostgreSQL + Storage)
- **File Storage:** Supabase Storage
- **Deployment:** FastAPI Cloud / VPS
- **Background Jobs:** APScheduler

---

## 📈 Project Status

### ✅ Completed Features

- [x] Authentication & Authorization
- [x] User & Worker Management
- [x] Hierarchy Management (6 levels)
- [x] RBAC with Score-based Access
- [x] Data Collection (Counts, Offerings, Records, Attendance)
- [x] Offline Sync with Idempotency
- [x] Fellowship Features (Members, Testimonies, Prayers)
- [x] Media Management (Galleries, Items)
- [x] Public API (Events, Locations, Galleries)
- [x] Reports & Analytics
- [x] Password Recovery
- [x] User Approval Workflow
- [x] Notification Polling
- [x] Row-Level Security (RLS)
- [x] Table Partitioning
- [x] Audit Logging

### 🚧 Next Steps

- [ ] Deploy to FastAPI Cloud
- [ ] Mobile Applications (Usher, Fellowship, Admin)
- [ ] Public Website
- [ ] Worker Transfer Workflows
- [ ] Real-time Notifications (WebSocket)
- [ ] Caching Layer (Redis)

---

## 🤝 Contributing

### Development Workflow

1. **Read Documentation** - Familiarize yourself with architecture
2. **Set Up Environment** - Follow [Setup Guide](./docs/SETUP.md)
3. **Create Feature Branch** - `git checkout -b feature/your-feature`
4. **Write Tests** - Add tests for new features
5. **Submit Pull Request** - Include description and tests

### Code Standards

- **Python:** Follow PEP 8
- **Type Hints:** Use type annotations
- **Docstrings:** Document all public functions
- **Tests:** Maintain 80%+ coverage
- **Async:** Use async/await for I/O operations

---

## 📞 Support

### Documentation Issues

If you find errors or gaps in documentation, please:

1. Check [FAQ](./FAQ.md) and [Troubleshooting](./TROUBLESHOOTING.md)
2. Search existing issues
3. Create a new issue with details

### Technical Support

- **Email:** <meshelleva@gmail.com>
- **WhatsApp:** +234 902 995 2120
- **Slack:** Coming Soon (#dclm-dev)
- **GitHub Issues:** [Report Bug](https://github.com/dclmkwara/Church_server/issues)

---

## 📄 License

Copyright © 2026 Deeper Life Church Management System  
All rights reserved.

---

**Next Steps:**

- [📖 Read API Documentation](./docs/API_DOCUMENTATION.md)
- [🏗️ Understand Architecture](./docs/QUICK_START.md)
- [⚙️ Set Up Development Environment](./docs/SETUP.md)
