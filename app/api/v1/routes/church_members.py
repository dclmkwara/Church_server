"""
API routes for ChurchMember — congregation member registry at location level.

POST   /api/v1/members                — Register new member
GET    /api/v1/members                — List members in scope
GET    /api/v1/members/{member_id}    — Get single member
PUT    /api/v1/members/{member_id}    — Update member
DELETE /api/v1/members/{member_id}    — Soft-delete member
"""
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_church_member
from app.models.user import User
from app.schemas.church_member import ChurchMemberCreate, ChurchMemberUpdate, ChurchMemberResponse

router = APIRouter()


@router.post(
    "",
    response_model=ChurchMemberResponse,
    status_code=201,
    tags=["Records"],
    dependencies=[Depends(deps.PermissionChecker("records:create"))],
)
async def register_church_member(
    *,
    db: AsyncSession = Depends(deps.get_db),
    member_in: ChurchMemberCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Register a new congregation member at a location.

    Only location pastors and above can register members.
    The member's path is derived from the current user's scope path.
    """
    location = await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=member_in.location_id,
        detail="Member location outside your scope",
    )
    return await crud_church_member.create(
        db, obj_in=member_in, user_id=current_user.user_id, path=str(location.path)
    )


@router.get(
    "",
    response_model=List[ChurchMemberResponse],
    tags=["Records"],
    dependencies=[Depends(deps.PermissionChecker("records:read"))],
)
async def list_church_members(
    *,
    db: AsyncSession = Depends(deps.get_db),
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    status: Optional[str] = Query(None, description="Filter by status: active|inactive|transferred|deceased"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    List congregation members within the user's scope.
    """
    if location_id:
        await deps.get_location_in_scope(
            db,
            current_user=current_user,
            location_id=location_id,
            detail="Member location outside your scope",
        )
        return await crud_church_member.get_by_location(
            db, location_id=location_id, skip=skip, limit=limit, status=status
        )
    scope_path = deps.resolve_scope_path(current_user)
    return await crud_church_member.get_multi_by_scope(
        db, scope_path=scope_path, skip=skip, limit=limit
    )


@router.get(
    "/{member_id}",
    response_model=ChurchMemberResponse,
    tags=["Records"],
    dependencies=[Depends(deps.PermissionChecker("records:read"))],
)
async def get_church_member(
    member_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    member = await crud_church_member.get(db, member_id=member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    deps.ensure_path_in_scope(current_user, member.path, detail="Member outside your scope")
    return member


@router.put(
    "/{member_id}",
    response_model=ChurchMemberResponse,
    tags=["Records"],
    dependencies=[Depends(deps.PermissionChecker("records:update"))],
)
async def update_church_member(
    member_id: UUID,
    member_in: ChurchMemberUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    member = await crud_church_member.get(db, member_id=member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    deps.ensure_path_in_scope(current_user, member.path, detail="Member outside your scope")
    return await crud_church_member.update(db, db_obj=member, obj_in=member_in)


@router.delete(
    "/{member_id}",
    status_code=204,
    tags=["Records"],
    dependencies=[Depends(deps.PermissionChecker("records:delete"))],
)
async def delete_church_member(
    member_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> None:
    member = await crud_church_member.get(db, member_id=member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    deps.ensure_path_in_scope(current_user, member.path, detail="Member outside your scope")
    deleted = await crud_church_member.remove(db, member_id=member_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Member not found")
    return None
