"""Official appointment models."""
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin


class OfficialAppointment(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    __tablename__ = "official_appointments"

    appointment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.worker_id", ondelete="RESTRICT"), nullable=False, index=True)
    worker_name = Column(String, nullable=False, index=True)
    location_id = Column(String, nullable=False, index=True)
    location_name = Column(String, nullable=False)
    appointed_role = Column(String, nullable=False, index=True)
    assigned_scope_label = Column(String, nullable=False)
    appointment_date = Column(Date, nullable=False, index=True)
    status = Column(String, nullable=False, default="active", index=True)
    note = Column(String, nullable=True)
    appointed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    appointed_by_name = Column(String, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    revoked_note = Column(String, nullable=True)

    worker = relationship("Worker", foreign_keys=[worker_id])
    appointed_by = relationship("User", foreign_keys=[appointed_by_id])
    revoked_by = relationship("User", foreign_keys=[revoked_by_id])

    __table_args__ = (
        UniqueConstraint("worker_id", "appointed_role", "path", name="uq_official_appointment_worker_role_path"),
    )

    def __repr__(self):
        return f"<OfficialAppointment(worker='{self.worker_name}', role='{self.appointed_role}', scope='{self.path}')>"
