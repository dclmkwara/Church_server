from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.counts import Count
from app.models.offerings import Offering
from app.models.fellowship_activities import FellowshipAttendance, PrayerRequest, Testimony

class NotificationService:
    @staticmethod
    async def poll_new_data(db: AsyncSession, scope_path: str, since: datetime) -> Dict[str, List[Any]]:
        """
        Check for new records in various tables created after `since` timestamp.
        """
        results = {}
        
        # 1. Counts
        stmt = select(Count).where(
            and_(
                (Count.path.op('<@')(scope_path)) | (Count.path == scope_path),
                Count.created_at > since
            )
        )
        counts = (await db.execute(stmt)).scalars().all()
        if counts:
            results["counts"] = [{"id": str(c.id), "program_type": c.program_type, "created_at": c.created_at} for c in counts]
            
        # 2. Offerings
        stmt = select(Offering).where(
            and_(
                (Offering.path.op('<@')(scope_path)) | (Offering.path == scope_path),
                Offering.created_at > since
            )
        )
        offerings = (await db.execute(stmt)).scalars().all()
        if offerings:
            results["offerings"] = [{"id": str(o.id), "amount": str(o.amount), "created_at": o.created_at} for o in offerings]
            
        # 3. Fellowship Attendance
        stmt = select(FellowshipAttendance).where(
            and_(
                (FellowshipAttendance.path.op('<@')(scope_path)) | (FellowshipAttendance.path == scope_path),
                FellowshipAttendance.created_at > since
            )
        )
        att = (await db.execute(stmt)).scalars().all()
        if att:
            results["fellowship_attendance"] = [{"id": str(a.id), "fellowship_id": a.fellowship_id, "total": a.total, "created_at": a.created_at} for a in att]

        # 4. Prayer Requests (Pending only?) - No, just new ones
        stmt = select(PrayerRequest).where(
            and_(
                (PrayerRequest.path.op('<@')(scope_path)) | (PrayerRequest.path == scope_path),
                PrayerRequest.created_at > since
            )
        )
        pr = (await db.execute(stmt)).scalars().all()
        if pr:
            results["prayer_requests"] = [{"id": str(p.id), "requestor": p.requestor_name, "created_at": p.created_at} for p in pr]
            
        return results
