"""
CRUD operations for transfer and status change approvals.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.approvals import TransferRequest, StatusChangeRequest
from app.models.user import Worker, User
from app.models.location import Location, Group, Region, State
from app.db.filters import scope_filter


class CRUDApprovals:
    async def create_transfer(
        self,
        db: AsyncSession,
        *,
        worker_id: UUID,
        to_location_id: str,
        requested_by: UUID,
        reason: Optional[str] = None,
        scope_path: Optional[str] = None,
    ) -> TransferRequest:
        stmt = select(Worker).where(Worker.worker_id == worker_id, Worker.is_deleted.is_(False))
        if scope_path:
            stmt = stmt.where(scope_filter(Worker.path, scope_path))
        worker = (await db.execute(stmt)).scalars().first()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        if worker.approval_status != "approved" or str(worker.status or "").lower() != "active":
            raise HTTPException(status_code=409, detail="Only active approved workers may be transferred")
        if str(worker.location_id) == str(to_location_id):
            raise HTTPException(status_code=422, detail="Destination must differ from the worker's current location")

        open_request = (await db.execute(select(TransferRequest.id).where(
            TransferRequest.worker_id == worker_id,
            TransferRequest.status.in_(("pending", "pending_region")),
        ).limit(1))).scalar_one_or_none()
        if open_request:
            raise HTTPException(status_code=409, detail="This worker already has a transfer awaiting review")

        dest = (await db.execute(select(Location).where(Location.location_id == to_location_id))).scalars().first()
        if not dest:
            raise HTTPException(status_code=404, detail="Destination location not found")
        source_context = (await db.execute(
            select(State.state_id)
            .join(Region, Region.state_id == State.state_id)
            .join(Group, Group.region_id == Region.region_id)
            .join(Location, Location.group_id == Group.group_id)
            .where(Location.location_id == worker.location_id)
        )).scalar_one_or_none()
        dest_context = (await db.execute(
            select(State.state_id)
            .join(Region, Region.state_id == State.state_id)
            .join(Group, Group.region_id == Region.region_id)
            .join(Location, Location.group_id == Group.group_id)
            .where(Location.location_id == to_location_id)
        )).scalar_one_or_none()
        if source_context is None or dest_context is None:
            raise HTTPException(status_code=422, detail="Both transfer locations must belong to a complete church hierarchy")
        if str(source_context) != str(dest_context):
            raise HTTPException(status_code=422, detail="This transfer workflow is limited to locations within one state")

        req = TransferRequest(
            worker_id=worker.worker_id,
            from_location_id=worker.location_id,
            to_location_id=to_location_id,
            status="pending",
            reason=reason,
            requested_by=requested_by,
            path=worker.path,
            current_level=3,
            workflow_stage="origin_group",
            reviews=[{
                "level": 2,
                "reviewer_id": str(requested_by),
                "action": "submit",
                "notes": reason,
                "at": datetime.now(timezone.utc).isoformat(),
            }],
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
        destination_path = select(Location.path).where(Location.location_id == TransferRequest.to_location_id).scalar_subquery()
        query = select(TransferRequest).where(or_(
            scope_filter(TransferRequest.path, scope_path),
            scope_filter(destination_path, scope_path),
        ))
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
        approver_score: int,
        approver_path: Optional[str] = None,
        scope_path: Optional[str] = None,
    ) -> TransferRequest:
        stmt = select(TransferRequest).where(TransferRequest.id == request_id)
        if scope_path:
            destination_path = select(Location.path).where(Location.location_id == TransferRequest.to_location_id).scalar_subquery()
            stmt = stmt.where(or_(scope_filter(TransferRequest.path, scope_path), scope_filter(destination_path, scope_path)))
        req = (await db.execute(stmt)).scalars().first()
        if not req:
            raise HTTPException(status_code=404, detail="Transfer request not found")
        if req.status not in ("pending", "pending_region"):
            raise HTTPException(status_code=400, detail="Transfer request already processed")
        now = datetime.now(timezone.utc)
        reviews = list(req.reviews or [])
        stage = req.workflow_stage or ("region" if req.status == "pending_region" else "origin_group")
        destination = (await db.execute(select(Location).where(Location.location_id == req.to_location_id))).scalars().first()
        origin = (await db.execute(select(Location).where(Location.location_id == req.from_location_id))).scalars().first()
        if not destination or not origin:
            raise HTTPException(status_code=409, detail="Transfer locations are no longer available")
        target_path = origin.path if stage == "origin_group" else destination.path
        if approver_path and not (str(target_path) == str(approver_path) or str(target_path).startswith(str(approver_path).rstrip(".") + ".")):
            raise HTTPException(status_code=403, detail="Reviewer is outside the location hierarchy required for this stage")
        if stage == "origin_group":
            if approver_score != 3:
                raise HTTPException(status_code=403, detail="The originating Group Pastor must approve first")
            req.group_approved_by = approver_id
            req.group_approved_at = now
            req.group_note = "Originating Group Pastor approval"
            req.workflow_stage = "receiving_location"
            req.current_level = 2
            req.status = "pending_region"
            reviews.append({"level": 3, "reviewer_id": str(approver_id), "action": "approve_origin_group", "notes": None, "at": now.isoformat()})
            req.reviews = reviews
            await db.commit()
            await db.refresh(req)
            return req

        if stage == "receiving_location":
            if approver_score != 2:
                raise HTTPException(status_code=403, detail="The receiving Location Pastor must accept the transfer")
            req.receiving_location_approved_by = approver_id
            req.receiving_location_approved_at = now
            req.receiving_location_note = "Receiving Location Pastor acceptance"
            req.workflow_stage = "receiving_group"
            req.current_level = 3
            reviews.append({"level": 2, "reviewer_id": str(approver_id), "action": "accept_receiving_location", "notes": None, "at": now.isoformat()})
            req.reviews = reviews
            await db.commit()
            await db.refresh(req)
            return req

        if stage == "receiving_group":
            if approver_score != 3:
                raise HTTPException(status_code=403, detail="The receiving Group Pastor must approve the transfer")
            req.receiving_group_approved_by = approver_id
            req.receiving_group_approved_at = now
            req.receiving_group_note = "Receiving Group Pastor approval"
            req.workflow_stage = "region"
            req.current_level = 4
            req.status = "pending_region"
            reviews.append({"level": 3, "reviewer_id": str(approver_id), "action": "approve_receiving_group", "notes": None, "at": now.isoformat()})
            req.reviews = reviews
            await db.commit()
            await db.refresh(req)
            return req

        if stage != "region" or approver_score < 4:
            raise HTTPException(status_code=403, detail="Regional Pastor approval is required after receiving leadership approvals")
        worker = (await db.execute(select(Worker).where(
            Worker.worker_id == req.worker_id, Worker.is_deleted.is_(False)
        ).with_for_update())).scalars().first()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        if str(worker.location_id) != str(req.from_location_id):
            raise HTTPException(status_code=409, detail="Worker's current location changed after this request was submitted")

        row = (await db.execute(
            select(Location, Group, Region, State)
            .join(Group, Group.group_id == Location.group_id)
            .join(Region, Region.region_id == Group.region_id)
            .join(State, State.state_id == Region.state_id)
            .where(Location.location_id == req.to_location_id, Location.is_deleted.is_(False))
        )).first()
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

        linked_user = (await db.execute(select(User).where(
            User.worker_id == worker.worker_id, User.is_deleted.is_(False)
        ))).scalars().first()
        if linked_user:
            linked_user.location_id = location.location_id
            linked_user.path = location.path

        req.region_approved_by = approver_id
        req.region_approved_at = now
        req.approved_by = approver_id
        req.approved_at = now
        req.current_level = 4
        req.status = "approved"
        reviews.append({"level": approver_score, "reviewer_id": str(approver_id), "action": "approve_region_and_complete", "notes": None, "at": now.isoformat()})
        req.reviews = reviews
        await db.commit()
        if linked_user:
            from app.core.auth_cache import invalidate_user_cache
            invalidate_user_cache(str(linked_user.user_id))
        await db.refresh(req)
        return req

    async def reject_transfer(
        self,
        db: AsyncSession,
        *,
        request_id: UUID,
        approver_id: UUID,
        approver_score: int,
        approver_path: Optional[str] = None,
        reason: Optional[str] = None,
        scope_path: Optional[str] = None,
    ) -> TransferRequest:
        stmt = select(TransferRequest).where(TransferRequest.id == request_id)
        if scope_path:
            destination_path = select(Location.path).where(Location.location_id == TransferRequest.to_location_id).scalar_subquery()
            stmt = stmt.where(or_(scope_filter(TransferRequest.path, scope_path), scope_filter(destination_path, scope_path)))
        req = (await db.execute(stmt)).scalars().first()
        if not req:
            raise HTTPException(status_code=404, detail="Transfer request not found")
        if req.status not in ("pending", "pending_region"):
            raise HTTPException(status_code=400, detail="Transfer request already processed")
        if approver_score < req.current_level:
            raise HTTPException(status_code=403, detail="This transfer requires approval from its current review level")
        if req.current_level == 2 and approver_score != 2:
            raise HTTPException(status_code=403, detail="The receiving Location Pastor must decide at this stage")
        if approver_path:
            stage = req.workflow_stage or "origin_group"
            target_id = req.from_location_id if stage == "origin_group" else req.to_location_id
            target = (await db.execute(select(Location).where(Location.location_id == target_id))).scalars().first()
            if not target or not (str(target.path) == str(approver_path) or str(target.path).startswith(str(approver_path).rstrip(".") + ".")):
                raise HTTPException(status_code=403, detail="Reviewer is outside the location hierarchy required for this stage")
        if not reason or len(reason.strip()) < 10:
            raise HTTPException(status_code=422, detail="A rejection reason of at least 10 characters is required")
        now = datetime.now(timezone.utc)
        reviews = list(req.reviews or [])
        reviews.append({"level": approver_score, "reviewer_id": str(approver_id), "action": "reject", "notes": reason.strip(), "at": now.isoformat()})
        req.status = "rejected"
        req.approved_by = approver_id
        req.approved_at = now
        req.rejection_reason = reason.strip()
        req.reviews = reviews

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
        scope_path: Optional[str] = None,
    ) -> StatusChangeRequest:
        stmt = select(Worker).where(Worker.worker_id == worker_id)
        if scope_path:
            stmt = stmt.where(scope_filter(Worker.path, scope_path))
        worker = (await db.execute(stmt)).scalars().first()
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
            scope_filter(StatusChangeRequest.path, scope_path)
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
            stmt = stmt.where(scope_filter(StatusChangeRequest.path, scope_path))
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
            stmt = stmt.where(scope_filter(StatusChangeRequest.path, scope_path))
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
      - submit: location pastor (score >= 2) in worker's scope
      - review (approve/reject/escalate): user whose score == current_level
      - max escalation level is 5 (State Overseer); state is final
    """

    async def submit(
        self,
        db: AsyncSession,
        *,
        worker_id: UUID,
        reason: str,
        requested_by: UUID,
        scope_path: Optional[str] = None,
    ) -> WorkerRemovalRequest:
        """A location pastor submits a removal request for group review."""
        stmt = select(Worker).where(Worker.worker_id == worker_id, Worker.is_deleted.is_(False)).with_for_update()
        if scope_path:
            stmt = stmt.where(scope_filter(Worker.path, scope_path))
        worker = (await db.execute(stmt)).scalars().first()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        if worker.approval_status != "approved" or str(worker.status or "").lower() not in {"active", "suspended"}:
            raise HTTPException(status_code=409, detail="Only active or suspended approved workers may enter removal review")

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

        linked_user = (await db.execute(select(User).where(
            User.worker_id == worker.worker_id, User.is_deleted.is_(False)
        ).with_for_update())).scalars().first()
        now = datetime.now(timezone.utc)
        old_status = worker.status or "Active"
        old_user_active = linked_user.is_active if linked_user else None
        worker.status = "Suspended"
        if linked_user:
            linked_user.is_active = False

        req = WorkerRemovalRequest(
            worker_id=worker.worker_id,
            reason=reason,
            status="pending",
            current_level=3,  # Sent to Group Pastor (score 3) immediately
            reviews=[{
                "level": 2,
                "reviewer_id": str(requested_by),
                "action": "suspend_and_submit",
                "notes": reason,
                "at": now.isoformat(),
            }],
            requested_by=requested_by,
            path=worker.path,
            worker_status_before_request=old_status,
            user_was_active_before_request=old_user_active,
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
            scope_filter(WorkerRemovalRequest.path, scope_path)
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
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        worker.is_deleted = True
        worker.approval_status = "removed"
        worker.status = "Removed"
        linked_user = (await db.execute(select(User).where(
            User.worker_id == worker.worker_id, User.is_deleted.is_(False)
        ).with_for_update())).scalars().first()
        if linked_user:
            linked_user.is_active = False

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

        worker = (await db.execute(select(Worker).where(
            Worker.worker_id == req.worker_id, Worker.is_deleted.is_(False)
        ).with_for_update())).scalars().first()
        if worker:
            worker.status = req.worker_status_before_request or "Active"
            linked_user = (await db.execute(select(User).where(
                User.worker_id == worker.worker_id, User.is_deleted.is_(False)
            ).with_for_update())).scalars().first()
            if linked_user and req.user_was_active_before_request is not None:
                linked_user.is_active = req.user_was_active_before_request

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
        Maximum escalation ceiling is score 5 (State Overseer).
        """
        req = await self._get_in_scope(db, request_id=request_id, scope_path=scope_path)
        self._assert_pending_or_escalated(req)
        if escalator_score != req.current_level:
            raise HTTPException(status_code=403, detail="Only the current review level may escalate this request")

        next_level = req.current_level + 1
        if next_level > 5:
            raise HTTPException(status_code=400, detail="Cannot escalate beyond State Overseer (score 5)")

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
            scope_filter(WorkerRemovalRequest.path, scope_path),
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
