
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api import deps
from app.models.programs import ProgramEvent, ProgramType
from app.models.location import Location
from app.models.media import MediaGallery
from app.schemas.public import (
    PublicEventResponse,
    PublicLocationResponse,
    PublicGalleryResponse,
    PublicGalleryDetailResponse,
    PublicGalleryItemResponse,
    PublicAnnouncementResponse
)

router = APIRouter()

@router.get("/events", response_model=List[PublicEventResponse])
async def get_public_events(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
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
        .where(ProgramEvent.date >= from_date)
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
    event_id: str,
    db: AsyncSession = Depends(deps.get_db),
):
    """Get a single public event."""
    query = (
        select(ProgramEvent)
        .options(selectinload(ProgramEvent.program_type))
        .where(ProgramEvent.id == event_id)
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
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None
):
    """
    Get public locations.
    """
    query = select(Location)
    
    if search:
        query = query.where(Location.location_name.ilike(f"%{search}%"))
    
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
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(10.0),
    db: AsyncSession = Depends(deps.get_db),
):
    """Find nearby locations by latitude/longitude."""
    query = select(Location).where(
        Location.latitude.is_not(None),
        Location.longitude.is_not(None),
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
            nearby.append(loc)
    
    return [
        PublicLocationResponse(
            id=e.location_id,
            name=e.location_name,
            type=e.church_type,
            address=e.address
        )
        for e in nearby
    ]

@router.get("/galleries", response_model=List[PublicGalleryResponse])
async def get_public_galleries(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100
):
    """
    Get public media galleries.
    """
    query = select(MediaGallery).order_by(MediaGallery.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    galleries = result.scalars().all()
    return galleries


@router.get("/announcements", response_model=List[PublicAnnouncementResponse])
async def get_public_announcements(
    db: AsyncSession = Depends(deps.get_db),
    limit: int = 50
):
    """Get public announcements (active only)."""
    from app.models.announcement import Announcement
    query = select(Announcement).where(Announcement.is_active == True).order_by(Announcement.date.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/galleries/{gallery_id}", response_model=PublicGalleryDetailResponse)
async def get_public_gallery(
    gallery_id: str,
    db: AsyncSession = Depends(deps.get_db),
):
    """Get gallery details with items."""
    from app.models.media import MediaItem
    query = select(MediaGallery).where(MediaGallery.id == gallery_id)
    result = await db.execute(query)
    gallery = result.scalars().first()
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    items_query = select(MediaItem).where(MediaItem.gallery_id == gallery_id)
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
from app.models.fellowship_activities import PrayerRequest
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
    state_code = str(location.path).split('.')[2] if len(str(location.path).split('.')) > 2 else "XX"
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
        state=location.path.split('.')[2] if len(str(location.path).split('.')) > 2 else "",
        region=location.path.split('.')[3] if len(str(location.path).split('.')) > 3 else "",
        group=location.path.split('.')[4] if len(str(location.path).split('.')) > 4 else "",
        unit=worker_in.unit,
        address=worker_in.address,
        occupation=worker_in.occupation,
        marital_status=worker_in.marital_status,
        status="Active",
        path=str(location.path)
    )
    
    db.add(worker)
    await db.commit()
    
    return PublicFormResponse(
        success=True,
        message="Registration successful! Your worker ID is: " + user_id,
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
    
    Stores contact inquiries for admin review.
    Could be stored in a dedicated table or sent via email.
    For now, we'll log it (in production, store in a contacts table).
    """
    # In production, create a Contact model and store this
    # For now, just return success
    # You could also send an email notification to admin
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Contact form submission from {contact_in.name} ({contact_in.email}): {contact_in.subject}")
    
    return PublicFormResponse(
        success=True,
        message="Thank you for contacting us! We will respond within 24-48 hours.",
        reference_id=str(uuid.uuid4())
    )


@router.post("/prayer-request", response_model=PublicFormResponse)
async def public_prayer_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    prayer_in: PublicPrayerRequest
):
    """
    Public prayer request submission.
    
    Creates a prayer request that can be viewed by fellowship leaders.
    """
    # Create prayer request (assign to a default fellowship or make it global)
    # For public requests, we might need a special "Public Requests" fellowship
    # Or store them separately
    
    # For now, log it and return success
    # In production, create a PublicPrayerRequest model or assign to a default fellowship
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Public prayer request from {prayer_in.name}: {prayer_in.request[:50]}...")
    
    return PublicFormResponse(
        success=True,
        message="Your prayer request has been received. We will pray for you!",
        reference_id=str(uuid.uuid4())
    )


# App Version & Downloads
@router.get("/app-version")
async def get_app_version():
    """
    Get mobile app version information and download links.
    
    Returns current version numbers and download URLs for all mobile apps.
    """
    # Try DB-backed versions first
    try:
        from app.db.session import AsyncSessionLocal
        from app.models.app_version import AppVersion
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AppVersion).where(AppVersion.is_active == True)
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
        pass

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
async def get_app_versions():
    """Alias for app version info."""
    return await get_app_version()


