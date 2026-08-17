# Scaling Decision

## Purpose

This document records the current architecture decision for the DCLM church management system so future performance work stays aligned with the same plan.

It is based on direct inspection of the current backend and admin frontend codebases, not on a generic template.

## Current Decision

The system should remain a **modular monolith** for now.

We are **not** adopting microservices at this stage as the primary performance strategy.

Instead, current work should focus on:

1. reducing first-load payloads
2. reducing repeated API calls
3. reducing repeated database work
4. tightening slow analytics and reporting queries
5. using caching and background processing where appropriate
6. strengthening domain boundaries inside the existing codebase

## Why This Decision Was Made

### 1. The backend is still one deployable application boundary

The current backend is a single FastAPI application with one app entrypoint and one router mounting surface:

- [app/main.py](../app/main.py)

This means the system is still operationally one service, even though it contains many domains.

### 2. The codebase already has strong internal domain separation

The backend already separates concerns by domain:

- route modules in `app/api/v1/routes/*`
- service modules in `app/services/*`
- CRUD modules in `app/crud/*`
- models in `app/models/*`
- schemas in `app/schemas/*`

Examples:

- `auth`, `users`, `workers`, `hierarchy`
- `counts`, `offerings`, `attendance`, `records`
- `reports`, `statistics`, `dashboard`
- `approvals`, `notifications`, `sync`, `system`, `public`

This is a strong sign that the right next move is to improve internal boundaries and performance, not to split deployment boundaries prematurely.

### 3. The admin frontend is also organized around the same domains

The admin frontend mirrors backend domains through:

- route modules in `dclm_admin/routes/*`
- communication/service modules in `dclm_admin/communication/*`

Important examples:

- [dclm_admin/routes/dashboard.py](../../FastHTML/Admin-Frontend/dclm_admin/routes/dashboard.py)
- [dclm_admin/communication/dashboard_service.py](../../FastHTML/Admin-Frontend/dclm_admin/communication/dashboard_service.py)

This symmetry is useful and should be preserved.

### 4. The current performance bottlenecks are not caused by a monolith boundary

Recent investigation showed the main problems were:

- dashboard first-load overfetching
- too many API calls from the frontend
- backend bootstrap computing too many analytics slices at once
- expensive reporting and aggregation queries
- repeated data retrieval across related views

These are usually solved faster by:

- better endpoint shaping
- caching
- query optimization
- section-aware loading
- summary-first rendering

They are **not** automatically solved by microservices.

### 5. Dashboard and reporting are highly cross-domain

The dashboard bootstrap route and analytics services aggregate data from several domains:

- members
- workers
- records
- counts
- attendance
- programs
- statistics

Relevant files:

- [app/api/v1/routes/dashboard.py](../app/api/v1/routes/dashboard.py)
- [app/services/dashboard_service.py](../app/services/dashboard_service.py)

If these were split into independent services too early, the system would likely replace local SQL/database aggregation with:

- more network calls
- cross-service read composition
- duplicated read models
- eventual consistency complexity

That would increase system complexity before it guarantees meaningful speed gains.

## What We Mean By "Modular Monolith"

For this project, modular monolith means:

- one main backend deployment
- one main transactional database
- clear internal domain ownership
- domain-focused route/service/CRUD layering
- selective background workers where needed
- no premature service extraction for core transactional domains

It does **not** mean "leave everything coupled."

It means the codebase should become easier to scale and reason about **inside the current application boundary** first.

## Recommended Internal Domain Boundaries

These should guide future refactors.

### 1. Identity and access

- auth
- recovery
- RBAC
- user approval

### 2. People and hierarchy

- users
- workers
- members
- hierarchy
- locations
- fellowships
- official appointments

### 3. Church data capture

- counts
- offerings
- tithes
- attendance
- records
- newcomers
- converts

### 4. Workflows and approvals

- approvals
- transfers
- status changes
- removal requests
- inbox-facing approval actions

### 5. Reporting and analytics

- dashboard
- reports
- statistics
- trend series
- cross-scope breakdowns

### 6. Communication and public channels

- announcements
- notifications
- public intake
- media

### 7. Platform and operations

- sync
- system
- app versions
- scheduler-driven tasks

## What We Should Optimize First

This is the active performance order of operations for the project.

### Priority 1: First-load UX and payload shaping

Keep making the initial admin experience smaller and faster.

Examples:

- summary-first dashboard rendering
- defer non-critical panels
- role-aware dashboard payloads
- section-aware bootstrap responses

### Priority 2: Query and aggregation cost

Reduce slow or repeated database work in:

- dashboard bootstrap
- reports
- statistics
- cross-scope analytics

Typical techniques:

- query simplification
- index review
- pre-aggregated read models where justified
- removing duplicated fetch patterns

### Priority 3: Caching

Prefer safe caching for read-heavy analytics and reference data.

Examples already present in the frontend:

- request cache
- TTL cache
- section-aware bootstrap reuse

The backend can progressively add more read-side caching where it is safe and measurable.

### Priority 4: Background work

Move non-interactive work off the request path.

Examples:

- notifications
- email dispatch
- report generation
- sync-related processing
- data refresh jobs

## What We Should Not Do Yet

These should be treated as "not now" decisions unless conditions change.

### 1. Do not split core transactional domains into separate services yet

That includes:

- auth
- people
- workers
- members
- hierarchy
- counts
- attendance
- records

### 2. Do not create microservices just to solve dashboard slowness

Dashboard slowness should be solved with:

- fewer calls
- smaller payloads
- cheaper queries
- better caching

### 3. Do not split by frontend page

Pages are not service boundaries.

The correct boundaries are business domains and scaling behavior, not screen names.

## When Microservices Would Start Making Sense

Microservices should only be considered when several of the following become true:

1. one subsystem has clearly different scaling pressure from the rest
2. one subsystem must be deployed independently very often
3. multiple teams need hard ownership boundaries
4. the system has mature tracing, monitoring, retries, and service auth
5. eventual consistency is acceptable for the extracted domain

## First Candidate for Future Extraction

If a service is extracted later, the best first candidate is:

**Reporting / analytics / read-model aggregation**

Reasons:

- it is read-heavy
- it is aggregation-heavy
- it already crosses many domains
- it has different performance characteristics from transactional CRUD
- it is the most likely place to justify separate scaling or specialized infrastructure later

This is a much safer first extraction than splitting auth or hierarchy.

## Signals That Would Trigger Reconsideration

Revisit the architecture decision if any of these become true:

1. dashboard/reporting traffic becomes disproportionately expensive compared with operational traffic
2. notification/sync workloads need separate runtime scaling
3. deployment risk becomes too high because unrelated domains keep colliding
4. multiple teams begin changing separate domains independently and frequently
5. one domain requires specialized storage or compute patterns that no longer fit the monolith well

## Practical Rule For Current Work

When improving this project, prefer this order:

1. improve payload shape
2. reduce frontend call count
3. reduce backend query count
4. cache repeatable reads
5. move non-interactive work to background jobs
6. strengthen internal domain boundaries
7. only then consider service extraction

## Current Performance Focus

For the present phase of work, the project should focus on:

- faster admin dashboard first load
- lighter governance/super-admin paths
- fewer analytics calls
- smaller dashboard bootstrap payloads
- cheaper reports/statistics queries
- keeping the frontend and backend aligned on role-aware loading

## Status

This is the current active architecture decision unless it is replaced by a newer documented decision.
