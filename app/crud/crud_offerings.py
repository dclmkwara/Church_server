"""
CRUD operations for Offering records.
"""
from typing import List, Optional
from datetime import date, datetime, timedelta, UTC
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.offerings import Offering, OfferingAudit
from app.schemas.offerings import OfferingCreate, OfferingUpdate, OfferingCorrection
from app.crud.idempotency import commit_idempotent, mark_existing_submission
from app.db.filters import scope_filter
from app.crud.workflow_rules import ensure_collection_open, load_event_campaign, require_approved_worker_user, resolve_program_context, resolve_program_level
from app.core import analytics_cache


class CRUDOffering(CRUDBase[Offering, OfferingCreate, OfferingUpdate]):
    """CRUD operations for Offering model with idempotency support."""
    
    async def create(self, db: AsyncSession, *, obj_in: OfferingCreate, user_id: UUID) -> Offering:
        """Create offering with idempotency check."""
        # Check for duplicate client_id
        if obj_in.client_id:
            existing = await self.get_by_client_id(db, client_id=obj_in.client_id)
            if existing:
                return mark_existing_submission(existing)
        await require_approved_worker_user(db, user_id)
        
        # Verify event exists
        from app.crud.crud_programs import program_event
        event = await program_event.get(db, id=obj_in.event_id) if obj_in.event_id else None
        if obj_in.event_id and not event:
            raise HTTPException(status_code=404, detail="Event not found")
        program_domain_id, program_type_id = await resolve_program_context(db, event=event, program_domain=obj_in.program_domain, program_type=obj_in.program_type)
        program_level = resolve_program_level(event=event, program_level=obj_in.program_level)
        if not event and str(obj_in.program_domain or "").lower() == "crusade":
            raise HTTPException(status_code=400, detail="Crusade financial entries must be linked to the scheduled event")
        if event:
            campaign = await load_event_campaign(db, event)
            ensure_collection_open(event, campaign, kind="financial entry")

        from app.crud.crud_location import location as crud_location
        location = await crud_location.get(db, obj_in.location_id)
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")

        event_path = str(event.path) if event else None
        location_path = str(location.path)
        if event_path and not (location_path == event_path or location_path.startswith(f"{event_path}.")):
            raise HTTPException(
                status_code=400,
                detail="Location must fall within the selected event scope",
            )
        
        db_obj = Offering(
            event_id=obj_in.event_id,
            location_id=obj_in.location_id,
            path=location_path,
            program_scope_path=str(event.path) if event else location_path,
            date=event.date if event else obj_in.date,
            church_type=obj_in.church_type,
            program_level=program_level,
            program_domain_id=program_domain_id,
            program_type_id=program_type_id,
            program_domain=obj_in.program_domain if not event else None,
            program_type=obj_in.program_type if not event else None,
            client_id=obj_in.client_id,
            amount=obj_in.amount,
            payment_method=obj_in.payment_method,
            fund_type=obj_in.fund_type or "offering",
            # Removed separate payer fields per user request
            note=obj_in.note,
            entered_by_id=user_id,
            status="pending"
        )
        
        db.add(db_obj)
        created = await commit_idempotent(
            db, db_obj, client_id=obj_in.client_id,
            lookup=lambda session, client_id: self.get_by_client_id(session, client_id=client_id),
        )
        analytics_cache.clear()
        return created

    @staticmethod
    def _snapshot(row: Offering) -> dict:
        return {
            "amount": str(row.amount),
            "payment_method": row.payment_method,
            "fund_type": row.fund_type,
            "note": row.note,
            "status": row.status,
            "reviewed_by_id": str(row.reviewed_by_id) if row.reviewed_by_id else None,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "review_note": row.review_note,
        }

    async def correct(self, db: AsyncSession, *, offering_id: UUID, correction: OfferingCorrection,
                      actor_id: UUID, scope_path: str) -> Offering:
        result = await db.execute(select(Offering).where(
            Offering.id == offering_id, Offering.is_deleted == False,
            scope_filter(Offering.path, scope_path),
        ).with_for_update())
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Offering not found")
        if row.status == "reversed":
            raise HTTPException(status_code=409, detail="Reversed financial entries are terminal and cannot be corrected")
        changes = correction.model_dump(exclude={"reason"}, exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=400, detail="Provide at least one field to correct")
        before = self._snapshot(row)
        for key, value in changes.items():
            setattr(row, key, value)
        row.status = "corrected"
        row.reviewed_by_id = None
        row.reviewed_at = None
        row.review_note = None
        after = self._snapshot(row)
        db.add(OfferingAudit(
            offering_id=row.id, actor_id=actor_id, action="corrected",
            reason=correction.reason, before_values=before, after_values=after,
        ))
        await db.commit()
        await db.refresh(row)
        analytics_cache.clear()
        return row

    async def review(self, db: AsyncSession, *, offering_id: UUID, actor_id: UUID,
                     scope_path: str, decision: str, note: Optional[str] = None) -> Offering:
        if decision not in {"approved", "rejected"}:
            raise HTTPException(status_code=400, detail="Invalid review decision")
        if decision == "rejected" and (not note or len(note.strip()) < 20):
            raise HTTPException(status_code=400, detail="Rejection reason must be at least 20 characters")
        result = await db.execute(select(Offering).where(
            Offering.id == offering_id, Offering.is_deleted == False,
            scope_filter(Offering.path, scope_path),
        ).with_for_update())
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Offering not found")
        if row.status not in {"pending", "corrected"}:
            raise HTTPException(status_code=409, detail="Only pending or corrected financial entries can be reviewed")
        if row.entered_by_id == actor_id:
            raise HTTPException(status_code=403, detail="The submitter cannot review their own financial entry")
        before = self._snapshot(row)
        row.status = decision
        row.reviewed_by_id = actor_id
        row.reviewed_at = datetime.now(UTC)
        row.review_note = note.strip() if note else None
        after = self._snapshot(row)
        db.add(OfferingAudit(
            offering_id=row.id, actor_id=actor_id, action=decision,
            reason=note.strip() if note else "Reviewed and approved",
            before_values=before, after_values=after,
        ))
        await db.commit()
        await db.refresh(row)
        analytics_cache.clear()
        return row

    async def reverse(self, db: AsyncSession, *, offering_id: UUID, actor_id: UUID,
                      scope_path: str, reason: str) -> Offering:
        if len(reason.strip()) < 20:
            raise HTTPException(status_code=400, detail="Reversal reason must be at least 20 characters")
        result = await db.execute(select(Offering).where(
            Offering.id == offering_id, Offering.is_deleted == False,
            scope_filter(Offering.path, scope_path),
        ).with_for_update())
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Offering not found")
        if row.status != "approved":
            raise HTTPException(status_code=409, detail="Only approved financial entries can be reversed")
        if row.entered_by_id == actor_id:
            raise HTTPException(status_code=403, detail="The submitter cannot reverse their own financial entry")
        before = self._snapshot(row)
        row.status = "reversed"
        row.review_note = reason.strip()
        after = self._snapshot(row)
        db.add(OfferingAudit(
            offering_id=row.id, actor_id=actor_id, action="reversed",
            reason=reason.strip(), before_values=before, after_values=after,
        ))
        await db.commit()
        await db.refresh(row)
        analytics_cache.clear()
        return row

    async def audit_history(self, db: AsyncSession, *, offering_id: UUID,
                            scope_path: str) -> list[OfferingAudit]:
        result = await db.execute(select(OfferingAudit).join(
            Offering, Offering.id == OfferingAudit.offering_id,
        ).where(
            OfferingAudit.offering_id == offering_id,
            scope_filter(Offering.path, scope_path),
        ).order_by(OfferingAudit.created_at.asc()))
        return list(result.scalars().all())

    async def soft_delete(self, db: AsyncSession, *, offering_id: UUID, actor_id: UUID,
                          scope_path: str, reason: str) -> None:
        if len(reason.strip()) < 20:
            raise HTTPException(status_code=400, detail="Deletion reason must be at least 20 characters")
        result = await db.execute(select(Offering).where(
            Offering.id == offering_id, Offering.is_deleted == False,
            scope_filter(Offering.path, scope_path),
        ).with_for_update())
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Offering not found")
        before = self._snapshot(row)
        row.is_deleted = True
        row.operation = "DELETE"
        after = {**self._snapshot(row), "is_deleted": True}
        db.add(OfferingAudit(
            offering_id=row.id, actor_id=actor_id, action="deleted",
            reason=reason.strip(), before_values=before, after_values=after,
        ))
        await db.commit()
        analytics_cache.clear()
    
    async def get_by_client_id(self, db: AsyncSession, *, client_id: UUID) -> Optional[Offering]:
        """Get offering by client_id."""
        query = select(Offering).where(Offering.client_id == client_id)
        result = await db.execute(query)
        return result.scalars().first()
    
    async def get_multi_by_scope(
        self, 
        db: AsyncSession, 
        *, 
        scope_path: str,
        fund_type: Optional[str] = None,
        location_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        amount: Optional[float] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Offering]:
        """Get offerings within scope."""
        query = select(Offering).where(
            scope_filter(Offering.path, scope_path),
            Offering.is_deleted == False,
        )
        if fund_type:
            query = query.where(Offering.fund_type == fund_type)
        if location_id:
            query = query.where(Offering.location_id == location_id)
        if start_date:
            query = query.where(Offering.date >= start_date)
        if end_date:
            query = query.where(Offering.date < end_date + timedelta(days=1))
        if amount is not None:
            query = query.where(Offering.amount == amount)

        query = query.offset(skip).limit(limit).order_by(Offering.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()


offering = CRUDOffering(Offering)
