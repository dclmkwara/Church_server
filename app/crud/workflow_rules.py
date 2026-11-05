"""Pure workflow helpers for event-bound submissions."""
from datetime import UTC, datetime
from fastapi import HTTPException
from sqlalchemy import func, select


def collection_window_for(event, campaign=None):
    """Return the event window, falling back to its campaign window."""
    start = event.collection_window_start or (campaign.collection_window_start if campaign else None)
    end = event.collection_window_end or (campaign.collection_window_end if campaign else None)
    return start, end


def collection_window_is_active(event, campaign=None, *, now=None) -> bool:
    """Auto-setup is available only inside an explicit, finite collection window."""
    start, end = collection_window_for(event, campaign)
    if not start or not end:
        return False
    now = now or datetime.now(UTC)
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return start <= now <= end


def ensure_collection_open(event, campaign=None, *, now=None, kind="submission"):
    """Reject writes outside explicitly configured windows; allow backfill if none set."""
    if event.is_deleted:
        raise HTTPException(status_code=400, detail=f"Cannot record {kind} for a deleted event")
    if getattr(event, "approval_status", "approved") != "approved":
        raise HTTPException(status_code=403, detail=f"Cannot record {kind} for an event that has not been approved")
    if campaign and campaign.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot record {kind} for a {campaign.status} campaign")
    start, end = collection_window_for(event, campaign)
    now = now or datetime.now(UTC)
    # Campaign status dates are not collection windows; only explicit windows gate writes.
    if start and start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end and end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if start and now < start:
        raise HTTPException(status_code=400, detail=f"{kind.capitalize()} collection has not opened")
    if end and now > end:
        raise HTTPException(status_code=400, detail=f"{kind.capitalize()} collection is closed")


async def load_event_campaign(db, event):
    if not event.campaign_id:
        return None
    from app.models.programs import ProgramCampaign
    campaign = await db.get(ProgramCampaign, event.campaign_id)
    if not campaign or campaign.is_deleted:
        raise HTTPException(status_code=400, detail="Event campaign is unavailable")
    return campaign


async def resolve_program_context(db, *, event=None, program_domain=None, program_type=None):
    """Return canonical domain/type IDs for a submission or scheduled event."""
    from app.models.programs import ProgramDomain, ProgramType

    if event is not None:
        type_row = await db.get(ProgramType, event.program_type_id)
        if not type_row:
            raise HTTPException(status_code=422, detail="Scheduled program has no valid program type")
        return type_row.domain_id, type_row.id

    domain_aliases = {
        "weekly": "weekly_programs", "weekly programs": "weekly_programs",
        "regular services": "weekly_programs", "crusade": "global_crusade",
        "open crusade": "global_crusade", "global crusade": "global_crusade",
        "conference": "conferences", "conferences": "conferences",
        "special": "special_programs", "special programs": "special_programs",
    }
    domain_key = (program_domain or "").strip().lower()
    domain_slug = domain_aliases.get(domain_key, domain_key.replace(" ", "_"))
    domain = (await db.execute(select(ProgramDomain).where(
        ProgramDomain.slug == domain_slug, ProgramDomain.is_deleted.is_(False)
    ))).scalars().first()
    if not domain:
        raise HTTPException(status_code=422, detail="Program domain is not in the canonical taxonomy")

    type_aliases = {
        "workers meeting": "saturday_workers_meeting",
        "thursday revival & training": "thursday_revival_hour",
        "thursday revival and training": "thursday_revival_hour",
        "evening crusade": "crusade_evening",
        "bible study": "retreat_bible_study" if domain.slug == "retreat" else "monday_bible_study",
    }
    type_key = (program_type or "").strip().lower()
    type_slug = type_aliases.get(type_key, type_key.replace(" ", "_").replace("&", "and"))
    type_row = (await db.execute(select(ProgramType).where(
        ProgramType.domain_id == domain.id,
        ProgramType.is_deleted.is_(False),
        (ProgramType.slug == type_slug) | (func.lower(func.trim(ProgramType.name)) == type_key),
    ))).scalars().first()
    if not type_row:
        raise HTTPException(status_code=422, detail="Program type does not belong to the selected canonical domain")
    return domain.id, type_row.id


def resolve_program_level(*, event=None, program_level=None):
    """Use the scheduled event scope as authority; require explicit routine scope."""
    levels = {
        "local": "Local", "location": "Local", "group": "Group",
        "region": "Region", "state": "State", "national": "National", "global": "Global",
    }
    if event is not None:
        expected = levels.get(str(event.reporting_scope or "").strip().lower())
        if not expected:
            raise HTTPException(status_code=422, detail="Scheduled program has an unsupported reporting scope")
        if program_level and str(program_level).strip().lower() != expected.lower():
            raise HTTPException(status_code=422, detail="Program level must match the scheduled program reporting scope")
        return expected
    if program_level:
        level = levels.get(str(program_level).strip().lower())
        if level:
            return level
    raise HTTPException(status_code=422, detail="Routine program submissions require a valid program level")


async def require_approved_worker_user(db, user_id):
    """Return the linked worker user, rejecting inactive or unapproved accounts."""
    from app.models.user import User
    user = await db.get(User, user_id)
    if not user or not user.is_active or user.approval_status != "approved":
        raise HTTPException(status_code=403, detail="An active approved worker account is required")
    return user


async def require_event_assignment(
    db,
    *,
    user,
    event,
    assignment_id,
    location_id,
    submission_kind: str,
    required: bool = False,
):
    """Authorize a field submission against an approved event/source assignment.

    Alpha assignments may report only for the event's host location. Satellite
    and regular assignments remain tied to the assigned worker's own location.
    The event assignment is the explicit cross-location authorization.
    """
    from app.models.programs import EventAssignment

    if not assignment_id:
        if required and event:
            detail = "Combined attendance requires an approved event assignment" if submission_kind == "attendance" else "Crusade field submissions require an approved event assignment"
            raise HTTPException(status_code=403, detail=detail)
        return None
    if event is None:
        raise HTTPException(status_code=400, detail="Event assignment requires a scheduled event")
    assignment = await db.get(EventAssignment, assignment_id)
    if not assignment or assignment.is_deleted:
        raise HTTPException(status_code=404, detail="Event assignment not found")
    if assignment.event_id != event.id:
        raise HTTPException(status_code=400, detail="Assignment does not belong to this event")
    if assignment.status != "approved":
        raise HTTPException(status_code=403, detail="Event assignment is not approved")
    if not user or user.worker_id != assignment.worker_id:
        raise HTTPException(status_code=403, detail="Event assignment belongs to a different worker")
    if str(assignment.path) != str(event.path):
        raise HTTPException(status_code=403, detail="Event assignment scope does not match its event")
    if submission_kind == "count" and assignment.assignment_type not in {"count", "both", "all"}:
        raise HTTPException(status_code=403, detail="Assignment is not enabled for count submission")
    if submission_kind == "record" and assignment.assignment_type not in {"convert", "both", "all"}:
        raise HTTPException(status_code=403, detail="Assignment is not enabled for newcomer/convert submission")
    if submission_kind == "attendance" and assignment.assignment_type not in {"attendance", "all"}:
        raise HTTPException(status_code=403, detail="Assignment is not enabled for worker attendance submission")

    source_role = assignment.source_role
    if source_role == "alpha":
        if not event.alpha_location_id or str(event.alpha_location_id) != str(location_id):
            raise HTTPException(status_code=403, detail="Alpha assignment may submit only for the event's host location")
    elif submission_kind == "attendance" and event.reporting_scope in {"group", "region", "state"}:
        if source_role != "regular":
            raise HTTPException(status_code=403, detail="Combined attendance requires a regular event-field assignment")
        if not str(location_id).strip():
            raise HTTPException(status_code=403, detail="A physical meeting location is required")
        if str(user.location_id) != str(location_id):
            raise HTTPException(status_code=403, detail="Combined attendance must identify the assigned worker's physical home location")
    elif source_role in {"satellite", "regular"}:
        if str(user.location_id) != str(location_id):
            raise HTTPException(status_code=403, detail="This assignment may submit only for the worker's home location")
    else:
        raise HTTPException(status_code=403, detail="Unsupported event assignment source")
    return assignment


async def widen_scope_for_approved_event_submission(db, event) -> None:
    """Temporarily use the event path for an already-authorized submission.

    The setting is transaction-local and is deliberately not saved to the
    request session context. The next transaction restores the user's home
    scope through the session's normal RLS context hook.
    """
    from sqlalchemy import text

    await db.execute(
        text("SELECT set_config('app.scope_path', :scope_path, true)"),
        {"scope_path": str(event.path)},
    )


def validate_campaign_transition(current: str, target: str) -> None:
    """Enforce one-way campaign lifecycle transitions; archived campaigns are terminal."""
    allowed = {
        "draft": {"draft", "active", "archived"},
        "active": {"active", "closed", "archived"},
        "closed": {"closed", "archived"},
        "archived": {"archived"},
    }
    if target not in allowed.get(current, set()):
        raise HTTPException(status_code=400, detail=f"Campaign cannot transition from {current} to {target}")
