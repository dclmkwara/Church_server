"""
CRUD operations for ChurchMember.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.church_member import ChurchMember
from app.schemas.church_member import ChurchMemberCreate, ChurchMemberUpdate
from app.db.filters import scope_filter
from app.crud.idempotency import commit_idempotent, mark_existing_submission


async def create(
    db: AsyncSession,
    *,
    obj_in: ChurchMemberCreate,
    user_id: UUID,
    path: str,
) -> ChurchMember:
    """Register a new church member."""
    if obj_in.client_id:
        existing = (await db.execute(
            select(ChurchMember).where(ChurchMember.client_id == obj_in.client_id)
        )).scalars().first()
        if existing:
            return mark_existing_submission(existing)
    db_obj = ChurchMember(
        **obj_in.model_dump(exclude_unset=True),
        path=path,
        entered_by_id=user_id,
    )
    db.add(db_obj)
    return await commit_idempotent(
        db,
        db_obj,
        client_id=obj_in.client_id,
        lookup=lambda session, client_id: _get_by_client_id(session, client_id),
    )


async def _get_by_client_id(db: AsyncSession, client_id: UUID) -> Optional[ChurchMember]:
    result = await db.execute(select(ChurchMember).where(ChurchMember.client_id == client_id))
    return result.scalars().first()


async def get(db: AsyncSession, *, member_id: UUID) -> Optional[ChurchMember]:
    result = await db.execute(
        select(ChurchMember).where(ChurchMember.id == member_id)
    )
    return result.scalars().first()


async def get_by_location(
    db: AsyncSession,
    *,
    location_id: str,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
) -> List[ChurchMember]:
    """List members for a specific location, with optional status filter."""
    query = select(ChurchMember).where(
        ChurchMember.location_id == location_id,
        ChurchMember.is_deleted == False,
    )
    if status:
        query = query.where(ChurchMember.status == status)
    query = query.offset(skip).limit(limit).order_by(ChurchMember.name)
    result = await db.execute(query)
    return result.scalars().all()


async def get_multi_by_scope(
    db: AsyncSession,
    *,
    scope_path: str,
    skip: int = 0,
    limit: int = 100,
) -> List[ChurchMember]:
    """Get members within a hierarchy scope."""
    query = select(ChurchMember).where(
        scope_filter(ChurchMember.path, scope_path),
        ChurchMember.is_deleted == False,
    ).offset(skip).limit(limit).order_by(ChurchMember.name)
    result = await db.execute(query)
    return result.scalars().all()


async def update(
    db: AsyncSession,
    *,
    db_obj: ChurchMember,
    obj_in: ChurchMemberUpdate,
) -> ChurchMember:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def remove(db: AsyncSession, *, member_id: UUID) -> bool:
    """Soft-delete a church member."""
    member = await get(db, member_id=member_id)
    if not member:
        return False
    member.is_deleted = True
    member.operation = "DELETE"
    await db.commit()
    return True
