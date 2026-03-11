"""
CRUD operations for transfer and status change approvals.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.approvals import TransferRequest, StatusChangeRequest
from app.models.user import Worker, User
from app.models.location import Location, Group, Region, State


class CRUDApprovals:
    async def create_transfer(
        self,
        db: AsyncSession,
        *,
        worker_id: UUID,
        to_location_id: str,
        requested_by: UUID,
        reason: Optional[str] = None,
    ) -> TransferRequest:
        worker = (await db.execute(select(Worker).where(Worker.worker_id == worker_id))).scalars().first()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        dest = (await db.execute(select(Location).where(Location.location_id == to_location_id))).scalars().first()
        if not dest:
            raise HTTPException(status_code=404, detail="Destination location not found")

        req = TransferRequest(
            worker_id=worker.worker_id,
            from_location_id=worker.location_id,
            to_location_id=to_location_id,
            status="pending",
            reason=reason,
            requested_by=requested_by,
            path=worker.path,
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req

    async def list_transfers(
        self,
        db: AsyncSession,
        *,
        scope_path: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TransferRequest]:
        query = select(TransferRequest).where(
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        )
        if status:
            query = query.where(TransferRequest.status == status)
        query = query.offset(skip).limit(limit).order_by(TransferRequest.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()

    async def approve_transfer(
        self,
        db: AsyncSession,
        *,
        request_id: UUID,
        approver_id: UUID,
        scope_path: Optional[str] = None,
    ) -> TransferRequest:
        stmt = select(TransferRequest).where(TransferRequest.id == request_id)
        if scope_path:
            stmt = stmt.where(text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path))
        req = (await db.execute(stmt)).scalars().first()
        if not req:
            raise HTTPException(status_code=404, detail="Transfer request not found")
        if req.status != "pending":
            raise HTTPException(status_code=400, detail="Transfer request already processed")

        worker = (await db.execute(select(Worker).where(Worker.worker_id == req.worker_id))).scalars().first()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        stmt = (
            select(Location, Group, Region, State)
            .join(Group, Group.group_id == Location.group_id)
            .join(Region, Region.region_id == Group.region_id)
            .join(State, State.state_id == Region.state_id)
            .where(Location.location_id == req.to_location_id)
        )
        row = (await db.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=404, detail="Destination location not found")
        location, group, region, state = row

        worker.location_id = location.location_id
        worker.location_name = location.location_name
        worker.church_type = location.church_type
        worker.group = group.group_name
        worker.region = region.region_name
        worker.state = state.state_name
        worker.path = location.path

        if worker.user:
            worker.user.location_id = location.location_id
            worker.user.path = location.path

        req.status = "approved"
        req.approved_by = approver_id
        req.approved_at = datetime.utcnow()

        await db.commit()
        await db.refresh(req)
        return req

    async def reject_transfer(
        self,
        db: AsyncSession,
        *,
        request_id: UUID,
        approver_id: UUID,
        reason: Optional[str] = None,
        scope_path: Optional[str] = None,
    ) -> TransferRequest:
        stmt = select(TransferRequest).where(TransferRequest.id == request_id)
        if scope_path:
            stmt = stmt.where(text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path))
        req = (await db.execute(stmt)).scalars().first()
        if not req:
            raise HTTPException(status_code=404, detail="Transfer request not found")
        if req.status != "pending":
            raise HTTPException(status_code=400, detail="Transfer request already processed")

        req.status = "rejected"
        req.approved_by = approver_id
        req.approved_at = datetime.utcnow()
        req.reason = reason or req.reason

        await db.commit()
        await db.refresh(req)
        return req

    async def create_status_change(
        self,
        db: AsyncSession,
        *,
        worker_id: UUID,
        new_status: str,
        requested_by: UUID,
        reason: Optional[str] = None,
    ) -> StatusChangeRequest:
        worker = (await db.execute(select(Worker).where(Worker.worker_id == worker_id))).scalars().first()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        req = StatusChangeRequest(
            worker_id=worker.worker_id,
            old_status=worker.status,
            new_status=new_status,
            status="pending",
            reason=reason,
            requested_by=requested_by,
            path=worker.path,
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req

    async def list_status_changes(
        self,
        db: AsyncSession,
        *,
        scope_path: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[StatusChangeRequest]:
        query = select(StatusChangeRequest).where(
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        )
        if status:
            query = query.where(StatusChangeRequest.status == status)
        query = query.offset(skip).limit(limit).order_by(StatusChangeRequest.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()

    async def approve_status_change(
        self,
        db: AsyncSession,
        *,
        request_id: UUID,
        approver_id: UUID,
        scope_path: Optional[str] = None,
    ) -> StatusChangeRequest:
        stmt = select(StatusChangeRequest).where(StatusChangeRequest.id == request_id)
        if scope_path:
            stmt = stmt.where(text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path))
        req = (await db.execute(stmt)).scalars().first()
        if not req:
            raise HTTPException(status_code=404, detail="Status change request not found")
        if req.status != "pending":
            raise HTTPException(status_code=400, detail="Status change request already processed")

        worker = (await db.execute(select(Worker).where(Worker.worker_id == req.worker_id))).scalars().first()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        worker.status = req.new_status
        if worker.user:
            if req.new_status.lower() in {"inactive", "suspended"}:
                worker.user.is_active = False
            elif req.new_status.lower() == "active":
                worker.user.is_active = True

        req.status = "approved"
        req.approved_by = approver_id
        req.approved_at = datetime.utcnow()

        await db.commit()
        await db.refresh(req)
        return req

    async def reject_status_change(
        self,
        db: AsyncSession,
        *,
        request_id: UUID,
        approver_id: UUID,
        reason: Optional[str] = None,
        scope_path: Optional[str] = None,
    ) -> StatusChangeRequest:
        stmt = select(StatusChangeRequest).where(StatusChangeRequest.id == request_id)
        if scope_path:
            stmt = stmt.where(text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path))
        req = (await db.execute(stmt)).scalars().first()
        if not req:
            raise HTTPException(status_code=404, detail="Status change request not found")
        if req.status != "pending":
            raise HTTPException(status_code=400, detail="Status change request already processed")

        req.status = "rejected"
        req.approved_by = approver_id
        req.approved_at = datetime.utcnow()
        req.reason = reason or req.reason

        await db.commit()
        await db.refresh(req)
        return req


approvals = CRUDApprovals()
