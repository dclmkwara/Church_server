from __future__ import annotations

from datetime import date
from typing import Any

from ..backend import BackendClientError, format_scope_display_id, split_scope_path
from ..backend.config import get_backend_config
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .pagination import fetch_all_pages
from .people_service import PeopleService
from .request_cache import request_cached
from .ttl_cache import invalidate_ttl_prefix, ttl_cached


def _safe_date(raw: Any) -> str:
    value = str(raw or "")
    return value[:10] if value else ""


def _build_announcement_items(payload: dict[str, str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    title = payload.get("title", "").strip() or "Weekly Note"
    summary = payload.get("summary", "").strip()
    body = payload.get("body", "").strip()
    if summary:
        items.append({"title": title, "text": summary})
    if body:
        items.append({"title": "Main message", "text": body})
    for index in range(1, 9):
        text = payload.get(f"item_{index}", "").strip()
        if text:
            items.append({"title": f"Point {index}", "text": text})
    return items or [{"title": title, "text": "No summary added."}]


def _announcement_content(row: dict[str, Any]) -> tuple[str, str, list[str]]:
    items = row.get("items") or []
    title = str((items[0].get("title") if items else "") or row.get("trets_topic") or row.get("sws_topic") or row.get("meeting") or "Weekly Note")
    summary = str((items[0].get("text") if items else "") or row.get("region_name") or "Weekly communication note.")
    body = str((items[1].get("text") if len(items) > 1 else "") or summary)
    extra_items = [str(item.get("text") or "").strip() for item in items[2:]]
    return title, body, [item for item in extra_items if item]


def _normalize_announcement(row: dict[str, Any]) -> dict[str, Any]:
    title, body, items = _announcement_content(row)
    meeting = str(row.get("meeting") or "special_notice")
    published_at = row.get("published_at")
    is_active = bool(row.get("is_active", True))
    if published_at and is_active:
        status = "published"
    elif not is_active:
        status = "archived"
    else:
        status = "draft"
    summary_text = str((row.get("items") or [{}])[0].get("text") or row.get("region_name") or "Weekly communication note.")
    return {
        "announcement_id": str(row.get("id") or ""),
        "title": title,
        "summary": summary_text,
        "body": body,
        "items": items,
        "meeting": meeting,
        "meeting_label": meeting.replace("_", " ").title(),
        "meeting_date": _safe_date(row.get("date")),
        "audience": str(row.get("region_name") or "Pastors in scope"),
        "status": status,
        "path": str(row.get("path") or ""),
        "region_id": str(row.get("region_id") or ""),
        "region_name": str(row.get("region_name") or ""),
        "sws_bible_reading": str(row.get("sws_bible_reading") or ""),
        "sws_hymn": str(row.get("sws_hymn") or ""),
        "sws_topic": str(row.get("sws_topic") or ""),
        "mbs_bible_reading": str(row.get("mbs_bible_reading") or ""),
        "mbs_topic": str(row.get("mbs_topic") or ""),
        "sts_study": str(row.get("sts_study") or ""),
        "revival_topic": str(row.get("revival_topic") or ""),
        "revival_info": str(row.get("revival_info") or ""),
        "wedding_announcements": str(row.get("wedding_announcements") or ""),
        "general_announcements": str(row.get("general_announcements") or ""),
        "can_return_to_draft": False,
    }


def _gallery_visibility(row: dict[str, Any]) -> str:
    return "national_share" if bool(row.get("is_public")) else "scope_only"


def _normalize_media_item(row: dict[str, Any], gallery: dict[str, Any]) -> dict[str, Any]:
    file_type = str(row.get("file_type") or "")
    media_type = "video" if "video" in file_type.lower() else "photo"
    uploaded_at = str(row.get("created_at") or "")
    title = str(row.get("file_name") or "Media item")
    return {
        "item_id": str(row.get("id") or ""),
        "gallery_id": str(gallery.get("id") or ""),
        "gallery_title": str(gallery.get("title") or "Gallery"),
        "gallery_visibility": _gallery_visibility(gallery),
        "title": title,
        "caption": str(row.get("caption") or ""),
        "media_type": media_type,
        "file_label": str(row.get("file_path") or row.get("file_name") or ""),
        "uploaded_at": uploaded_at.replace("T", " ")[:16],
        "uploaded_by": str(row.get("uploaded_by_id") or "Backend upload"),
        "path": str(gallery.get("path") or ""),
    }


def _normalize_gallery(row: dict[str, Any]) -> dict[str, Any]:
    items = row.get("items") or []
    normalized_items = [_normalize_media_item(item, row) for item in items]
    photo_count = sum(1 for item in normalized_items if item["media_type"] == "photo")
    video_count = sum(1 for item in normalized_items if item["media_type"] == "video")
    return {
        "gallery_id": str(row.get("id") or ""),
        "title": str(row.get("title") or "Gallery"),
        "description": str(row.get("description") or ""),
        "event_name": str(row.get("title") or "Gallery"),
        "event_date": _safe_date(row.get("published_at") or row.get("created_at") or date.today().isoformat()),
        "visibility": _gallery_visibility(row),
        "scope_label": format_scope_display_id(str(row.get("path") or "")),
        "created_by": str(row.get("created_by_id") or "Backend upload"),
        "item_count": len(normalized_items),
        "photo_count": photo_count,
        "video_count": video_count,
        "path": str(row.get("path") or ""),
        "items": normalized_items,
    }


class CommunicationService:
    @staticmethod
    async def live_enabled(request) -> bool:
        return get_backend_config().enabled and bool(AuthService.get_access_token(request))

    @staticmethod
    async def use_mock(request) -> str:
        token = AuthService.get_access_token(request)
        if not token:
            raise BackendClientError("Backend authentication is required for communication.")
        return token

    @staticmethod
    async def effective_scope_path(request, ctx) -> dict[str, str]:
        identity = AuthService.get_identity(request)
        return split_scope_path(identity.scope_path if identity and identity.scope_path else ctx.current_scope_path)

    @staticmethod
    async def _scope_bits(request, ctx) -> dict[str, str]:
        return await CommunicationService.effective_scope_path(request, ctx)

    @staticmethod
    async def list_announcements(request, ctx, *, search: str = "", status: str = "all", meeting: str = "") -> list[dict[str, Any]]:
        identity = AuthService.get_identity(request)
        effective_path = str(identity.scope_path if identity and identity.scope_path else ctx.current_scope_path or "")
        identity_key = str(identity.user_id if identity else "demo")
        cache_key = ("communication", "announcements", identity_key, effective_path, meeting or "", status or "all")

        async def load_rows() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = await CommunicationService.use_mock(request)
            try:
                source = await maybe_await(ttl_cached(
                    cache_key,
                    45.0,
                        lambda: fetch_all_pages(lambda skip, limit: client.list_announcements(
                            access_token,
                            meeting=meeting or None,
                            is_active=False if status == "archived" else None,
                            skip=skip,
                            limit=limit,
                        ), page_size=200),
                ))
            except BackendClientError:
                raise
            return [_normalize_announcement(row) for row in source]

        rows = await request_cached(
            request,
            cache_key,
            load_rows,
        )
        if status != "all":
            rows = [row for row in rows if row["status"] == status]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["title"].lower()
                or term in row["summary"].lower()
                or term in row["audience"].lower()
                or term in row["meeting_label"].lower()
            ]
        return sorted(rows, key=lambda row: (row["meeting_date"], row["title"].lower()), reverse=True)

    @staticmethod
    async def announcement_summary_legacy(request, ctx) -> dict[str, int]:
        rows = await CommunicationService.list_announcements(request, ctx)
        return {
            "total": len(rows),
            "published": sum(1 for row in rows if row["status"] == "published"),
            "drafts": sum(1 for row in rows if row["status"] == "draft"),
            "archived": sum(1 for row in rows if row["status"] == "archived"),
        }

    @staticmethod
    async def get_announcement_legacy(request, announcement_id: str) -> dict[str, Any] | None:
        client = async_client(get_api_client())
        try:
            row = await client.get_announcement(await CommunicationService.use_mock(request), announcement_id)
        except BackendClientError:
            return None
        return _normalize_announcement(row)

    @staticmethod
    async def create_announcement_legacy(request, ctx, payload: dict[str, str]) -> dict[str, Any]:
        client = async_client(get_api_client())
        scope_bits = await CommunicationService._scope_bits(request, ctx)
        meeting_date = payload.get("meeting_date") or date.today().isoformat()
        region_id = scope_bits.get("region_id") or scope_bits.get("state_id") or scope_bits.get("nation_id") or scope_bits.get("location_id")
        if not region_id:
            raise BackendClientError("The current church scope does not have a valid announcement region.")
        backend_payload = {
            "region_id": region_id,
            "region_name": payload.get("audience") or ctx.current_scope_label,
            "meeting": payload.get("meeting") or "special_notice",
            "date": meeting_date,
            "items": _build_announcement_items(payload),
            "sws_bible_reading": payload.get("sws_bible_reading") or None,
            "sws_hymn": payload.get("sws_hymn") or None,
            "sws_topic": payload.get("sws_topic") or None,
            "mbs_bible_reading": payload.get("mbs_bible_reading") or None,
            "mbs_topic": payload.get("mbs_topic") or None,
            "sts_study": payload.get("sts_study") or None,
            "revival_topic": payload.get("revival_topic") or None,
            "revival_info": payload.get("revival_info") or None,
            "wedding_announcements": payload.get("wedding_announcements") or None,
            "general_announcements": payload.get("general_announcements") or None,
            "is_active": payload.get("submit_action") != "archive",
        }
        created = await client.create_announcement(await CommunicationService.use_mock(request), backend_payload)
        if payload.get("submit_action") == "publish":
            created = await client.publish_announcement(await CommunicationService.use_mock(request), str(created.get("id") or ""))
        invalidate_ttl_prefix(("communication", "announcements"))
        return _normalize_announcement(created)

    @staticmethod
    async def list_broadcasts(request) -> list[dict[str, Any]]:
        client = async_client(get_api_client())
        return await client.list_broadcasts(await CommunicationService.use_mock(request), limit=100)

    @staticmethod
    async def create_broadcast(request, payload: dict[str, Any]) -> dict[str, Any]:
        client = async_client(get_api_client())
        return await client.create_broadcast(await CommunicationService.use_mock(request), payload)

    @staticmethod
    async def update_announcement_legacy(request, ctx, announcement_id: str, payload: dict[str, str]) -> dict[str, Any]:
        client = async_client(get_api_client())
        backend_payload = {
            "region_name": payload.get("audience") or ctx.current_scope_label,
            "meeting": payload.get("meeting") or None,
            "date": payload.get("meeting_date") or None,
            "items": _build_announcement_items(payload),
            "sws_bible_reading": payload.get("sws_bible_reading") or None,
            "sws_hymn": payload.get("sws_hymn") or None,
            "sws_topic": payload.get("sws_topic") or None,
            "mbs_bible_reading": payload.get("mbs_bible_reading") or None,
            "mbs_topic": payload.get("mbs_topic") or None,
            "sts_study": payload.get("sts_study") or None,
            "revival_topic": payload.get("revival_topic") or None,
            "revival_info": payload.get("revival_info") or None,
            "wedding_announcements": payload.get("wedding_announcements") or None,
            "general_announcements": payload.get("general_announcements") or None,
            "is_active": True,
        }
        updated = await client.update_announcement(await CommunicationService.use_mock(request), announcement_id, backend_payload)
        if payload.get("submit_action") == "publish":
            updated = await client.publish_announcement(await CommunicationService.use_mock(request), announcement_id)
        invalidate_ttl_prefix(("communication", "announcements"))
        return _normalize_announcement(updated)

    @staticmethod
    async def set_announcement_status_legacy(request, announcement_id: str, *, action: str) -> dict[str, Any]:
        client = async_client(get_api_client())
        token = await CommunicationService.use_mock(request)
        if action == "publish":
            return _normalize_announcement(await client.publish_announcement(token, announcement_id))
        if action == "archive":
            updated = await client.update_announcement(token, announcement_id, {"is_active": False})
        elif action == "draft":
            updated = await client.update_announcement(token, announcement_id, {"is_active": True})
        else:
            raise BackendClientError("Unsupported announcement status action.")
        invalidate_ttl_prefix(("communication", "announcements"))
        return _normalize_announcement(updated)

    @staticmethod
    async def list_galleries(request, ctx, *, search: str = "", visibility: str = "all") -> list[dict[str, Any]]:
        identity = AuthService.get_identity(request)
        scope_path = identity.scope_path if identity and identity.scope_path else ctx.current_scope_path
        identity_key = str(identity.user_id if identity else "demo")
        gallery_cache_key = ("communication", "galleries", identity_key, scope_path)

        async def load_rows() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = await CommunicationService.use_mock(request)
            try:
                source = await maybe_await(ttl_cached(
                    gallery_cache_key,
                    45.0,
                    lambda: fetch_all_pages(lambda skip, limit: client.list_media_galleries(access_token, scope_path=scope_path, skip=skip, limit=limit), page_size=200),
                ))
            except BackendClientError:
                raise
            return [_normalize_gallery(row) for row in source]

        rows = await request_cached(
            request,
            gallery_cache_key,
            load_rows,
        )
        if visibility != "all":
            rows = [row for row in rows if row["visibility"] == visibility]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["title"].lower()
                or term in row["description"].lower()
                or term in row["scope_label"].lower()
            ]
        return sorted(rows, key=lambda row: (row["event_date"], row["title"].lower()), reverse=True)

    @staticmethod
    async def media_summary_legacy(request, ctx) -> dict[str, int]:
        rows = await CommunicationService.list_galleries(request, ctx)
        items = [item for row in rows for item in row["items"]]
        return {
            "galleries": len(rows),
            "items": len(items),
            "videos": sum(1 for item in items if item["media_type"] == "video"),
            "shared_upward": sum(1 for row in rows if row["visibility"] == "national_share"),
        }

    @staticmethod
    async def get_gallery_legacy(request, ctx, gallery_id: str) -> dict[str, Any] | None:
        client = async_client(get_api_client())
        access_token = await CommunicationService.use_mock(request)
        gallery = _normalize_gallery(await client.get_media_gallery(access_token, gallery_id))
        gallery["items"] = await CommunicationService.list_media_items(request, ctx, gallery_id=gallery_id)
        gallery["item_count"] = len(gallery["items"])
        gallery["photo_count"] = sum(1 for item in gallery["items"] if item["media_type"] == "photo")
        gallery["video_count"] = sum(1 for item in gallery["items"] if item["media_type"] == "video")
        return gallery

    @staticmethod
    async def create_gallery_legacy(request, ctx, payload: dict[str, str]) -> dict[str, Any]:
        client = async_client(get_api_client())
        locations = await PeopleService.list_locations(request, ctx)
        scope_bits = await CommunicationService._scope_bits(request, ctx)
        preferred_location = scope_bits.get("location_id") or (locations[0]["location_id"] if locations else "")
        created = await client.create_media_gallery(
            await CommunicationService.use_mock(request),
            {
                "title": payload.get("title") or "Gallery",
                "description": payload.get("description") or None,
                "location_id": preferred_location,
                "slug": (payload.get("title") or "gallery").lower().replace(" ", "-"),
                "is_public": payload.get("visibility") == "national_share",
            },
        )
        invalidate_ttl_prefix(("communication", "galleries"))
        return _normalize_gallery(created)

    @staticmethod
    async def list_media_items(request, ctx, *, search: str = "", media_type: str = "all", gallery_id: str = "") -> list[dict[str, Any]]:
        galleries = await CommunicationService.list_galleries(request, ctx)
        selected = [row for row in galleries if not gallery_id or row["gallery_id"] == gallery_id]
        items = [item for row in selected for item in row["items"]]
        if media_type != "all":
            items = [item for item in items if item["media_type"] == media_type]
        if search:
            term = search.lower().strip()
            items = [
                item
                for item in items
                if term in item["title"].lower()
                or term in item["caption"].lower()
                or term in item["file_label"].lower()
                or term in item["gallery_title"].lower()
            ]
        return sorted(items, key=lambda row: (row["uploaded_at"], row["title"].lower()), reverse=True)

    @staticmethod
    async def get_media_item(request, ctx, item_id: str) -> dict[str, Any] | None:
        return next((item for item in await CommunicationService.list_media_items(request, ctx) if item["item_id"] == item_id), None)

    @staticmethod
    async def create_media_item(request, ctx, gallery_id: str, payload: dict[str, str]) -> dict[str, Any]:
        client = async_client(get_api_client())
        media_type = payload.get("media_type") or "photo"
        created = await client.create_media_item(
            await CommunicationService.use_mock(request),
            {
                "gallery_id": gallery_id,
                "file_path": payload.get("file_label") or payload.get("title") or "backend-upload",
                "file_name": payload.get("title") or "Media item",
                "file_type": "video/mp4" if media_type == "video" else "image/jpeg",
                "file_size": 0,
                "caption": payload.get("caption") or None,
                "is_cover": False,
            },
        )
        invalidate_ttl_prefix(("communication", "galleries"))
        gallery = await CommunicationService.get_gallery(request, ctx, gallery_id)
        base_gallery = {
            "id": gallery_id,
            "title": gallery["title"] if gallery else "Gallery",
            "path": gallery["path"] if gallery else "",
            "is_public": gallery["visibility"] == "national_share" if gallery else False,
        }
        return _normalize_media_item(created, base_gallery)

    @staticmethod
    async def delete_gallery_legacy(request, ctx, gallery_id: str) -> dict[str, Any] | None:
        gallery = await CommunicationService.get_gallery(request, ctx, gallery_id)
        await async_client(get_api_client()).delete_media_gallery(await CommunicationService.use_mock(request), gallery_id)
        invalidate_ttl_prefix(("communication", "galleries"))
        return gallery

    @staticmethod
    async def delete_media_item_legacy(request, ctx, item_id: str) -> dict[str, Any] | None:
        item = await CommunicationService.get_media_item(request, ctx, item_id)
        await async_client(get_api_client()).delete_media_item(await CommunicationService.use_mock(request), item_id)
        invalidate_ttl_prefix(("communication", "galleries"))
        return item


async def _announcement_summary(request, ctx):
    rows = await CommunicationService.list_announcements(request, ctx)
    return {"total": len(rows), "published": sum(row["status"] == "published" for row in rows), "drafts": sum(row["status"] == "draft" for row in rows), "archived": sum(row["status"] == "archived" for row in rows)}


async def _get_announcement(request, announcement_id: str):
    client = async_client(get_api_client())
    row = await client.get_announcement(await CommunicationService.use_mock(request), announcement_id)
    return _normalize_announcement(row)


async def _create_announcement(request, ctx, payload: dict[str, str]):
    client = async_client(get_api_client())
    scope_bits = await CommunicationService._scope_bits(request, ctx)
    region_id = scope_bits.get("region_id") or scope_bits.get("state_id") or scope_bits.get("nation_id") or scope_bits.get("location_id")
    if not region_id:
        raise BackendClientError("The current church scope does not have a valid announcement region.")
    created = await client.create_announcement(await CommunicationService.use_mock(request), {
        "region_id": region_id,
        "region_name": payload.get("audience") or ctx.current_scope_label,
        "meeting": payload.get("meeting") or "special_notice",
        "date": payload.get("meeting_date") or date.today().isoformat(),
        "items": _build_announcement_items(payload),
        "is_active": payload.get("submit_action") != "archive",
    })
    if payload.get("submit_action") == "publish":
        created = await client.publish_announcement(await CommunicationService.use_mock(request), str(created.get("id") or ""))
    invalidate_ttl_prefix(("communication", "announcements"))
    return _normalize_announcement(created)


async def _update_announcement(request, ctx, announcement_id: str, payload: dict[str, str]):
    client = async_client(get_api_client())
    updated = await client.update_announcement(await CommunicationService.use_mock(request), announcement_id, {
        "region_name": payload.get("audience") or ctx.current_scope_label,
        "meeting": payload.get("meeting") or None,
        "date": payload.get("meeting_date") or None,
        "items": _build_announcement_items(payload),
        "is_active": True,
    })
    if payload.get("submit_action") == "publish":
        updated = await client.publish_announcement(await CommunicationService.use_mock(request), announcement_id)
    invalidate_ttl_prefix(("communication", "announcements"))
    return _normalize_announcement(updated)


async def _set_announcement_status(request, announcement_id: str, *, action: str):
    client = async_client(get_api_client())
    token = await CommunicationService.use_mock(request)
    if action == "publish":
        updated = await client.publish_announcement(token, announcement_id)
    elif action in {"archive", "draft"}:
        updated = await client.update_announcement(token, announcement_id, {"is_active": action == "draft"})
    else:
        raise BackendClientError("Unsupported announcement status action.")
    invalidate_ttl_prefix(("communication", "announcements"))
    return _normalize_announcement(updated)


async def _media_summary(request, ctx):
    rows = await CommunicationService.list_galleries(request, ctx)
    items = [item for row in rows for item in row["items"]]
    return {"galleries": len(rows), "items": len(items), "videos": sum(item["media_type"] == "video" for item in items), "shared_upward": sum(row["visibility"] == "national_share" for row in rows)}


async def _get_gallery(request, ctx, gallery_id: str):
    client = async_client(get_api_client())
    row = _normalize_gallery(await client.get_media_gallery(await CommunicationService.use_mock(request), gallery_id))
    row["items"] = await CommunicationService.list_media_items(request, ctx, gallery_id=gallery_id)
    row["item_count"] = len(row["items"])
    row["photo_count"] = sum(item["media_type"] == "photo" for item in row["items"])
    row["video_count"] = sum(item["media_type"] == "video" for item in row["items"])
    return row


async def _create_gallery(request, ctx, payload: dict[str, str]):
    client = async_client(get_api_client())
    locations = await PeopleService.list_locations(request, ctx)
    scope_bits = await CommunicationService._scope_bits(request, ctx)
    location_id = scope_bits.get("location_id") or (locations[0]["location_id"] if locations else "")
    if not location_id:
        raise BackendClientError("A location in the current scope is required to create a gallery.")
    created = await client.create_media_gallery(await CommunicationService.use_mock(request), {
        "title": payload.get("title") or "Gallery",
        "description": payload.get("description") or None,
        "location_id": location_id,
        "slug": (payload.get("title") or "gallery").lower().replace(" ", "-"),
        "is_public": payload.get("visibility") == "national_share",
    })
    invalidate_ttl_prefix(("communication", "galleries"))
    return _normalize_gallery(created)


async def _delete_gallery(request, ctx, gallery_id: str):
    gallery = await _get_gallery(request, ctx, gallery_id)
    await async_client(get_api_client()).delete_media_gallery(await CommunicationService.use_mock(request), gallery_id)
    invalidate_ttl_prefix(("communication", "galleries"))
    return gallery


async def _delete_media_item(request, ctx, item_id: str):
    item = await CommunicationService.get_media_item(request, ctx, item_id)
    if item is None:
        return None
    await async_client(get_api_client()).delete_media_item(await CommunicationService.use_mock(request), item_id)
    invalidate_ttl_prefix(("communication", "galleries"))
    return item


CommunicationService.announcement_summary = staticmethod(_announcement_summary)
CommunicationService.get_announcement = staticmethod(_get_announcement)
CommunicationService.create_announcement = staticmethod(_create_announcement)
CommunicationService.update_announcement = staticmethod(_update_announcement)
CommunicationService.set_announcement_status = staticmethod(_set_announcement_status)
CommunicationService.media_summary = staticmethod(_media_summary)
CommunicationService.get_gallery = staticmethod(_get_gallery)
CommunicationService.create_gallery = staticmethod(_create_gallery)
CommunicationService.delete_gallery = staticmethod(_delete_gallery)
CommunicationService.delete_media_item = staticmethod(_delete_media_item)

dual_mode_class(CommunicationService)

__all__ = ["CommunicationService"]
