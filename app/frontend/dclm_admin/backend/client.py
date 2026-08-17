from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .config import BackendConfig, get_backend_config

logger = logging.getLogger(__name__)

# Module-level singleton async client avoids per-call client creation overhead.
_ASYNC_CLIENT: Any = None


class BackendClientError(RuntimeError):
    pass


def _get_async_http_client(config: BackendConfig) -> Any:
    """Return the module-level httpx.AsyncClient, creating it if needed."""
    global _ASYNC_CLIENT
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - defensive guard
        raise BackendClientError("httpx is required for backend integration.") from exc
    if _ASYNC_CLIENT is None or _ASYNC_CLIENT.is_closed:
        import os
        single_instance = (
            config.base_url in ("internal://asgi", "asgi", "single-instance")
            or os.getenv("DCLM_SINGLE_INSTANCE", "true").strip().lower() in {"1", "true", "yes", "on"}
        )
        asgi_app = None
        if single_instance:
            try:
                from app.main import app as _backend_app
                asgi_app = _backend_app
            except ImportError:
                asgi_app = None

        if asgi_app is not None:
            _ASYNC_CLIENT = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=asgi_app),
                base_url="http://dclm.internal",
                timeout=config.timeout_seconds,
                follow_redirects=True,
            )
            logger.info("Initialized BackendClient with ultra-fast in-memory ASGI transport (zero TCP overhead).")
        else:
            limits = httpx.Limits(
                max_connections=40,
                max_keepalive_connections=20,
                keepalive_expiry=30,
            )
            _ASYNC_CLIENT = httpx.AsyncClient(
                timeout=config.timeout_seconds,
                verify=config.verify_ssl,
                limits=limits,
                http2=False,
                follow_redirects=True,
            )
    return _ASYNC_CLIENT


async def close_async_http_client() -> None:
    """Close the shared HTTP client on application shutdown."""
    global _ASYNC_CLIENT
    if _ASYNC_CLIENT is not None and not _ASYNC_CLIENT.is_closed:
        await _ASYNC_CLIENT.aclose()
    _ASYNC_CLIENT = None


@dataclass
class BackendClient:
    config: BackendConfig | None = None

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = get_backend_config()

    def build_url(self, path: str, *, api_path: bool = True) -> str:
        import os
        single_instance = (
            self.config.base_url in ("internal://asgi", "asgi", "single-instance")
            or os.getenv("DCLM_SINGLE_INSTANCE", "true").strip().lower() in {"1", "true", "yes", "on"}
        )
        if single_instance:
            prefix = self.config.api_prefix if api_path else ""
            normalized_path = path if path.startswith("/") else f"/{path}"
            return f"{prefix}{normalized_path}"
        base = self.config.api_base_url if api_path else self.config.normalized_base_url
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{base}{normalized_path}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        api_path: bool = True,
        access_token: str | None = None,
        json: Any | None = None,
        data: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - defensive guard
            raise BackendClientError("httpx is required for backend integration.") from exc

        request_headers = dict(headers or {})
        if access_token:
            request_headers["Authorization"] = f"Bearer {access_token}"

        url = self.build_url(path, api_path=api_path)
        try:
            response = await _get_async_http_client(self.config).request(
                method=method.upper(),
                url=url,
                json=json,
                data=data,
                params=params,
                headers=request_headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Backend error %s on %s %s",
                exc.response.status_code,
                method.upper(),
                url,
            )
            raise BackendClientError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise BackendClientError(str(exc)) from exc

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    async def _request_binary(
        self,
        method: str,
        path: str,
        *,
        api_path: bool = True,
        access_token: str | None = None,
        json: Any | None = None,
        data: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - defensive guard
            raise BackendClientError("httpx is required for backend integration.") from exc

        request_headers = dict(headers or {})
        if access_token:
            request_headers["Authorization"] = f"Bearer {access_token}"

        url = self.build_url(path, api_path=api_path)
        client = _get_async_http_client(self.config)
        try:
            # Use streaming to avoid loading large export files fully into memory.
            async with client.stream(
                method=method.upper(),
                url=url,
                json=json,
                data=data,
                params=params,
                headers=request_headers,
            ) as response:
                response.raise_for_status()
                content = await response.aread()
                return content, dict(response.headers)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Backend error %s on %s %s",
                exc.response.status_code,
                method.upper(),
                url,
            )
            raise BackendClientError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise BackendClientError(str(exc)) from exc


    async def login(self, *, username: str, password: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/auth/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        return await self._request("POST", "/auth/refresh", access_token=refresh_token)

    async def get_current_user(self, access_token: str) -> dict[str, Any]:
        return await self._request("GET", "/auth/me", access_token=access_token)

    async def get_health(self) -> dict[str, Any]:
        return await self._request("GET", "/health", api_path=False)

    async def get_system_metadata(self, access_token: str) -> dict[str, Any]:
        return await self._request("GET", "/system/meta", access_token=access_token)

    async def get_system_metrics(self, access_token: str) -> dict[str, Any]:
        return await self._request("GET", "/system/metrics", access_token=access_token)

    async def list_audit_logs(self, access_token: str, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._request("GET", "/system/audit-logs", access_token=access_token, params={"skip": skip, "limit": limit})

    async def seed_database(self, access_token: str, *, confirm: bool = True) -> dict[str, Any]:
        return await self._request("POST", "/system/seed", access_token=access_token, params={"confirm": confirm})

    async def get_sync_changes(self, access_token: str, *, since: str) -> dict[str, Any]:
        return await self._request("GET", "/sync/changes", access_token=access_token, params={"since": since})

    async def list_sync_conflicts(self, access_token: str) -> dict[str, Any]:
        return await self._request("GET", "/sync/conflicts", access_token=access_token)

    async def resolve_sync_conflict(self, access_token: str, conflict_id: str, resolution: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/sync/resolve",
            access_token=access_token,
            json={"conflict_id": conflict_id, "resolution": resolution},
        )

    async def list_public_contact_submissions(
        self,
        access_token: str,
        *,
        status: str | None = None,
        search: str | None = None,
        skip: int = 0,  
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        return await self._request("GET", "/system/public-contact-submissions", access_token=access_token, params=params)

    async def review_public_contact_submission(self, access_token: str, submission_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/system/public-contact-submissions/{submission_id}/review", access_token=access_token, json=payload)

    async def list_public_prayer_submissions(
        self,
        access_token: str,
        *,
        status: str | None = None,
        urgent: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if status:
            params["status"] = status
        if urgent is not None:
            params["urgent"] = urgent
        if search:
            params["search"] = search
        return await self._request("GET", "/system/public-prayer-submissions", access_token=access_token, params=params)

    async def review_public_prayer_submission(self, access_token: str, submission_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/system/public-prayer-submissions/{submission_id}/review", access_token=access_token, json=payload)

    async def poll_notifications(self, access_token: str, *, since: str) -> dict[str, list[dict[str, Any]]]:
        return await self._request("GET", "/notifications/poll", access_token=access_token, params={"since": since})

    async def get_notification_history(
        self,
        access_token: str,
        *,
        since: str | None = None,
        days: int = 14,
        kind: str = "all",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"days": days, "kind": kind, "limit": limit}
        if since:
            params["since"] = since
        return await self._request("GET", "/notifications/history", access_token=access_token, params=params)

    async def mark_notification_read(self, access_token: str, notification_key: str) -> dict[str, Any]:
        return await self._request("POST", f"/notifications/{notification_key}/read", access_token=access_token)

    async def mark_notification_unread(self, access_token: str, notification_key: str) -> dict[str, Any]:
        return await self._request("POST", f"/notifications/{notification_key}/unread", access_token=access_token)

    async def list_app_versions(
        self,
        access_token: str,
        *,
        skip: int = 0,
        limit: int = 100,
        app_name: str | None = None,
        platform: str | None = None,
        version_number: str | None = None,
        release_date: str | None = None,
        is_active: bool | None = None,
        get_last: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit, "get_last": get_last}
        if app_name:
            params["app_name"] = app_name
        if platform:
            params["platform"] = platform
        if version_number:
            params["version_number"] = version_number
        if release_date:
            params["release_date"] = release_date
        if is_active is not None:
            params["is_active"] = is_active
        return await self._request("GET", "/app-versions/", access_token=access_token, params=params)

    async def get_app_version(self, access_token: str, version_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/app-versions/{version_id}", access_token=access_token)

    async def create_app_version(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/app-versions/", access_token=access_token, json=payload)

    async def update_app_version(self, access_token: str, version_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/app-versions/{version_id}", access_token=access_token, json=payload)

    async def list_workers(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        return await self._request("GET", "/workers/", access_token=access_token, params=params)

    async def list_users(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        return await self._request("GET", "/users/", access_token=access_token, params=params)

    async def list_official_appointments(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        search: str | None = None,
        status: str | None = None,
        appointed_role: str | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        if appointed_role:
            params["appointed_role"] = appointed_role
        return await self._request("GET", "/official-appointments/", access_token=access_token, params=params)

    async def get_official_appointment(self, access_token: str, appointment_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/official-appointments/{appointment_id}", access_token=access_token)

    async def create_official_appointment(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/official-appointments/", access_token=access_token, json=payload)

    async def update_official_appointment(self, access_token: str, appointment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/official-appointments/{appointment_id}", access_token=access_token, json=payload)

    async def revoke_official_appointment(self, access_token: str, appointment_id: str, note: str | None = None) -> dict[str, Any]:
        return await self._request("POST", f"/official-appointments/{appointment_id}/revoke", access_token=access_token, json={"note": note})

    async def list_members(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        skip: int = 0,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        if location_id:
            params["location_id"] = location_id
        return await self._request("GET", "/members", access_token=access_token, params=params)

    async def get_member(self, access_token: str, member_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/members/{member_id}", access_token=access_token)

    async def create_member(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/members", access_token=access_token, json=payload)

    async def list_locations(self, access_token: str, *, skip: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        return await self._request("GET", "/locations/", access_token=access_token, params={"skip": skip, "limit": limit})

    async def list_fellowships(
        self,
        access_token: str,
        *,
        location_id: str | None = None,
        skip: int = 0,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if location_id:
            params["location_id"] = location_id
        return await self._request("GET", "/fellowships/", access_token=access_token, params=params)

    async def get_fellowship(self, access_token: str, fellowship_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/fellowships/{fellowship_id}", access_token=access_token)

    async def create_fellowship(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fellowships/", access_token=access_token, json=payload)

    async def list_fellowship_members(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._request("GET", "/fellowships/members", access_token=access_token, params={"fellowship_id": fellowship_id, "skip": skip, "limit": limit})

    async def create_fellowship_member(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fellowships/members", access_token=access_token, json=payload)

    async def list_fellowship_attendance(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._request("GET", "/fellowships/attendance", access_token=access_token, params={"fellowship_id": fellowship_id, "skip": skip, "limit": limit})

    async def create_fellowship_attendance(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fellowships/attendance", access_token=access_token, json=payload)

    async def list_fellowship_offerings(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._request("GET", "/fellowships/offerings", access_token=access_token, params={"fellowship_id": fellowship_id, "skip": skip, "limit": limit})

    async def create_fellowship_offering(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fellowships/offerings", access_token=access_token, json=payload)

    async def list_fellowship_testimonies(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._request("GET", "/fellowships/testimonies", access_token=access_token, params={"fellowship_id": fellowship_id, "skip": skip, "limit": limit})

    async def create_fellowship_testimony(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fellowships/testimonies", access_token=access_token, json=payload)

    async def list_fellowship_prayers(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._request("GET", "/fellowships/prayers", access_token=access_token, params={"fellowship_id": fellowship_id, "skip": skip, "limit": limit})

    async def create_fellowship_prayer(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fellowships/prayers", access_token=access_token, json=payload)

    async def list_fellowship_summaries(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._request("GET", "/fellowships/attendance-summaries", access_token=access_token, params={"fellowship_id": fellowship_id, "skip": skip, "limit": limit})

    async def list_announcements(
        self,
        access_token: str,
        *,
        meeting: str | None = None,
        is_active: bool | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if meeting:
            params["meeting"] = meeting
        if is_active is not None:
            params["is_active"] = is_active
        return await self._request("GET", "/announcements/", access_token=access_token, params=params)

    async def get_announcement(self, access_token: str, announcement_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/announcements/{announcement_id}", access_token=access_token)

    async def create_announcement(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/announcements/", access_token=access_token, json=payload)

    async def update_announcement(self, access_token: str, announcement_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/announcements/{announcement_id}", access_token=access_token, json=payload)

    async def publish_announcement(self, access_token: str, announcement_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/announcements/{announcement_id}/publish", access_token=access_token)

    async def delete_announcement(self, access_token: str, announcement_id: str) -> Any:
        return await self._request("DELETE", f"/announcements/{announcement_id}", access_token=access_token)

    async def list_media_galleries(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        return await self._request("GET", "/media/galleries", access_token=access_token, params=params)

    async def get_media_gallery(self, access_token: str, gallery_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/media/galleries/{gallery_id}", access_token=access_token)

    async def create_media_gallery(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/media/galleries", access_token=access_token, json=payload)

    async def delete_media_gallery(self, access_token: str, gallery_id: str) -> Any:
        return await self._request("DELETE", f"/media/galleries/{gallery_id}", access_token=access_token)

    async def list_media_items(self, access_token: str, *, gallery_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._request("GET", f"/media/galleries/{gallery_id}/items", access_token=access_token, params={"skip": skip, "limit": limit})

    async def create_media_item(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/media/items", access_token=access_token, json=payload)

    async def delete_media_item(self, access_token: str, item_id: str) -> Any:
        return await self._request("DELETE", f"/media/items/{item_id}", access_token=access_token)

    async def get_location_details(self, access_token: str, location_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/locations/{location_id}/details", access_token=access_token)

    async def get_location(self, access_token: str, location_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/locations/{location_id}", access_token=access_token)

    async def update_location(self, access_token: str, location_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/locations/{location_id}", access_token=access_token, json=payload)

    async def list_hierarchy_tree(self, access_token: str) -> list[dict[str, Any]]:
        return await self._request("GET", "/hierarchy/tree", access_token=access_token)

    async def search_hierarchy(self, access_token: str, query: str) -> list[dict[str, Any]]:
        return await self._request("GET", "/hierarchy/search", access_token=access_token, params={"query": query})

    async def get_location_profile(self, access_token: str, location_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/locations/{location_id}/profile", access_token=access_token)

    async def upsert_location_profile(self, access_token: str, location_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/locations/{location_id}/profile", access_token=access_token, json=payload)

    async def create_worker(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/workers/", access_token=access_token, json=payload)

    async def create_user(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/users/", access_token=access_token, json=payload)

    async def list_program_events(self, access_token: str, *, scope_path: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        return await self._request("GET", "/programs/events", access_token=access_token, params=params)

    async def get_program_event(self, access_token: str, event_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/programs/events/{event_id}", access_token=access_token)

    async def create_program_event(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/programs/events", access_token=access_token, json=payload)

    async def list_program_campaigns(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        program_domain: str | None = None,
        event_mode: str | None = None,
        status_value: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        if program_domain:
            params["program_domain"] = program_domain
        if event_mode:
            params["event_mode"] = event_mode
        if status_value:
            params["status_value"] = status_value
        return await self._request("GET", "/programs/campaigns", access_token=access_token, params=params)

    async def get_program_campaign(self, access_token: str, campaign_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/programs/campaigns/{campaign_id}", access_token=access_token)

    async def create_program_campaign(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/programs/campaigns", access_token=access_token, json=payload)

    async def list_event_assignments(self, access_token: str, event_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/programs/events/{event_id}/assignments", access_token=access_token)

    async def create_event_assignment(self, access_token: str, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/programs/events/{event_id}/assignments", access_token=access_token, json=payload)

    async def approve_event_assignment(self, access_token: str, assignment_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/programs/assignments/{assignment_id}/approve", access_token=access_token)

    async def reject_event_assignment(self, access_token: str, assignment_id: str, note: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if note:
            params["note"] = note
        return await self._request("POST", f"/programs/assignments/{assignment_id}/reject", access_token=access_token, params=params or None)

    async def list_program_domains(self, access_token: str, *, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._request("GET", "/programs/domains", access_token=access_token, params={"skip": skip, "limit": limit})

    async def get_program_domain(self, access_token: str, domain_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/programs/domains/{domain_id}", access_token=access_token)

    async def create_program_domain(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/programs/domains", access_token=access_token, json=payload)

    async def list_program_types(
        self,
        access_token: str,
        *,
        domain_id: int | str | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if domain_id not in (None, ""):
            params["domain_id"] = domain_id
        return await self._request("GET", "/programs/types", access_token=access_token, params=params)

    async def get_program_type(self, access_token: str, type_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/programs/types/{type_id}", access_token=access_token)

    async def create_program_type(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/programs/types", access_token=access_token, json=payload)

    async def list_counts(self, access_token: str, *, scope_path: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        return await self._request("GET", "/counts/", access_token=access_token, params=params)

    async def create_count(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/counts/", access_token=access_token, json=payload)

    async def list_offerings(self, access_token: str, *, scope_path: str | None = None, fund_type: str | None = None, location_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        if fund_type:
            params["fund_type"] = fund_type
        if location_id:
            params["location_id"] = location_id
        return await self._request("GET", "/offerings/", access_token=access_token, params=params)

    async def create_offering(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/offerings/", access_token=access_token, json=payload)

    async def list_records(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        return await self._request("GET", "/records/", access_token=access_token, params=params)

    async def get_record(self, access_token: str, record_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/records/{record_id}", access_token=access_token)

    async def create_record(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/records/", access_token=access_token, json=payload)

    async def list_attendance(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        return await self._request("GET", "/attendance/", access_token=access_token, params=params)

    async def get_attendance(self, access_token: str, attendance_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/attendance/{attendance_id}", access_token=access_token)

    async def create_attendance(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/attendance/", access_token=access_token, json=payload)

    async def get_attendance_stats(self, access_token: str, *, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/attendance/stats", access_token=access_token, params=params or None)

    async def get_population_statistics(
        self,
        access_token: str,
        *,
        program_domain: str | None = None,
        program_type: str | None = None,
        location_id: str | None = None,
        start_month: int | None = None,
        end_month: int | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if program_domain:
            params["program_domain"] = program_domain
        if program_type:
            params["program_type"] = program_type
        if location_id:
            params["location_id"] = location_id
        if start_month is not None:
            params["start_month"] = start_month
        if end_month is not None:
            params["end_month"] = end_month
        if start_year is not None:
            params["start_year"] = start_year
        if end_year is not None:
            params["end_year"] = end_year
        return await self._request("GET", "/statistics/read-population/", access_token=access_token, params=params or None)

    async def get_church_statistics(self, access_token: str) -> dict[str, Any]:
        return await self._request("GET", "/statistics/church-statistics/", access_token=access_token)

    async def get_user_statistics(self, access_token: str) -> dict[str, Any]:
        return await self._request("GET", "/statistics/get-user-statistics/", access_token=access_token)

    async def get_dashboard_summary(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if scope_path:
            params["scope_path"] = scope_path
        if location_id:
            params["location_id"] = location_id
        return await self._request("GET", "/dashboard/summary", access_token=access_token, params=params or None)

    async def get_dashboard_bootstrap(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        months: int = 12,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"months": months}
        if scope_path:
            params["scope_path"] = scope_path
        if location_id:
            params["location_id"] = location_id
        if sections:
            params["sections"] = sections
        return await self._request("GET", "/dashboard/bootstrap", access_token=access_token, params=params)

    async def get_dashboard_member_analytics(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        months: int = 12,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"months": months}
        if scope_path:
            params["scope_path"] = scope_path
        if location_id:
            params["location_id"] = location_id
        return await self._request("GET", "/dashboard/member-analytics", access_token=access_token, params=params)

    async def get_dashboard_worker_analytics(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if scope_path:
            params["scope_path"] = scope_path
        if location_id:
            params["location_id"] = location_id
        return await self._request("GET", "/dashboard/worker-analytics", access_token=access_token, params=params or None)

    async def get_dashboard_program_comparison(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        if location_id:
            params["location_id"] = location_id
        return await self._request("GET", "/dashboard/program-comparison", access_token=access_token, params=params)

    async def get_dashboard_worker_meeting_comparison(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        if location_id:
            params["location_id"] = location_id
        return await self._request("GET", "/dashboard/worker-meeting-comparison", access_token=access_token, params=params)

    async def get_dashboard_newcomer_analytics(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        months: int = 12,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"months": months}
        if scope_path:
            params["scope_path"] = scope_path
        if location_id:
            params["location_id"] = location_id
        return await self._request("GET", "/dashboard/newcomer-analytics", access_token=access_token, params=params)

    async def get_report_summary(self, access_token: str, *, scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if scope_path:
            params["scope_path"] = scope_path
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/reports/summary", access_token=access_token, params=params or None)

    async def get_report_financial(self, access_token: str, *, scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if scope_path:
            params["scope_path"] = scope_path
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/reports/financial", access_token=access_token, params=params or None)

    async def get_report_attendance(self, access_token: str, *, scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if scope_path:
            params["scope_path"] = scope_path
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/reports/attendance", access_token=access_token, params=params or None)

    async def get_report_timeseries(self, access_token: str, *, metric: str, interval: str = "daily", scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"metric": metric, "interval": interval}
        if scope_path:
            params["scope_path"] = scope_path
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/reports/timeseries", access_token=access_token, params=params)

    async def get_report_breakdown(self, access_token: str, *, metric: str, level: str, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"metric": metric, "level": level}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/reports/by-level", access_token=access_token, params=params)

    async def get_report_anomalies(self, access_token: str, *, metric: str = "counts", threshold: float = 2.0, days: int = 30) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/reports/anomalies",
            access_token=access_token,
            params={"metric": metric, "threshold": threshold, "days": days},
        )

    async def get_report_growth(self, access_token: str, *, metric: str = "counts", period: str = "monthly", months: int = 12) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/reports/growth-rate",
            access_token=access_token,
            params={"metric": metric, "period": period, "months": months},
        )

    async def refresh_reports(self, access_token: str) -> dict[str, Any]:
        return await self._request("POST", "/reports/refresh", access_token=access_token)

    async def export_report_csv(self, access_token: str, *, report_type: str, scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> tuple[bytes, dict[str, str]]:
        params: dict[str, Any] = {"report_type": report_type}
        if scope_path:
            params["scope_path"] = scope_path
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request_binary("GET", "/reports/export/csv", access_token=access_token, params=params)

    async def export_report_excel(self, access_token: str, *, report_type: str, start_date: str | None = None, end_date: str | None = None) -> tuple[bytes, dict[str, str]]:
        params: dict[str, Any] = {"report_type": report_type}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request_binary("POST", "/reports/export/excel", access_token=access_token, params=params)

    async def export_report_pdf(self, access_token: str, *, report_type: str, start_date: str | None = None, end_date: str | None = None) -> tuple[bytes, dict[str, str]]:
        params: dict[str, Any] = {"report_type": report_type}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request_binary("POST", "/reports/export/pdf", access_token=access_token, params=params)

    async def get_worker(self, access_token: str, worker_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/workers/{worker_id}", access_token=access_token)

    async def list_pending_workers(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if scope_path:
            params["scope_path"] = scope_path
        return await self._request("GET", "/workers/pending", access_token=access_token, params=params)

    async def get_user_details(self, access_token: str, user_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/users/{user_id}/details", access_token=access_token)

    async def update_user(self, access_token: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/users/{user_id}", access_token=access_token, json=payload)

    async def assign_roles(self, access_token: str, user_id: str, role_ids: list[int]) -> dict[str, Any]:
        return await self._request("POST", f"/users/{user_id}/assign-roles", access_token=access_token, json={"role_ids": role_ids})

    async def list_available_roles(self, access_token: str) -> list[dict[str, Any]]:
        return await self._request("GET", "/rbac/roles/available", access_token=access_token)

    async def list_rbac_roles(self, access_token: str, *, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._request("GET", "/rbac/roles", access_token=access_token, params={"skip": skip, "limit": limit})

    async def get_rbac_role(self, access_token: str, role_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/rbac/roles/{role_id}", access_token=access_token)

    async def update_rbac_role(self, access_token: str, role_id: int | str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/rbac/roles/{role_id}", access_token=access_token, json=payload)

    async def list_rbac_permissions(self, access_token: str, *, skip: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        return await self._request("GET", "/rbac/permissions", access_token=access_token, params={"skip": skip, "limit": limit})

    async def get_rbac_permission(self, access_token: str, permission_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/rbac/permissions/{permission_id}", access_token=access_token)

    async def list_rbac_scores(self, access_token: str, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._request("GET", "/rbac/scores", access_token=access_token, params={"skip": skip, "limit": limit})

    async def list_pending_users(self, access_token: str, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._request("GET", "/users/pending", access_token=access_token, params={"skip": skip, "limit": limit})

    async def approve_user(self, access_token: str, user_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/users/{user_id}/approve", access_token=access_token)

    async def reject_user(self, access_token: str, user_id: str, reason: str) -> dict[str, Any]:
        return await self._request("POST", f"/users/{user_id}/reject", access_token=access_token, json={"reason": reason})

    async def deactivate_user(self, access_token: str, user_id: str, reason: str | None = None) -> dict[str, Any]:
        return await self._request("POST", f"/users/{user_id}/deactivate", access_token=access_token, json={"reason": reason or ""})

    async def reactivate_user(self, access_token: str, user_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/users/{user_id}/reactivate", access_token=access_token)

    async def approve_worker(self, access_token: str, worker_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/workers/{worker_id}/approve", access_token=access_token)

    async def reject_worker(self, access_token: str, worker_id: str, reason: str) -> dict[str, Any]:
        return await self._request("POST", f"/workers/{worker_id}/reject", access_token=access_token, params={"reason": reason})

    async def list_transfer_requests(self, access_token: str, *, status: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if status and status != "all":
            params["status"] = status
        return await self._request("GET", "/approvals/transfers", access_token=access_token, params=params)

    async def approve_transfer_request(self, access_token: str, request_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/approvals/transfers/{request_id}/approve", access_token=access_token)

    async def reject_transfer_request(self, access_token: str, request_id: str, reason: str | None = None) -> dict[str, Any]:
        params = {"reason": reason} if reason else None
        return await self._request("POST", f"/approvals/transfers/{request_id}/reject", access_token=access_token, params=params)

    async def list_status_change_requests(self, access_token: str, *, status: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if status and status != "all":
            params["status"] = status
        return await self._request("GET", "/approvals/status-changes", access_token=access_token, params=params)

    async def approve_status_change_request(self, access_token: str, request_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/approvals/status-changes/{request_id}/approve", access_token=access_token)

    async def reject_status_change_request(self, access_token: str, request_id: str, reason: str | None = None) -> dict[str, Any]:
        params = {"reason": reason} if reason else None
        return await self._request("POST", f"/approvals/status-changes/{request_id}/reject", access_token=access_token, params=params)

    async def list_removal_requests(self, access_token: str, *, status: str | None = None, current_level: int | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if status and status != "all":
            params["status"] = status
        if current_level is not None:
            params["current_level"] = current_level
        return await self._request("GET", "/approvals/removals", access_token=access_token, params=params)

    async def approve_removal_request(self, access_token: str, request_id: str, notes: str | None = None) -> dict[str, Any]:
        return await self._request("POST", f"/approvals/removals/{request_id}/approve", access_token=access_token, json={"notes": notes or ""})

    async def reject_removal_request(self, access_token: str, request_id: str, notes: str | None = None) -> dict[str, Any]:
        return await self._request("POST", f"/approvals/removals/{request_id}/reject", access_token=access_token, json={"notes": notes or ""})

    async def escalate_removal_request(self, access_token: str, request_id: str, notes: str) -> dict[str, Any]:
        return await self._request("POST", f"/approvals/removals/{request_id}/escalate", access_token=access_token, json={"notes": notes})

    async def create_transfer_request(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/approvals/transfers", access_token=access_token, json=payload)

    async def create_status_change_request(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/approvals/status-changes", access_token=access_token, json=payload)

    async def create_removal_request(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/approvals/removals", access_token=access_token, json=payload)

