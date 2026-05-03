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
            text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
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
            stmt = stmt.where(text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path))
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
            stmt = stmt.where(text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path))
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
            text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
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
            stmt = stmt.where(text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path))
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
            stmt = stmt.where(text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path))
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


# ──────────────────────────────────────────────────────────────
# Worker Removal Request CRUD
# ──────────────────────────────────────────────────────────────

from app.models.approvals import WorkerRemovalRequest  # noqa: E402 (after class def)


class CRUDRemoval:
    """
    Manages the escalating worker removal request workflow.

    Level rules:
      - submit: any user with score >= 3 in worker's scope
      - review (approve/reject/escalate): user whose score == current_level
      - max escalation level is 6 (State Overseer); above 6 approve directly
    """

    async def submit(
        self,
        db: AsyncSession,
        *,
        worker_id: UUID,
        reason: str,
        requested_by: UUID,
    ) -> WorkerRemovalRequest:
        """Level 3 submits a removal request. Starts at current_level=4 (Group Pastor reviews)."""
        worker = (await db.execute(select(Worker).where(Worker.worker_id == worker_id))).scalars().first()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        # Check no open request already exists for this worker
        existing = (await db.execute(
            select(WorkerRemovalRequest).where(
                WorkerRemovalRequest.worker_id == worker_id,
                WorkerRemovalRequest.status.in_(["pending", "escalated"])
            )
        )).scalars().first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="An open removal request already exists for this worker"
            )

        req = WorkerRemovalRequest(
            worker_id=worker.worker_id,
            reason=reason,
            status="pending",
            current_level=4,  # Sent to Group Pastor (level 4) immediately
            reviews=[],
            requested_by=requested_by,
            path=worker.path,
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req

    async def list_requests(
        self,
        db: AsyncSession,
        *,
        scope_path: str,
        status: Optional[str] = None,
        current_level: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkerRemovalRequest]:
        """List removal requests within the caller's scope, optionally filtered by status or level."""
        query = select(WorkerRemovalRequest).where(
            text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        )
        if status:
            query = query.where(WorkerRemovalRequest.status == status)
        if current_level is not None:
            query = query.where(WorkerRemovalRequest.current_level == current_level)
        query = query.offset(skip).limit(limit).order_by(WorkerRemovalRequest.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()

    async def get(self, db: AsyncSession, *, request_id: UUID) -> Optional[WorkerRemovalRequest]:
        result = await db.execute(
            select(WorkerRemovalRequest).where(WorkerRemovalRequest.id == request_id)
        )
        return result.scalars().first()

    async def approve(
        self,
        db: AsyncSession,
        *,
        request_id: UUID,
        approver_id: UUID,
        approver_score: int,
        scope_path: str,
        notes: Optional[str] = None,
    ) -> WorkerRemovalRequest:
        """
        Approve a removal request. Soft-deletes the worker.
        Only allowed if approver's score >= current_level.
        """
        req = await self._get_in_scope(db, request_id=request_id, scope_path=scope_path)
        self._assert_pending_or_escalated(req)
        self._assert_authority(approver_score, req.current_level)

        # Append review entry
        import datetime as dt_module
        reviews = list(req.reviews or [])
        reviews.append({
            "level": approver_score,
            "reviewer_id": str(approver_id),
            "action": "approve",
            "notes": notes,
            "at": dt_module.datetime.utcnow().isoformat(),
        })
        req.reviews = reviews
        req.status = "approved"
        req.decided_by = approver_id
        req.decided_at = dt_module.datetime.utcnow()

        # Soft-delete the worker
        worker = (await db.execute(select(Worker).where(Worker.worker_id == req.worker_id))).scalars().first()
        if worker:
            worker.is_deleted = True
            worker.approval_status = "removed"
            # Also deactivate the linked user account if exists
            if worker.user:
                worker.user.is_active = False

        await db.commit()
        await db.refresh(req)
        return req

    async def reject(
        self,
        db: AsyncSession,
        *,
        request_id: UUID,
        approver_id: UUID,
        approver_score: int,
        scope_path: str,
        notes: Optional[str] = None,
    ) -> WorkerRemovalRequest:
        """Reject a removal request. Worker stays active."""
        req = await self._get_in_scope(db, request_id=request_id, scope_path=scope_path)
        self._assert_pending_or_escalated(req)
        self._assert_authority(approver_score, req.current_level)

        import datetime as dt_module
        reviews = list(req.reviews or [])
        reviews.append({
            "level": approver_score,
            "reviewer_id": str(approver_id),
            "action": "reject",
            "notes": notes,
            "at": dt_module.datetime.utcnow().isoformat(),
        })
        req.reviews = reviews
        req.status = "rejected"
        req.decided_by = approver_id
        req.decided_at = dt_module.datetime.utcnow()

        await db.commit()
        await db.refresh(req)
        return req

    async def escalate(
        self,
        db: AsyncSession,
        *,
        request_id: UUID,
        escalator_id: UUID,
        escalator_score: int,
        scope_path: str,
        notes: str,
    ) -> WorkerRemovalRequest:
        """
        Escalate to the next governance level.
        Maximum escalation ceiling is level 6 (State Overseer).
        """
        req = await self._get_in_scope(db, request_id=request_id, scope_path=scope_path)
        self._assert_pending_or_escalated(req)
        self._assert_authority(escalator_score, req.current_level)

        next_level = req.current_level + 1
        if next_level > 6:
            raise HTTPException(status_code=400, detail="Cannot escalate beyond State Overseer (level 6)")

        import datetime as dt_module
        reviews = list(req.reviews or [])
        reviews.append({
            "level": escalator_score,
            "reviewer_id": str(escalator_id),
            "action": "escalate",
            "notes": notes,
            "escalated_to_level": next_level,
            "at": dt_module.datetime.utcnow().isoformat(),
        })
        req.reviews = reviews
        req.status = "escalated"
        req.current_level = next_level
        req.escalated_by = escalator_id
        req.escalated_at = dt_module.datetime.utcnow()
        req.escalation_notes = notes

        await db.commit()
        await db.refresh(req)
        return req

    # ── Private helpers ─────────────────────────────────────────

    async def _get_in_scope(
        self, db: AsyncSession, *, request_id: UUID, scope_path: str
    ) -> WorkerRemovalRequest:
        stmt = select(WorkerRemovalRequest).where(
            WorkerRemovalRequest.id == request_id,
            text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
        )
        req = (await db.execute(stmt)).scalars().first()
        if not req:
            raise HTTPException(status_code=404, detail="Removal request not found or outside your scope")
        return req

    @staticmethod
    def _assert_pending_or_escalated(req: WorkerRemovalRequest) -> None:
        if req.status not in ("pending", "escalated"):
            raise HTTPException(status_code=400, detail=f"Request already {req.status}")

    @staticmethod
    def _assert_authority(approver_score: int, current_level: int) -> None:
        if approver_score < current_level:
            raise HTTPException(
                status_code=403,
                detail=f"This request requires a level {current_level}+ user to action"
            )


removal = CRUDRemoval()
