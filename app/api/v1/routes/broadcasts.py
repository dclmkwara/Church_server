"""Hierarchy-scoped downward broadcasts with dynamic recipient resolution."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.filters import scope_or_ancestor_filter
from app.models.broadcast import BroadcastMessage
from app.models.core import _LTREE
from app.models.location import Group, Location, Region, State
from app.models.user import User, Role, RoleScore, user_roles

router = APIRouter()


class BroadcastCreate(BaseModel):
    target_level: Literal["state", "region", "group", "location"]
    target_path: str = Field(min_length=3, max_length=255)
    audience: Literal["all_users", "pastors"] = "all_users"
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    priority: Literal["low", "normal", "high"] = "normal"


class BroadcastResponse(BaseModel):
    id: UUID
    target_level: str
    target_path: str = Field(validation_alias="path", serialization_alias="target_path")
    audience: str
    title: str
    content: str
    priority: str
    sender_role_score: str
    sent_at: datetime
    recipient_count: int | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


_TARGET_MODEL = {"state": State, "region": Region, "group": Group, "location": Location}


@router.post("/", response_model=BroadcastResponse, status_code=201, dependencies=[Depends(deps.PermissionChecker("announcements:manage"))])
async def create_broadcast(
    payload: BroadcastCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    score = deps.highest_role_score(current_user)
    minimum = {"location": 3, "group": 3, "region": 4, "state": 5}[payload.target_level]
    if score < minimum or score < 3:
        raise HTTPException(status_code=403, detail="Your role cannot broadcast to this hierarchy level")
    target = (await db.execute(
        select(_TARGET_MODEL[payload.target_level]).where(
            cast(_TARGET_MODEL[payload.target_level].path, _LTREE()) == cast(payload.target_path, _LTREE())
        )
    )).scalars().first()
    if target is None:
        raise HTTPException(status_code=404, detail="Broadcast target is not a canonical church hierarchy node")
    deps.ensure_path_in_scope(current_user, target.path, detail="Broadcast target is outside your jurisdiction")
    message = BroadcastMessage(
        sender_id=current_user.user_id,
        sender_role_score=str(score),
        target_level=payload.target_level,
        path=str(target.path),
        audience=payload.audience,
        title=payload.title.strip(),
        content=payload.content.strip(),
        priority=payload.priority,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


@router.get("/", response_model=list[BroadcastResponse], dependencies=[Depends(deps.PermissionChecker("announcements:read"))])
async def list_broadcasts(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    scope_path = deps.effective_scope_path(current_user)
    rows = (await db.execute(
        select(BroadcastMessage).where(
            scope_or_ancestor_filter(BroadcastMessage.path, scope_path),
            BroadcastMessage.is_active.is_(True),
        ).order_by(BroadcastMessage.sent_at.desc()).limit(limit)
    )).scalars().all()
    response = []
    role_score = deps.highest_role_score(current_user)
    for row in rows:
        if role_score <= 2 and not deps.path_in_scope(str(row.path), str(current_user.path)):
            continue
        if row.audience == "pastors" and role_score < 2:
            continue
        # Resolve counts only for governance users, whose database session has
        # authority to read the complete target jurisdiction.
        if role_score < 3:
            response.append(row)
            continue
        recipient_filter = cast(User.path, _LTREE()).op("<@")(cast(row.path, _LTREE()))
        recipient_query = select(User.user_id).where(
            recipient_filter,
            User.is_active.is_(True),
            User.approval_status == "approved",
            User.is_deleted.is_(False),
        )
        recipients = (await db.execute(recipient_query)).scalars().all()
        if row.audience == "pastors":
            # A pastor audience contains governance roles (scores 2+) only.
            recipients = (await db.execute(
                select(User.user_id).join(user_roles, user_roles.c.user_id == User.user_id)
                .join(Role, Role.id == user_roles.c.role_id)
                .join(RoleScore, RoleScore.id == Role.score_id)
                .where(
                    recipient_filter, User.is_active.is_(True), User.approval_status == "approved",
                    User.is_deleted.is_(False), RoleScore.score >= 2,
                ).distinct()
            )).scalars().all()
        response.append({
            "id": row.id, "target_level": row.target_level, "target_path": str(row.path),
            "audience": row.audience, "title": row.title, "content": row.content,
            "priority": row.priority, "sender_role_score": row.sender_role_score,
            "sent_at": row.sent_at, "recipient_count": len(recipients),
        })
    return response
