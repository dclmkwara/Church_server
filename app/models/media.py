"""
Media Management Models.

This module defines models for handling media galleries and file uploads (photos/videos).
"""
import uuid
from sqlalchemy import Column, String, ForeignKey, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin

class MediaGallery(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Media Gallery Model.
    
    Represents a collection of media items (photos/videos).
    Can be linked to a specific ProgramEvent (e.g., "Easter Retreat Photos")
    or exist independently (e.g., "Location History").
    """
    __tablename__ = "media_galleries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Path is inherited from LTreePathMixin (defines scope)
    # e.g., org.234.kw.iln
    
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Optional URL friendly slug
    slug = Column(String, index=True, nullable=True)
    
    # Optional link to event
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=True, index=True)
    
    # Audit
    # created_by from TimestampMixin? No, AuditMixin usually has it. 
    # But checking core.py, AuditMixin was defined but not imported/used in others consistently.
    # We'll explicitly add created_by_id like others.
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    items = relationship("MediaItem", back_populates="gallery", cascade="all, delete-orphan")
    event = relationship("ProgramEvent")
    created_by = relationship("User")
    
    def __repr__(self):
        return f"<MediaGallery(title='{self.title}', path='{self.path}')>"


class MediaItem(Base, TimestampMixin, SoftDeleteMixin):
    """
    Media Item Model.
    
    Represents an individual file (photo/video) within a gallery.
    Stores metadata only; actual files are in Object Storage (Supabase).
    """
    __tablename__ = "media_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    gallery_id = Column(UUID(as_uuid=True), ForeignKey("media_galleries.id"), nullable=False, index=True)
    
    # File Metadata
    file_path = Column(String, nullable=False) # Path in storage bucket (e.g. galleries/uuid/image.jpg)
    file_name = Column(String, nullable=False) # Original filename
    file_type = Column(String, nullable=False) # Mime type (image/jpeg)
    file_size = Column(Integer, nullable=False) # Bytes
    
    # Display Info
    caption = Column(String, nullable=True)
    is_cover = Column(Boolean, default=False, index=True) # Is this the cover image for the gallery?
    
    uploaded_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    gallery = relationship("MediaGallery", back_populates="items")
    uploaded_by = relationship("User")
    
    def __repr__(self):
        return f"<MediaItem(name='{self.file_name}', type='{self.file_type}')>"
