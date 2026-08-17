from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from .contracts import CORE_ADMIN_FAMILIES, SHARED_PLATFORM_FAMILIES, route_family_count


@dataclass(frozen=True)
class BackendConfig:
    mode: str
    base_url: str
    api_prefix: str
    timeout_seconds: float
    verify_ssl: bool
    session_secret: str
    session_cookie_name: str
    session_max_age_seconds: int
    auth_cookie_secure: bool
    access_cookie_name: str
    refresh_cookie_name: str
    profile_cookie_name: str
    role_score_cookie_name: str
    role_name_cookie_name: str
    scope_cookie_name: str
    home_cookie_name: str
    display_name_cookie_name: str
    email_cookie_name: str
    user_id_cookie_name: str

    @property
    def enabled(self) -> bool:
        return self.mode == "backend"

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")

    @property
    def api_base_url(self) -> str:
        return f"{self.normalized_base_url}{self.api_prefix}"


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@lru_cache(maxsize=1)
def get_backend_config() -> BackendConfig:
    return BackendConfig(
        mode=os.getenv("DCLM_ADMIN_DATA_MODE", "backend").strip().lower() or "backend",
        base_url=os.getenv("DCLM_ADMIN_BACKEND_URL", "http://127.0.0.1:8010").strip() or "http://127.0.0.1:8010",
        api_prefix=os.getenv("DCLM_ADMIN_API_PREFIX", "/api/v1").strip() or "/api/v1",
        timeout_seconds=float(os.getenv("DCLM_ADMIN_BACKEND_TIMEOUT", "12")),
        verify_ssl=_read_bool("DCLM_ADMIN_BACKEND_VERIFY_SSL", True),
        session_secret=os.getenv("DCLM_ADMIN_SESSION_SECRET", "dclm-admin-dev-session-secret").strip()
        or "dclm-admin-dev-session-secret",
        session_cookie_name=os.getenv("DCLM_ADMIN_SESSION_COOKIE", "dclm_admin_session").strip() or "dclm_admin_session",
        session_max_age_seconds=int(os.getenv("DCLM_ADMIN_SESSION_MAX_AGE", "28800")),
        auth_cookie_secure=_read_bool("DCLM_ADMIN_COOKIE_SECURE", False),
        access_cookie_name=os.getenv("DCLM_ADMIN_ACCESS_COOKIE", "dclm_admin_access").strip() or "dclm_admin_access",
        refresh_cookie_name=os.getenv("DCLM_ADMIN_REFRESH_COOKIE", "dclm_admin_refresh").strip() or "dclm_admin_refresh",
        profile_cookie_name=os.getenv("DCLM_ADMIN_PROFILE_COOKIE", "dclm_admin_profile").strip() or "dclm_admin_profile",
        role_score_cookie_name=os.getenv("DCLM_ADMIN_ROLE_SCORE_COOKIE", "dclm_admin_role_score").strip() or "dclm_admin_role_score",
        role_name_cookie_name=os.getenv("DCLM_ADMIN_ROLE_NAME_COOKIE", "dclm_admin_role_name").strip() or "dclm_admin_role_name",
        scope_cookie_name=os.getenv("DCLM_ADMIN_SCOPE_COOKIE", "dclm_admin_scope").strip() or "dclm_admin_scope",
        home_cookie_name=os.getenv("DCLM_ADMIN_HOME_COOKIE", "dclm_admin_home").strip() or "dclm_admin_home",
        display_name_cookie_name=os.getenv("DCLM_ADMIN_DISPLAY_COOKIE", "dclm_admin_display").strip() or "dclm_admin_display",
        email_cookie_name=os.getenv("DCLM_ADMIN_EMAIL_COOKIE", "dclm_admin_email").strip() or "dclm_admin_email",
        user_id_cookie_name=os.getenv("DCLM_ADMIN_USER_ID_COOKIE", "dclm_admin_user_id").strip() or "dclm_admin_user_id",
    )


def get_backend_status() -> dict[str, object]:
    config = get_backend_config()
    return {
        "mode": config.mode,
        "enabled": config.enabled,
        "base_url": config.normalized_base_url,
        "api_base_url": config.api_base_url,
        "session_cookie_name": config.session_cookie_name,
        "session_max_age_seconds": config.session_max_age_seconds,
        "access_cookie_name": config.access_cookie_name,
        "refresh_cookie_name": config.refresh_cookie_name,
        "core_admin_family_count": len(CORE_ADMIN_FAMILIES),
        "shared_platform_family_count": len(SHARED_PLATFORM_FAMILIES),
        "total_family_count": route_family_count(),
        "next_target": "enable backend mode and bootstrap starter data" if not config.enabled else "run live admin with seeded hierarchy and real pastor accounts",
    }
