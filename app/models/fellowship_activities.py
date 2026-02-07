"""
Fellowship Activity models.

Tracks operations within House Fellowships (small groups), including:
- Member Registry (FellowshipMember)
- Weekly Meeting Attendance (FellowshipAttendance)
- Weekly Offerings (FellowshipOffering - Aggregate)
"""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType


class FellowshipMember(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Fellowship Member Registry.
    
    Persistent registry of members belonging to a specific fellowship.
    This is different from church-wide members; this is specifically for small group lists.
    """
    __tablename__ = "fellowship_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True) # For offline sync
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    fellowship_id = Column(String, ForeignKey("fellowships.fellowship_id"), nullable=False, index=True)
    
    # Personal Info
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True) # Optional for some rural areas?
    gender = Column(String, nullable=True)
    address = Column(String, nullable=True)
    
    # Status
    role = Column(String, default="member") # member, leader, assistant
    is_active = Column(Boolean, default=True)
    
    # Relationships
    fellowship = relationship("Fellowship")
    
    def __repr__(self):
        return f"<FellowshipMember(name='{self.name}', fellowship='{self.fellowship_id}')>"


class FellowshipAttendance(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Fellowship Meeting Attendance.
    
    Tracks weekly attendance for the fellowship.
    Can be summary (total count) or granular (list of members present).
    Based on typical use case, we often start with Summary for fellowships, 
    but for "Data Collection" phase 6, let's allow granular linking to members if needed.
    However, usually fellowships just report: "Men: 5, Women: 3".
    
    Let's stick to the granular design pattern if we have `FellowshipMember` registry.
    Actually, user asked for "Count" separately. 
    "it is usually important for the church to keep track of counts... based on the program".
    
    For Fellowship, usually it's a "Home Caring Fellowship".
    Let's implement **Head Count** primarily (Men, Women, Boys, Girls) like the main church Count,
    but specific to a fellowship meeting.
    """
    __tablename__ = "fellowship_attendance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    fellowship_id = Column(String, ForeignKey("fellowships.fellowship_id"), nullable=False, index=True)
    
    # Date/Context
    date = Column(DateTime, nullable=False, index=True) # Meeting date
    
    # Counts
    men = Column(Integer, default=0)
    women = Column(Integer, default=0)
    youths = Column(Integer, default=0)
    children = Column(Integer, default=0)
    total = Column(Integer, default=0)
    
    # Metadata
    topic = Column(String, nullable=True) # Bible study topic
    note = Column(Text, nullable=True)
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    fellowship = relationship("Fellowship")
    entered_by = relationship("User", foreign_keys=[entered_by_id])


class FellowshipOffering(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Fellowship Offering.
    
    Tracks the offering collected at the fellowship meeting.
    Aggregate amount.
    """
    __tablename__ = "fellowship_offerings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    fellowship_id = Column(String, ForeignKey("fellowships.fellowship_id"), nullable=False, index=True)
    
    # Financials
    date = Column(DateTime, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    
    # Metadata
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    note = Column(Text, nullable=True)
    
    # Relationships
    fellowship = relationship("Fellowship")
    entered_by = relationship("User", foreign_keys=[entered_by_id])


class Testimony(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Fellowship Testimony.
    
    Tracks testimonies shared during fellowship meetings.
    """
    __tablename__ = "fellowship_testimony"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    fellowship_id = Column(String, ForeignKey("fellowships.fellowship_id"), nullable=False, index=True)
    
    # Content
    date = Column(DateTime, nullable=False, index=True)
    testifier_name = Column(String, nullable=True) # Could be a member name or visitor
    content = Column(Text, nullable=False)
    
    # Metadata
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    note = Column(Text, nullable=True) # Admin notes/verification status?
    
    # Relationships
    fellowship = relationship("Fellowship")
    entered_by = relationship("User", foreign_keys=[entered_by_id])


class PrayerRequest(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Fellowship Prayer Request.
    
    Tracks prayer requests shared during meetings.
    """
    __tablename__ = "fellowship_prayer_request"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    fellowship_id = Column(String, ForeignKey("fellowships.fellowship_id"), nullable=False, index=True)
    
    # Content
    date = Column(DateTime, nullable=False, index=True)
    requestor_name = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    status = Column(String, default="pending") # pending, prayed, answered
    
    # Metadata
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    fellowship = relationship("Fellowship")
    entered_by = relationship("User", foreign_keys=[entered_by_id])


class AttendanceSummary(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Fellowship Attendance Summary.
    
    Aggregated attendance data (e.g. monthly summaries) if needed separate from daily/weekly.
    However, typically we just query `FellowshipAttendance`.
    Legacy system had `attendance_summaries`.
    We will map it here to support legacy feature set if they used it for specific reporting.
    """
    __tablename__ = "fellowship_attendance_summaries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    fellowship_id = Column(String, ForeignKey("fellowships.fellowship_id"), nullable=False, index=True)
    
    # Period
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    
    # Aggregates
    total_meetings = Column(Integer, default=0)
    avg_attendance = Column(Integer, default=0)
    total_offering = Column(Numeric(12, 2), default=0)
    
    # Metadata
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    fellowship = relationship("Fellowship")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
