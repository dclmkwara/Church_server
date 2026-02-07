"""
Import all models here for Alembic auto-detection.
"""
from app.models.core import *  # noqa
from app.models.user import (  # noqa
    RoleScore,
    Permission,
    Role,
    Worker,
    User,
    PasswordResetToken,
    role_permissions,
    user_roles,
)

# Import other models as they are created
from app.models.location import Nation, State, Region, Group, Location, Fellowship
from app.models.programs import ProgramDomain, ProgramType, ProgramEvent
from app.models.counts import Count
from app.models.offerings import Offering
from app.models.records import Record
from app.models.attendance import WorkerAttendance
from app.models.fellowship_activities import FellowshipMember, FellowshipAttendance, FellowshipOffering
from app.models.audit import IdempotencyKey, AuditLog
from app.models.announcement import Announcement, AnnouncementItem
from app.models.media import MediaGallery, MediaItem
# from app.models.audit import AuditLog, ClientSyncQueue, ExportJob
# from app.models.version import AppVersion
