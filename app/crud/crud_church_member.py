"""
CRUD operations for ChurchMember.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.church_member import ChurchMember
from app.schemas.church_member import ChurchMemberCreate, ChurchMemberUpdate


async def create(
    db: AsyncSession,
    *,
    obj_in: ChurchMemberCreate,
    user_id: UUID,
    path: str,
) -> ChurchMember:
    """Register a new church member."""
    db_obj = ChurchMember(
        **obj_in.model_dump(exclude_unset=True),
        path=path,
        entered_by_id=user_id,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


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
        text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
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
