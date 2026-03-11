from sqlalchemy import Column, String, Boolean, Date, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin


class AppVersion(Base, TimestampMixin, SoftDeleteMixin):
    """
    App version metadata for mobile/web clients.
    """
    __tablename__ = "app_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_name = Column(String, nullable=False)  # e.g. "Usher App"
    platform = Column(String, nullable=False)  # Android, iOS, Web
    version_number = Column(String, nullable=True)
    version_tag = Column(String, nullable=True)  # e.g. v1.0.0
    release_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    file_name = Column(String, nullable=True)
    download_url = Column(String, nullable=True)
    min_os_version = Column(String, nullable=True)
    build = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
