"""Import all models here for Alembic auto-detection."""
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
from app.models.location import Nation, State, Region, Group, Location, Fellowship
from app.models.programs import ProgramDomain, ProgramType, ProgramCampaign, ProgramEvent, EventAssignment
from app.models.counts import Count
from app.models.offerings import Offering
from app.models.records import Record
from app.models.attendance import WorkerAttendance
from app.models.fellowship_activities import FellowshipMember, FellowshipAttendance, FellowshipOffering
from app.models.audit import IdempotencyKey, AuditLog, NotificationReadState
from app.models.announcement import Announcement, AnnouncementItem
from app.models.media import MediaGallery, MediaItem
from app.models.app_version import AppVersion
from app.models.approvals import TransferRequest, StatusChangeRequest, WorkerRemovalRequest
from app.models.public_intake import PublicContactSubmission, PublicPrayerSubmission
from app.models.official_appointment import OfficialAppointment
from app.models.location_profile import LocationProfile  # noqa
from app.models.church_member import ChurchMember  # noqa
from app.models.transfers import WorkerTransfer  # noqa
from app.models.attendance import WorkerAbsenceNotice  # noqa
from app.models.refresh_token import RefreshToken  # noqa — token rotation table
