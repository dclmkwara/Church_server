from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
import os
from time import perf_counter, time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from starlette.requests import Request
from starlette.responses import Response

from ..backend import BackendClientError, get_backend_config, profile_key_for_score
from .api_client import get_api_client
from app.core.security import create_admin_access_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthIdentity:
    user_id: str
    access_token: str
    refresh_token: str
    user: dict[str, Any]
    profile_key: str
    role_score: int
    role_name: str
    scope_path: str
    home_path: str
    maximum_scope_path: str = ""

    @property
    def display_name(self) -> str:
        """Return the display name persisted with this authenticated identity."""
        return str(self.user.get("name") or self.user.get("email") or "Authenticated User")

    @property
    def email(self) -> str:
        """Return the email persisted with this authenticated identity."""
        return str(self.user.get("email") or "")

    @property
    def permissions(self) -> frozenset[str]:
        """Return the backend permissions cached for this session."""
        return frozenset(str(permission) for permission in (self.user.get("permissions") or []))

    def has_permission(self, permission: str) -> bool:
        """Check whether the authenticated identity carries a permission."""
        return permission in self.permissions


class AuthService:
    REFRESH_WINDOW_SECONDS = 180

    @staticmethod
    def _refresh_cookie_name() -> str:
        return f"{get_backend_config().access_cookie_name}_refreshed_at"

    @staticmethod
    def _cookie_value(request: Request, name: str, default: str | None = None) -> str | None:
        if not hasattr(request, "cookies"):
            return default
        value = request.cookies.get(name)
        if value is None or value == "":
            return default
        return value

    @staticmethod
    def _best_role(user: dict[str, Any]) -> tuple[int, str]:
        roles = user.get("roles") or []
        best_score = 0
        best_name = "Worker"
        for role in roles:
            score_value = int(role.get("score_value") or 0)
            if score_value >= best_score:
                best_score = score_value
                best_name = str(role.get("role_name") or best_name)
        return best_score, best_name

    @classmethod
    def _identity_from_payload(cls, *, tokens: dict[str, Any], user: dict[str, Any]) -> AuthIdentity:
        """Separate assigned hierarchy from the role-derived maximum scope."""
        role_score, role_name = cls._best_role(user)
        assigned_path = str(user.get("path") or "")
        home_path = create_admin_access_id(assigned_path, role_score or 2) if assigned_path else ""
        return AuthIdentity(
            user_id=str(user.get("user_id") or ""),
            access_token=str(tokens.get("access_token") or ""),
            refresh_token=str(tokens.get("refresh_token") or ""),
            user=user,
            profile_key=profile_key_for_score(role_score or 2),
            role_score=role_score,
            role_name=role_name,
            scope_path=home_path,
            home_path=home_path,
            maximum_scope_path=home_path,
        )

    @classmethod
    async def authenticate(cls, *, email: str, password: str) -> AuthIdentity:
        perf_enabled = os.getenv("DCLM_AUTH_PERF", "0").strip().lower() in {"1", "true", "yes", "on"}
        started = perf_counter()
        client = get_api_client()
        phase_started = perf_counter()
        tokens = await client.login(email=email, password=password)
        token_exchange_ms = (perf_counter() - phase_started) * 1000
        access_token = str(tokens.get("access_token") or "")
        if not access_token:
            raise ValueError("The backend did not return an access token.")
        phase_started = perf_counter()
        user = await client.get_current_user(access_token)
        profile_load_ms = (perf_counter() - phase_started) * 1000
        if perf_enabled:
            logger.info(
                "auth_frontend_perf phases_ms=%s total_ms=%.1f",
                {"token_exchange": round(token_exchange_ms, 1), "profile_and_permissions": round(profile_load_ms, 1)},
                (perf_counter() - started) * 1000,
            )
        return cls._identity_from_payload(tokens=tokens, user=user)

    @classmethod
    async def refresh_identity(cls, request: Request) -> AuthIdentity | None:
        refresh_token = cls.get_refresh_token(request)
        if not refresh_token:
            return None
        client = get_api_client()
        try:
            tokens = await client.refresh(refresh_token)
        except BackendClientError:
            return None
        access_token = str(tokens.get("access_token") or "")
        if not access_token:
            return None
        try:
            user = await client.get_current_user(access_token)
        except BackendClientError:
            return None
        return cls._identity_from_payload(tokens=tokens, user=user)

    @classmethod
    async def persist_identity(cls, response: Response, identity: AuthIdentity) -> None:
        config = get_backend_config()
        cookie_args = {
            "httponly": True,
            "secure": config.auth_cookie_secure,
            "samesite": "lax",
            "max_age": config.session_max_age_seconds,
            "path": "/",
        }
        response.set_cookie(config.access_cookie_name, identity.access_token, **cookie_args)
        response.set_cookie(config.refresh_cookie_name, identity.refresh_token, **cookie_args)
        response.set_cookie(config.user_id_cookie_name, identity.user_id, **cookie_args)
        response.set_cookie(config.profile_cookie_name, identity.profile_key, **cookie_args)
        response.set_cookie(config.role_score_cookie_name, str(identity.role_score), **cookie_args)
        response.set_cookie(config.role_name_cookie_name, identity.role_name, **cookie_args)
        response.set_cookie(config.scope_cookie_name, identity.maximum_scope_path or identity.scope_path, **cookie_args)
        response.set_cookie(config.home_cookie_name, str(identity.user.get("path") or identity.home_path), **cookie_args)
        response.set_cookie("dclm_admin_location_id", str(identity.user.get("location_id") or ""), **cookie_args)
        response.set_cookie("dclm_admin_maximum_scope", identity.maximum_scope_path or identity.home_path, **cookie_args)
        response.set_cookie(config.display_name_cookie_name, identity.display_name, **cookie_args)
        response.set_cookie(config.email_cookie_name, identity.email, **cookie_args)
        response.set_cookie(
            "dclm_admin_permissions",
            json.dumps(sorted(identity.permissions), separators=(",", ":")),
            **cookie_args,
        )
        response.set_cookie(cls._refresh_cookie_name(), str(int(time())), **cookie_args)

    @classmethod
    async def clear_identity(cls, response: Response) -> None:
        config = get_backend_config()
        for cookie_name in [
            config.access_cookie_name,
            config.refresh_cookie_name,
            config.user_id_cookie_name,
            config.profile_cookie_name,
            config.role_score_cookie_name,
            config.role_name_cookie_name,
            config.scope_cookie_name,
            config.home_cookie_name,
            "dclm_admin_location_id",
            config.display_name_cookie_name,
            config.email_cookie_name,
            "dclm_admin_permissions",
            "dclm_admin_maximum_scope",
            cls._refresh_cookie_name(),
        ]:
            response.delete_cookie(cookie_name, path="/")

    @staticmethod
    def is_authenticated(request: Request) -> bool:
        config = get_backend_config()
        return bool(
            AuthService._cookie_value(request, config.access_cookie_name)
            and AuthService._cookie_value(request, config.profile_cookie_name)
        )

    @staticmethod
    def get_access_token(request: Request) -> str | None:
        return AuthService._cookie_value(request, get_backend_config().access_cookie_name)

    @staticmethod
    def get_refresh_token(request: Request) -> str | None:
        return AuthService._cookie_value(request, get_backend_config().refresh_cookie_name)

    @staticmethod
    def get_profile_key(request: Request, default: str | None = None) -> str | None:
        return AuthService._cookie_value(request, get_backend_config().profile_cookie_name, default)

    @classmethod
    def get_identity(cls, request: Request) -> AuthIdentity | None:
        config = get_backend_config()
        user_id = cls._cookie_value(request, config.user_id_cookie_name, "")
        access_token = cls.get_access_token(request)
        refresh_token = cls.get_refresh_token(request)
        profile_key = cls.get_profile_key(request)
        if not (user_id and access_token and refresh_token and profile_key):
            return None
        display_name = cls._cookie_value(request, config.display_name_cookie_name, "")
        email = cls._cookie_value(request, config.email_cookie_name, "")
        role_score = int(cls._cookie_value(request, config.role_score_cookie_name, "0") or 0)
        role_name = cls._cookie_value(request, config.role_name_cookie_name, "Worker") or "Worker"
        scope_path = cls._cookie_value(request, config.scope_cookie_name, "") or ""
        maximum_scope_path = cls._cookie_value(request, "dclm_admin_maximum_scope", "") or ""
        assigned_path = cls._cookie_value(request, config.home_cookie_name, "") or ""
        home_path = assigned_path
        if not maximum_scope_path and assigned_path:
            maximum_scope_path = create_admin_access_id(assigned_path, role_score or 2)
        try:
            permissions = json.loads(cls._cookie_value(request, "dclm_admin_permissions", "[]") or "[]")
            if not isinstance(permissions, list) or any(not isinstance(item, str) for item in permissions):
                permissions = []
        except (TypeError, ValueError):
            permissions = []
        location_id = cls._cookie_value(request, "dclm_admin_location_id", "") or ""
        user = {"name": display_name, "email": email, "path": assigned_path, "location_id": location_id, "permissions": permissions}
        return AuthIdentity(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            user=user,
            profile_key=profile_key,
            role_score=role_score,
            role_name=role_name,
            scope_path=scope_path,
            home_path=home_path,
            maximum_scope_path=maximum_scope_path,
        )

    @classmethod
    def should_refresh(cls, request: Request) -> bool:
        last_refresh_raw = cls._cookie_value(request, cls._refresh_cookie_name(), "0") or "0"
        try:
            last_refresh = int(last_refresh_raw)
        except ValueError:
            return True
        return (int(time()) - last_refresh) >= cls.REFRESH_WINDOW_SECONDS

    @staticmethod
    def sanitize_next_path(next_path: str | None) -> str | None:
        cleaned = (next_path or "").strip()
        if not cleaned or not cleaned.startswith("/") or cleaned.startswith("//"):
            return None
        return cleaned

    @classmethod
    def with_profile_query(cls, request: Request, path: str | None = None) -> str:
        target = cls.sanitize_next_path(path) or "/dashboard"
        profile_key = cls.get_profile_key(request)
        if not profile_key:
            return target
        parts = urlsplit(target)
        params = dict(parse_qsl(parts.query, keep_blank_values=True))
        params.setdefault("profile", profile_key)
        query = urlencode(params)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    @classmethod
    async def login_redirect_path(cls, request: Request) -> str:
        # Prefer the actual browser page URL for HTMX requests
        hx_current = request.headers.get("HX-Current-URL")
        if hx_current:
            parts = urlsplit(hx_current)
            current = parts.path
            if parts.query:
                current = f"{current}?{parts.query}"
        else:
            current = request.url.path
            if request.url.query:
                current = f"{current}?{request.url.query}"
        # Prevent redirect loops back to login or logout
        if not current or current.startswith("/login") or current.startswith("/logout"):
            current = "/dashboard"
        return f"/login?{urlencode({'next': current})}"

    @classmethod
    async def session_info(cls, request: Request) -> dict[str, Any]:
        identity = cls.get_identity(request)
        if identity is None:
            return {
                "authenticated": False,
                "profile_key": None,
                "role_score": None,
                "role_name": None,
                "scope_path": None,
                "display_name": None,
                "email": None,
            }
        payload = asdict(identity)
        payload.update(
            {
                "authenticated": True,
                "display_name": identity.display_name,
                "email": identity.email,
            }
        )
        return payload

    @classmethod
    def session_snapshot(cls, request: Request) -> dict[str, Any]:
        identity = cls.get_identity(request)
        if identity is None:
            return {
                "authenticated": False,
                "profile_key": None,
                "role_score": None,
                "role_name": None,
                "scope_path": None,
                "display_name": None,
                "email": None,
            }
        payload = asdict(identity)
        payload.update(
            {
                "authenticated": True,
                "display_name": identity.display_name,
                "email": identity.email,
            }
        )
        return payload


__all__ = ["AuthIdentity", "AuthService", "BackendClientError"]
