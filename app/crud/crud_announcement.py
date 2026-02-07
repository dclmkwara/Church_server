from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.announcement import Announcement, AnnouncementItem
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate

class CRUDAnnouncement:
    @staticmethod
    async def create(db: AsyncSession, announcement_in: AnnouncementCreate, path: str) -> Announcement:
        """Create a new announcement with items."""
        announcement = Announcement(
            region_id=announcement_in.region_id,
            region_name=announcement_in.region_name,
            meeting=announcement_in.meeting,
            date=announcement_in.date,
            trets_topic=announcement_in.trets_topic,
            trets_date=announcement_in.trets_date,
            sws_topic=announcement_in.sws_topic,
            sws_bible_reading=announcement_in.sws_bible_reading,
            mbs_bible_reading=announcement_in.mbs_bible_reading,
            sts_study=announcement_in.sts_study,
            adult_hcf_lesson=announcement_in.adult_hcf_lesson,
            adult_hcf_volume=announcement_in.adult_hcf_volume,
            youth_hcf_lesson=announcement_in.youth_hcf_lesson,
            youth_hcf_volume=announcement_in.youth_hcf_volume,
            children_hcf_lesson=announcement_in.children_hcf_lesson,
            children_hcf_volume=announcement_in.children_hcf_volume,
            is_active=announcement_in.is_active,
            path=path
        )
        
        db.add(announcement)
        await db.flush()
        
        # Add items
        for item_data in announcement_in.items:
            item = AnnouncementItem(
                announcement_id=announcement.id,
                title=item_data.title,
                text=item_data.text
            )
            db.add(item)
        
        await db.commit()
        await db.refresh(announcement)
        return announcement

    @staticmethod
    async def get_by_id(db: AsyncSession, announcement_id: UUID) -> Optional[Announcement]:
        """Get announcement by ID with items."""
        stmt = select(Announcement).where(Announcement.id == announcement_id).options(selectinload(Announcement.items))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_list(
        db: AsyncSession,
        scope_path: str,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Announcement]:
        """Get announcements filtered by scope and active status."""
        stmt = select(Announcement).options(selectinload(Announcement.items))
        
        # Scope filtering using ltree
        stmt = stmt.where(
            (Announcement.path.op('<@')(scope_path)) | (Announcement.path == scope_path)
        )
        
        if is_active is not None:
            stmt = stmt.where(Announcement.is_active == is_active)
        
        stmt = stmt.order_by(Announcement.date.desc()).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        announcement_id: UUID,
        announcement_in: AnnouncementUpdate
    ) -> Optional[Announcement]:
        """Update announcement."""
        announcement = await CRUDAnnouncement.get_by_id(db, announcement_id)
        if not announcement:
            return None
        
        update_data = announcement_in.model_dump(exclude_unset=True)
        
        # Handle items separately
        items_data = update_data.pop('items', None)
        
        for field, value in update_data.items():
            setattr(announcement, field, value)
        
        if items_data is not None:
            # Delete existing items and create new ones
            for item in announcement.items:
                await db.delete(item)
            
            for item_data in items_data:
                item = AnnouncementItem(
                    announcement_id=announcement.id,
                    title=item_data.title,
                    text=item_data.text
                )
                db.add(item)
        
        await db.commit()
        await db.refresh(announcement)
        return announcement

    @staticmethod
    async def publish(db: AsyncSession, announcement_id: UUID) -> Optional[Announcement]:
        """Publish an announcement."""
        announcement = await CRUDAnnouncement.get_by_id(db, announcement_id)
        if not announcement:
            return None
        
        announcement.published_at = datetime.utcnow()
        announcement.is_active = True
        
        await db.commit()
        await db.refresh(announcement)
        return announcement

announcement = CRUDAnnouncement()
