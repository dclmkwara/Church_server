from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.api import deps
from app.models.user import User
from app.models.audit import AuditLog
from app.models.programs import ProgramDomain, ProgramType
from pydantic import BaseModel

router = APIRouter()

class SystemMetadata(BaseModel):
    program_domains: List[dict]
    program_types: List[dict]
    server_time: datetime

class AuditLogResponse(BaseModel):
    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    ts_utc: datetime
    ip_address: str | None
    
    class Config:
        from_attributes = True

@router.get("/meta", response_model=SystemMetadata)
async def get_system_metadata(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get system metadata including program domains and types.
    """
    # Get all program domains
    domains_stmt = select(ProgramDomain)
    domains_result = await db.execute(domains_stmt)
    domains = domains_result.scalars().all()
    
    # Get all program types
    types_stmt = select(ProgramType)
    types_result = await db.execute(types_stmt)
    types = types_result.scalars().all()
    
    return SystemMetadata(
        program_domains=[{"id": d.id, "slug": d.slug, "name": d.name} for d in domains],
        program_types=[{"id": t.id, "slug": t.slug, "name": t.name, "domain_id": t.domain_id} for t in types],
        server_time=datetime.utcnow()
    )

@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get audit logs (admin only).
    TODO: Add permission check for admin role.
    """
    stmt = select(AuditLog).order_by(AuditLog.ts_utc.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    audit_logs = [AuditLogResponse(
        id=str(log.id),
        user_id=str(log.user_id),
        action=log.action,
        resource_type=log.resource_type,
        resource_id=str(log.resource_id) if log.resource_id else "",
        ts_utc=log.ts_utc,
        ip_address=log.ip_address
    ) for log in logs]
    
    return audit_logs


# System Utilities
@router.get("/metrics")
async def get_system_metrics(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get system performance metrics.
    
    Returns database statistics, API performance, and system health indicators.
    Requires admin access.
    """
    # Check if user has admin privileges (score >= 7)
    if not current_user.roles or max(r.score_value for r in current_user.roles) < 7:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from sqlalchemy import text, func
    from app.models.data_collection import Count, Offering
    from app.models.user import User as UserModel, Worker
    from app.models.location import Location
    
    # Database statistics
    counts_total = await db.execute(select(func.count(Count.id)))
    offerings_total = await db.execute(select(func.count(Offering.id)))
    users_total = await db.execute(select(func.count(UserModel.user_id)))
    workers_total = await db.execute(select(func.count(Worker.worker_id)))
    locations_total = await db.execute(select(func.count(Location.id)))
    
    return {
        "database": {
            "tables": {
                "counts": counts_total.scalar(),
                "offerings": offerings_total.scalar(),
                "users": users_total.scalar(),
                "workers": workers_total.scalar(),
                "locations": locations_total.scalar()
            }
        },
        "api": {
            "version": "1.0.0",
            "total_endpoints": 130
        },
        "system": {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }
    }


@router.post("/seed")
async def seed_database(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    confirm: bool = Query(False, description="Confirm seed operation")
):
    """
    Seed database with initial data (Development only).
    
    WARNING: This should only be used in development environments.
    Requires global admin access (score 9).
    """
    # Check if user has global admin privileges
    if not current_user.roles or max(r.score_value for r in current_user.roles) < 9:
        raise HTTPException(status_code=403, detail="Global admin access required")
    
    if not confirm:
        return {
            "message": "Seed operation requires confirmation",
            "warning": "This will add initial data to the database",
            "instructions": "Add ?confirm=true to proceed"
        }
    
    # Seed role scores (1-9)
    from app.models.user import RoleScore
    
    role_scores_data = [
        (1, "Worker", "Location level worker/usher"),
        (2, "Usher", "Location level usher"),
        (3, "LocationPastor", "Location pastor"),
        (4, "GroupPastor", "Group level pastor"),
        (5, "RegionalPastor", "Regional level pastor"),
        (6, "StatePastor", "State level pastor"),
        (7, "NationalAdmin", "National level administrator"),
        (8, "ContinentalLeader", "Continental level leader"),
        (9, "GlobalAdmin", "Global administrator")
    ]
    
    seeded_count = 0
    for score, name, desc in role_scores_data:
        existing = await db.execute(select(RoleScore).where(RoleScore.score == score))
        if not existing.scalars().first():
            role_score = RoleScore(score=score, score_name=name, description=desc)
            db.add(role_score)
            seeded_count += 1
    
    await db.commit()
    
    return {
        "status": "success",
        "message": f"Database seeded successfully. Added {seeded_count} role scores.",
        "warning": "This endpoint should be disabled in production"
    }

