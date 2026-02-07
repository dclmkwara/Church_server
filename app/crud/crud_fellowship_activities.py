"""
CRUD operations for Fellowship Activities.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.fellowship_activities import (
    FellowshipMember, FellowshipAttendance, FellowshipOffering,
    Testimony, PrayerRequest, AttendanceSummary
)
from app.schemas.fellowship_activities import (
    FellowshipMemberCreate, FellowshipMemberResponse,
    FellowshipAttendanceCreate, FellowshipAttendanceResponse,
    FellowshipOfferingCreate, FellowshipOfferingResponse,
    TestimonyCreate, PrayerRequestCreate, AttendanceSummaryCreate,
    TestimonyUpdate, PrayerRequestUpdate, AttendanceSummaryUpdate
)


class CRUDFellowshipMember(CRUDBase[FellowshipMember, FellowshipMemberCreate, FellowshipMemberCreate]):
    """CRUD for Fellowship Members."""
    
    async def create(self, db: AsyncSession, *, obj_in: FellowshipMemberCreate) -> FellowshipMember:
        # Verify fellowship exists
        from app.crud.crud_location import fellowship
        fel = await fellowship.get(db, id=obj_in.fellowship_id)
        if not fel:
            raise HTTPException(status_code=404, detail="Fellowship not found")
            
        path_str = str(fel.path)
        
        # Check idempotency
        if obj_in.client_id:
            query = select(FellowshipMember).where(FellowshipMember.client_id == obj_in.client_id)
            existing = (await db.execute(query)).scalars().first()
            if existing:
                return existing

        db_obj = FellowshipMember(
            fellowship_id=obj_in.fellowship_id,
            path=path_str,
            client_id=obj_in.client_id,
            name=obj_in.name,
            phone=obj_in.phone,
            gender=obj_in.gender,
            address=obj_in.address,
            role=obj_in.role
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
        
    async def get_by_fellowship(self, db: AsyncSession, fellowship_id: str, skip=0, limit=100) -> List[FellowshipMember]:
        query = select(FellowshipMember).where(
            FellowshipMember.fellowship_id == fellowship_id
        ).offset(skip).limit(limit)
        return (await db.execute(query)).scalars().all()


class CRUDFellowshipAttendance(CRUDBase[FellowshipAttendance, FellowshipAttendanceCreate, FellowshipAttendanceCreate]):
    """CRUD for Fellowship Attendance."""
    
    async def create(self, db: AsyncSession, *, obj_in: FellowshipAttendanceCreate, user_id: UUID) -> FellowshipAttendance:
        from app.crud.crud_location import fellowship
        fel = await fellowship.get(db, id=obj_in.fellowship_id)
        if not fel:
            raise HTTPException(status_code=404, detail="Fellowship not found")
            
        path_str = str(fel.path)
        
        if obj_in.client_id:
            query = select(FellowshipAttendance).where(FellowshipAttendance.client_id == obj_in.client_id)
            existing = (await db.execute(query)).scalars().first()
            if existing:
                return existing

        total = obj_in.men + obj_in.women + obj_in.youths + obj_in.children
        
        db_obj = FellowshipAttendance(
            fellowship_id=obj_in.fellowship_id,
            path=path_str,
            client_id=obj_in.client_id,
            date=obj_in.date,
            men=obj_in.men,
            women=obj_in.women,
            youths=obj_in.youths,
            children=obj_in.children,
            total=total,
            topic=obj_in.topic,
            note=obj_in.note,
            entered_by_id=user_id
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


class CRUDFellowshipOffering(CRUDBase[FellowshipOffering, FellowshipOfferingCreate, FellowshipOfferingCreate]):
    """CRUD for Fellowship Offering."""
    
    async def create(self, db: AsyncSession, *, obj_in: FellowshipOfferingCreate, user_id: UUID) -> FellowshipOffering:
        from app.crud.crud_location import fellowship
        fel = await fellowship.get(db, id=obj_in.fellowship_id)
        if not fel:
            raise HTTPException(status_code=404, detail="Fellowship not found")
            
        path_str = str(fel.path)
        
        if obj_in.client_id:
            query = select(FellowshipOffering).where(FellowshipOffering.client_id == obj_in.client_id)
            existing = (await db.execute(query)).scalars().first()
            if existing:
                return existing

        db_obj = FellowshipOffering(
            fellowship_id=obj_in.fellowship_id,
            path=path_str,
            client_id=obj_in.client_id,
            date=obj_in.date,
            amount=obj_in.amount,
            note=obj_in.note,
            entered_by_id=user_id
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


class CRUDTestimony(CRUDBase[Testimony, TestimonyCreate, TestimonyUpdate]):
    """CRUD for Fellowship Testimonies."""
    
    async def create(self, db: AsyncSession, *, obj_in: TestimonyCreate, user_id: UUID) -> Testimony:
        from app.crud.crud_location import fellowship
        fel = await fellowship.get(db, id=obj_in.fellowship_id)
        if not fel:
            raise HTTPException(status_code=404, detail="Fellowship not found")
            
        path_str = str(fel.path)
        
        if obj_in.client_id:
            query = select(Testimony).where(Testimony.client_id == obj_in.client_id)
            existing = (await db.execute(query)).scalars().first()
            if existing:
                return existing

        db_obj = Testimony(
            fellowship_id=obj_in.fellowship_id,
            path=path_str,
            client_id=obj_in.client_id,
            date=obj_in.date,
            testifier_name=obj_in.testifier_name,
            content=obj_in.content,
            note=obj_in.note,
            entered_by_id=user_id
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


class CRUDPrayerRequest(CRUDBase[PrayerRequest, PrayerRequestCreate, PrayerRequestUpdate]):
    """CRUD for Fellowship Prayer Requests."""
    
    async def create(self, db: AsyncSession, *, obj_in: PrayerRequestCreate, user_id: UUID) -> PrayerRequest:
        from app.crud.crud_location import fellowship
        fel = await fellowship.get(db, id=obj_in.fellowship_id)
        if not fel:
            raise HTTPException(status_code=404, detail="Fellowship not found")
            
        path_str = str(fel.path)
        
        if obj_in.client_id:
            query = select(PrayerRequest).where(PrayerRequest.client_id == obj_in.client_id)
            existing = (await db.execute(query)).scalars().first()
            if existing:
                return existing

        db_obj = PrayerRequest(
            fellowship_id=obj_in.fellowship_id,
            path=path_str,
            client_id=obj_in.client_id,
            date=obj_in.date,
            requestor_name=obj_in.requestor_name,
            content=obj_in.content,
            status=obj_in.status,
            entered_by_id=user_id
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


class CRUDAttendanceSummary(CRUDBase[AttendanceSummary, AttendanceSummaryCreate, AttendanceSummaryUpdate]):
    """CRUD for Fellowship Attendance Summaries."""
    
    async def create(self, db: AsyncSession, *, obj_in: AttendanceSummaryCreate, user_id: UUID) -> AttendanceSummary:
        from app.crud.crud_location import fellowship
        fel = await fellowship.get(db, id=obj_in.fellowship_id)
        if not fel:
            raise HTTPException(status_code=404, detail="Fellowship not found")
            
        path_str = str(fel.path)
        
        if obj_in.client_id:
            query = select(AttendanceSummary).where(AttendanceSummary.client_id == obj_in.client_id)
            existing = (await db.execute(query)).scalars().first()
            if existing:
                return existing

        db_obj = AttendanceSummary(
            fellowship_id=obj_in.fellowship_id,
            path=path_str,
            client_id=obj_in.client_id,
            month=obj_in.month,
            year=obj_in.year,
            total_meetings=obj_in.total_meetings,
            avg_attendance=obj_in.avg_attendance,
            total_offering=obj_in.total_offering,
            entered_by_id=user_id
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


member = CRUDFellowshipMember(FellowshipMember)
attendance = CRUDFellowshipAttendance(FellowshipAttendance)
offering = CRUDFellowshipOffering(FellowshipOffering)
testimony = CRUDTestimony(Testimony)
prayer_request = CRUDPrayerRequest(PrayerRequest)
attendance_summary = CRUDAttendanceSummary(AttendanceSummary)
