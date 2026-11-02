"""Pure workflow helpers for event-bound submissions."""
from datetime import UTC, datetime
from fastapi import HTTPException


def collection_window_for(event, campaign=None):
    """Return the event window, falling back to its campaign window."""
    start = event.collection_window_start or (campaign.collection_window_start if campaign else None)
    end = event.collection_window_end or (campaign.collection_window_end if campaign else None)
    return start, end


def ensure_collection_open(event, campaign=None, *, now=None, kind="submission"):
    """Reject writes outside explicitly configured windows; allow backfill if none set."""
    if event.is_deleted:
        raise HTTPException(status_code=400, detail=f"Cannot record {kind} for a deleted event")
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


async def require_approved_worker_user(db, user_id):
    """Return the linked worker user, rejecting inactive or unapproved accounts."""
    from app.models.user import User
    user = await db.get(User, user_id)
    if not user or not user.is_active or user.approval_status != "approved":
        raise HTTPException(status_code=403, detail="An active approved worker account is required")
    return user


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
