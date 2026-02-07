from sqlalchemy import Column, String, Boolean, Date, ForeignKey, Text, Integer, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, LTreePathMixin

class Announcement(Base, TimestampMixin, LTreePathMixin):
    __tablename__ = "announcements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_id = Column(String, nullable=False, index=True) # References Region.region_id strictly or logically? Logic for now as Region.id is String
    # Note: In location.py Region PK is region_id (String). 
    # We can add FK if we want strictness: ForeignKey("regions.region_id")
    # But let's verify if regions table is named 'regions'. Yes in location.py it is 'regions'.
    
    region_name = Column(String, nullable=False)
    
    meeting = Column(String, nullable=True) # e.g. "Tuesday Leadership"
    date = Column(Date, nullable=False)
    
    trets_topic = Column(String, nullable=True)
    trets_date = Column(Date, nullable=True)
    
    sws_topic = Column(String, nullable=True)
    sws_bible_reading = Column(String, nullable=True)
    
    mbs_bible_reading = Column(String, nullable=True)
    sts_study = Column(String, nullable=True)
    
    adult_hcf_lesson = Column(String, nullable=True)
    adult_hcf_volume = Column(String, nullable=True)
    
    youth_hcf_lesson = Column(String, nullable=True)
    youth_hcf_volume = Column(String, nullable=True)
    
    children_hcf_lesson = Column(String, nullable=True)
    children_hcf_volume = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    items = relationship("AnnouncementItem", back_populates="announcement", cascade="all, delete-orphan", lazy="selectin")

class AnnouncementItem(Base):
    __tablename__ = "announcement_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    announcement_id = Column(UUID(as_uuid=True), ForeignKey("announcements.id"), nullable=False)
    title = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    
    announcement = relationship("Announcement", back_populates="items")
