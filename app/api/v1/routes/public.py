import logging
from typing import List, Optional
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.models.programs import ProgramEvent, ProgramType
from app.models.location import Location
from app.models.media import MediaGallery
from app.models.public_intake import PublicContactSubmission, PublicPrayerSubmission
from app.schemas.public import (
    PublicEventResponse,
    PublicLocationResponse,
    PublicGalleryResponse,
    PublicGalleryDetailResponse,
    PublicGalleryItemResponse,
    PublicAnnouncementResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/events", response_model=List[PublicEventResponse])
async def get_public_events(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    from_date: Optional[date] = None
):
    """
    Get upcoming public events.
    """
    if not from_date:
        from_date = date.today()
        
    query = (
        select(ProgramEvent)
        .options(selectinload(ProgramEvent.program_type))
        .where(
            ProgramEvent.date >= from_date,
            ProgramEvent.is_public == True,
            ProgramEvent.is_deleted == False,
            ProgramEvent.published_at.is_not(None),
        )
        .order_by(ProgramEvent.date.asc())
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    # Map to schema (needed because type_name is not on model)
    # Actually Pydantic v2/orm_mode might not auto-resolve `type_name` from `program_type.name` 
    # unless we use a property or explicit construction.
    # We'll construct explicitly to be safe and fast.
    return [
        PublicEventResponse(
            id=e.id,
            title=e.title,
            date=e.date,
            type_name=e.program_type.name if e.program_type else "Unknown"
        )
        for e in events
    ]


@router.get("/events/{event_id}", response_model=PublicEventResponse)
async def get_public_event(
    event_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
):
    """Get a single public event."""
    query = (
        select(ProgramEvent)
        .options(selectinload(ProgramEvent.program_type))
        .where(
            ProgramEvent.id == event_id,
            ProgramEvent.is_public == True,
            ProgramEvent.is_deleted == False,
            ProgramEvent.published_at.is_not(None),
        )
    )
    result = await db.execute(query)
    event = result.scalars().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return PublicEventResponse(
        id=event.id,
        title=event.title,
        date=event.date,
        type_name=event.program_type.name if event.program_type else "Unknown"
    )

@router.get("/locations", response_model=List[PublicLocationResponse])
async def get_public_locations(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, min_length=2, max_length=100)
):
    """
    Get public locations.
    """
    query = select(Location).order_by(Location.location_name.asc())
    
    if search:
        query = query.where(Location.location_name.ilike(f"%{search.strip()}%"))
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    locations = result.scalars().all()
    
    return [
        PublicLocationResponse(
            id=e.location_id,
            name=e.location_name,
            type=e.church_type,
            address=e.address
        )
        for e in locations
    ]


@router.get("/locations/nearby", response_model=List[PublicLocationResponse])
async def get_nearby_locations(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10.0, gt=0, le=200),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(deps.get_db),
):
    """Find nearby locations by latitude/longitude."""
    from math import cos, radians

    lat_delta = radius_km / 111.32
    lng_delta = radius_km / max(111.32 * abs(cos(radians(lat))), 0.01)
    query = select(Location).where(
        Location.latitude.is_not(None),
        Location.longitude.is_not(None),
        Location.latitude.between(lat - lat_delta, lat + lat_delta),
        Location.longitude.between(lng - lng_delta, lng + lng_delta),
    )
    result = await db.execute(query)
    locations = result.scalars().all()
    
    def haversine_km(lat1, lon1, lat2, lon2):
        from math import radians, sin, cos, sqrt, atan2
        R = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c
    
    nearby = []
    for loc in locations:
        dist = haversine_km(lat, lng, loc.latitude, loc.longitude)
        if dist <= radius_km:
            nearby.append((dist, loc))
    nearby.sort(key=lambda item: item[0])
    
    return [
        PublicLocationResponse(
            id=loc.location_id,
            name=loc.location_name,
            type=loc.church_type,
            address=loc.address
        )
        for _, loc in nearby[:limit]
    ]

@router.get("/galleries", response_model=List[PublicGalleryResponse])
async def get_public_galleries(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get public media galleries.
    """
    query = (
        select(MediaGallery)
        .where(
            MediaGallery.is_public == True,
            MediaGallery.is_deleted == False,
            MediaGallery.published_at.is_not(None),
        )
        .order_by(MediaGallery.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    galleries = result.scalars().all()
    return galleries


@router.get("/announcements", response_model=List[PublicAnnouncementResponse])
async def get_public_announcements(
    db: AsyncSession = Depends(deps.get_db),
    limit: int = Query(25, ge=1, le=100)
):
    """Get public announcements (active only)."""
    from app.models.announcement import Announcement
    query = (
        select(Announcement)
        .where(Announcement.is_active == True, Announcement.published_at.is_not(None))
        .order_by(Announcement.date.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/galleries/{gallery_id}", response_model=PublicGalleryDetailResponse)
async def get_public_gallery(
    gallery_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
):
    """Get gallery details with items."""
    from app.models.media import MediaItem
    query = select(MediaGallery).where(
        MediaGallery.id == gallery_id,
        MediaGallery.is_public == True,
        MediaGallery.is_deleted == False,
        MediaGallery.published_at.is_not(None),
    )
    result = await db.execute(query)
    gallery = result.scalars().first()
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    items_query = (
        select(MediaItem)
        .where(MediaItem.gallery_id == gallery_id, MediaItem.is_deleted == False)
        .order_by(MediaItem.is_cover.desc(), MediaItem.created_at.desc())
        .limit(200)
    )
    items_result = await db.execute(items_query)
    items = items_result.scalars().all()
    return PublicGalleryDetailResponse(
        id=gallery.id,
        title=gallery.title,
        description=gallery.description,
        slug=gallery.slug,
        created_at=gallery.created_at,
        items=[
            PublicGalleryItemResponse(
                id=i.id,
                file_path=i.file_path,
                file_name=i.file_name,
                file_type=i.file_type,
                file_size=i.file_size,
                caption=i.caption,
                is_cover=i.is_cover,
                created_at=i.created_at
            ) for i in items
        ]
    )


# Public Forms
from app.schemas.public import (
    PublicWorkerRegistration,
    PublicContactForm,
    PublicPrayerRequest,
    PublicFormResponse
)
from app.models.user import Worker
import uuid


@router.post("/workers/register", response_model=PublicFormResponse)
async def public_worker_registration(
    *,
    db: AsyncSession = Depends(deps.get_db),
    worker_in: PublicWorkerRegistration
):
    """
    Public worker registration form (from website).
    
    Creates a worker record that can later be converted to a user account
    by an administrator.
    """
    # Check if phone or email already exists
    existing = await db.execute(
        select(Worker).where(
            (Worker.phone == worker_in.phone) | (Worker.email == worker_in.email)
        )
    )
    if existing.scalars().first():
        return PublicFormResponse(
            success=False,
            message="A worker with this phone or email already exists."
        )
    
    # Get location to derive path
    from app.models.location import Location
    location_result = await db.execute(
        select(Location).where(Location.location_id == worker_in.location_id)
    )
    location = location_result.scalars().first()
    
    if not location:
        return PublicFormResponse(
            success=False,
            message=f"Location {worker_in.location_id} not found."
        )
    
    # Generate user_id (simplified version)
    # Format: STATE/PHONE (e.g., KW/2349012345678)
    phone_clean = worker_in.phone.replace("+", "").replace(" ", "")
    path_parts = str(location.path).split(".")
    state_code = path_parts[2] if len(path_parts) > 2 else "XX"
    user_id = f"{state_code.upper()}/{phone_clean}"
    
    # Create worker
    worker = Worker(
        worker_id=uuid.uuid4(),
        user_id=user_id,
        name=worker_in.name,
        phone=worker_in.phone,
        email=worker_in.email,
        gender=worker_in.gender,
        location_id=worker_in.location_id,
        location_name=location.location_name,
        church_type=location.church_type,
        state=path_parts[2] if len(path_parts) > 2 else "",
        region=path_parts[3] if len(path_parts) > 3 else "",
        group=path_parts[4] if len(path_parts) > 4 else "",
        unit=worker_in.unit,
        address=worker_in.address,
        occupation=worker_in.occupation,
        marital_status=worker_in.marital_status,
        status="Pending",
        approval_status="pending_verification",
        path=str(location.path)
    )
    
    db.add(worker)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return PublicFormResponse(
            success=False,
            message="A worker with this phone, email, or generated ID already exists."
        )
    
    return PublicFormResponse(
        success=True,
        message="Registration received. Your worker ID is: " + user_id + ". Awaiting verification.",
        reference_id=user_id
    )


@router.post("/contact", response_model=PublicFormResponse)
async def public_contact_form(
    *,
    db: AsyncSession = Depends(deps.get_db),
    contact_in: PublicContactForm
):
    """
    Public contact form submission.
    
    Stores contact inquiries durably for admin review.
    """
    submission = PublicContactSubmission(
        name=contact_in.name,
        email=contact_in.email,
        phone=contact_in.phone,
        subject=contact_in.subject,
        message=contact_in.message,
        status="new",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    
    return PublicFormResponse(
        success=True,
        message="Thank you for contacting us! We will respond within 24-48 hours.",
        reference_id=str(submission.id)
    )


@router.post("/prayer-request", response_model=PublicFormResponse)
async def public_prayer_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    prayer_in: PublicPrayerRequest
):
    """
    Public prayer request submission.
    
    Stores prayer requests durably for later admin review and routing.
    """
    submission = PublicPrayerSubmission(
        name=prayer_in.name,
        email=prayer_in.email,
        phone=prayer_in.phone,
        request=prayer_in.request,
        is_urgent=prayer_in.is_urgent,
        status="new",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    
    return PublicFormResponse(
        success=True,
        message="Your prayer request has been received. We will pray for you!",
        reference_id=str(submission.id)
    )


# App Version & Downloads
@router.get("/app-version")
async def get_app_version(db: AsyncSession = Depends(deps.get_db)):
    """
    Get mobile app version information and download links.
    
    Returns current version numbers and download URLs for all mobile apps.
    """
    # Try DB-backed versions first
    try:
        from app.models.app_version import AppVersion
        result = await db.execute(
            select(AppVersion)
            .where(AppVersion.is_active == True)
            .order_by(AppVersion.app_name.asc(), AppVersion.platform.asc())
        )
        versions = result.scalars().all()
        if versions:
            return {
                "apps": [
                    {
                        "name": v.app_name,
                        "platform": v.platform,
                        "version": v.version_number,
                        "build": v.build,
                        "download_url": v.download_url,
                        "min_os_version": v.min_os_version,
                        "release_date": v.release_date,
                        "changelog": v.description
                    }
                    for v in versions
                ],
                "api_version": "1.0.0",
                "min_supported_api": "1.0.0"
            }
    except Exception:
        logger.exception("Failed to load DB-backed app version information; using fallback payload")

    return {
        "apps": [
            {
                "name": "Usher App",
                "platform": "Android",
                "version": "1.0.0",
                "build": "100",
                "download_url": "https://play.google.com/store/apps/details?id=org.dclm.usher",
                "min_os_version": "8.0",
                "release_date": "2026-01-24",
                "changelog": [
                    "Initial release",
                    "Offline data collection",
                    "Automatic sync"
                ]
            },
            {
                "name": "Fellowship Leaders App",
                "platform": "Android",
                "version": "1.0.0",
                "build": "100",
                "download_url": "https://play.google.com/store/apps/details?id=org.dclm.fellowship",
                "min_os_version": "8.0",
                "release_date": "2026-01-24",
                "changelog": [
                    "Initial release",
                    "Member management",
                    "Attendance tracking"
                ]
            },
            {
                "name": "Admin App",
                "platform": "Web",
                "version": "1.0.0",
                "url": "https://admin.dclm.org",
                "release_date": "2026-01-24"
            }
        ],
        "api_version": "1.0.0",
        "min_supported_api": "1.0.0"
    }


@router.get("/app-versions")
async def get_app_versions(db: AsyncSession = Depends(deps.get_db)):
    """Alias for app version info."""
    return await get_app_version(db)


