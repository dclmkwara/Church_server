from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlencode

from starlette.requests import Request

from .backend import format_scope_display_id, profile_key_for_score, split_scope_path
from .backend.config import get_backend_config
from .communication.auth_service import AuthService


class _AuthRedirectRequired(Exception):
    """Raised by build_context() when a corrupted session must be cleared.

    Route handlers and middleware should catch this and return a RedirectResponse.
    """
    def __init__(self, location: str = "/logout") -> None:
        self.location = location
        super().__init__(f"Auth redirect required: {location}")


SEGMENT_ORDER = ["continent", "nation", "state", "region", "group", "location", "fellowship"]


DEMO_SCOPE_ROWS = [
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Kwara State",
        "region": "Ilorin North Region",
        "group": "Ilorin East Group",
        "location": "GRA DLBC",
        "path": "global.west_africa.nigeria.kwara_state.ilorin_north_region.ilorin_east_group.gra_dlbc",
    },
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Kwara State",
        "region": "Ilorin North Region",
        "group": "Ilorin East Group",
        "location": "University DLBC",
        "path": "global.west_africa.nigeria.kwara_state.ilorin_north_region.ilorin_east_group.university_dlbc",
    },
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Kwara State",
        "region": "Ilorin North Region",
        "group": "Ilorin East Group",
        "location": "Tanke DLBC",
        "path": "global.west_africa.nigeria.kwara_state.ilorin_north_region.ilorin_east_group.tanke_dlbc",
    },
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Kwara State",
        "region": "Offa Region",
        "group": "Offa Central Group",
        "location": "Offa Township DLBC",
        "path": "global.west_africa.nigeria.kwara_state.offa_region.offa_central_group.offa_township_dlbc",
    },
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Lagos State",
        "region": "Ikeja Region",
        "group": "Surulere Group",
        "location": "Surulere DLBC",
        "path": "global.west_africa.nigeria.lagos_state.ikeja_region.surulere_group.surulere_dlbc",
    },
]


DEMO_SCOPE_PATHS = {
    "global": {"Global": "global"},
    "continent": {"West Africa Division": "global.west_africa"},
    "nation": {"Nigeria": "global.west_africa.nigeria"},
    "state": {
        "Kwara State": "global.west_africa.nigeria.kwara_state",
        "Lagos State": "global.west_africa.nigeria.lagos_state",
    },
    "region": {
        "Ilorin North Region": "global.west_africa.nigeria.kwara_state.ilorin_north_region",
        "Offa Region": "global.west_africa.nigeria.kwara_state.offa_region",
        "Ikeja Region": "global.west_africa.nigeria.lagos_state.ikeja_region",
    },
    "group": {
        "Ilorin East Group": "global.west_africa.nigeria.kwara_state.ilorin_north_region.ilorin_east_group",
        "Offa Central Group": "global.west_africa.nigeria.kwara_state.offa_region.offa_central_group",
        "Surulere Group": "global.west_africa.nigeria.lagos_state.ikeja_region.surulere_group",
    },
    "location": {row["location"]: row["path"] for row in DEMO_SCOPE_ROWS},
}


def _demo_in_scope(path: str, root_path: str) -> bool:
    return path == root_path or path.startswith(f"{root_path}.")


@dataclass(frozen=True)
class ProfileConfig:
    key: str
    level: int
    user_name: str
    role_label: str
    mode_label: str
    root_kind: str
    root_label: str
    root_path: str
    selector_fields: tuple[str, ...]


PROFILE_CONFIGS = {
    "location_pastor": ProfileConfig(
        key="location_pastor",
        level=3,
        user_name="Pastor Samuel Adebayo",
        role_label="Location Pastor",
        mode_label="Action Mode",
        root_kind="location",
        root_label="GRA DLBC",
        root_path=DEMO_SCOPE_PATHS["location"]["GRA DLBC"],
        selector_fields=(),
    ),
    "group_pastor": ProfileConfig(
        key="group_pastor",
        level=4,
        user_name="Pastor Deborah Yusuf",
        role_label="Group Pastor",
        mode_label="Oversight Mode",
        root_kind="group",
        root_label="Ilorin East Group",
        root_path=DEMO_SCOPE_PATHS["group"]["Ilorin East Group"],
        selector_fields=("group", "location"),
    ),
    "region_pastor": ProfileConfig(
        key="region_pastor",
        level=5,
        user_name="Pastor David Akinwale",
        role_label="Region Pastor",
        mode_label="Oversight Mode",
        root_kind="region",
        root_label="Ilorin North Region",
        root_path=DEMO_SCOPE_PATHS["region"]["Ilorin North Region"],
        selector_fields=("region", "group", "location"),
    ),
    "state_overseer": ProfileConfig(
        key="state_overseer",
        level=6,
        user_name="Pastor Grace Omoniyi",
        role_label="State Overseer",
        mode_label="Oversight Mode",
        root_kind="state",
        root_label="Kwara State",
        root_path=DEMO_SCOPE_PATHS["state"]["Kwara State"],
        selector_fields=("state", "region", "group", "location"),
    ),
    "national_admin": ProfileConfig(
        key="national_admin",
        level=7,
        user_name="Pastor John Fasanmi",
        role_label="National Admin",
        mode_label="Admin Mode",
        root_kind="nation",
        root_label="Nigeria",
        root_path=DEMO_SCOPE_PATHS["nation"]["Nigeria"],
        selector_fields=("nation", "state", "region", "group", "location"),
    ),
    "continental_admin": ProfileConfig(
        key="continental_admin",
        level=8,
        user_name="Pastor Ruth Balogun",
        role_label="Continental Admin",
        mode_label="Admin Mode",
        root_kind="continent",
        root_label="West Africa Division",
        root_path=DEMO_SCOPE_PATHS["continent"]["West Africa Division"],
        selector_fields=("continent", "nation", "state", "region", "group", "location"),
    ),
    "global_admin": ProfileConfig(
        key="global_admin",
        level=9,
        user_name="Pastor Michael Ojo",
        role_label="Global Admin",
        mode_label="Admin Mode",
        root_kind="global",
        root_label="Global",
        root_path=DEMO_SCOPE_PATHS["global"]["Global"],
        selector_fields=("continent", "nation", "state", "region", "group", "location"),
    ),
}


VISIBLE_MODULES = {
    3: ["dashboard", "inbox", "people", "workflows", "church-data", "fellowship", "organization"],
    4: ["dashboard", "inbox", "people", "workflows", "church-data", "fellowship", "organization"],
    5: ["dashboard", "inbox", "people", "workflows", "church-data", "fellowship", "organization", "communication"],
    6: [
        "dashboard",
        "inbox",
        "people",
        "workflows",
        "church-data",
        "fellowship",
        "organization",
        "communication",
        "reports",
    ],
    7: [
        "dashboard",
        "inbox",
        "people",
        "workflows",
        "church-data",
        "fellowship",
        "organization",
        "communication",
        "reports",
        "system",
    ],
    8: [
        "dashboard",
        "inbox",
        "people",
        "workflows",
        "church-data",
        "fellowship",
        "organization",
        "communication",
        "reports",
        "system",
    ],
    9: [
        "dashboard",
        "inbox",
        "people",
        "workflows",
        "church-data",
        "fellowship",
        "organization",
        "communication",
        "reports",
        "system",
    ],
}


def _mode_label_for_level(level: int) -> str:
    if level <= 3:
        return "Action Mode"
    if level <= 6:
        return "Oversight Mode"
    return "Admin Mode"


def _scope_kind_from_backend_path(path: str, level: int) -> str:
    parts = [segment for segment in str(path or "").split(".") if segment]
    depth = len(parts)
    if depth <= 1:
        return "global" if level >= 9 else "continent"
    if depth == 2:
        return "nation"
    if depth == 3:
        return "state"
    if depth == 4:
        return "region"
    if depth == 5:
        return "group"
    if depth == 6:
        return "location"
    return "fellowship"


@dataclass(frozen=True)
class AdminContext:
    profile: ProfileConfig
    selected: dict[str, str]
    options: dict[str, list[str]]
    current_scope_kind: str
    current_scope_label: str
    current_scope_path: str
    query_extras: dict[str, str] = field(default_factory=dict)

    @property
    def level(self) -> int:
        return self.profile.level

    @property
    def visible_modules(self) -> list[str]:
        return VISIBLE_MODULES[self.level]

    @property
    def page_scope_title(self) -> str:
        if self.level == 9 and self.current_scope_kind == "global":
            return "System Administration Dashboard"
        if self.current_scope_kind == "nation":
            return f"{self.current_scope_label} National Dashboard"
        if self.current_scope_kind == "continent":
            return f"{self.current_scope_label} Continental Dashboard"
        return f"{self.current_scope_label} Dashboard"

    def query_dict(self) -> dict[str, str]:
        data = {"profile": self.profile.key}
        data.update(self.query_extras)
        for field in self.profile.selector_fields:
            value = self.selected.get(field)
            if value:
                data[field] = value
        return data

    def url_for(self, path: str, **overrides: str | None) -> str:
        params = {k: v for k, v in self.query_dict().items() if v is not None}
        for key, value in overrides.items():
            if value:
                params[key] = value
            else:
                params.pop(key, None)
        query = urlencode(params)
        return f"{path}?{query}" if query else path


def _visible_rows(root_path: str, current: dict[str, str]) -> list[dict[str, str]]:
    rows = [row for row in DEMO_SCOPE_ROWS if _demo_in_scope(row["path"], root_path)]
    for key, value in current.items():
        rows = [row for row in rows if row.get(key) == value]
    return rows


def _mapping_from_source(source: Request | Mapping[str, Any]) -> Mapping[str, Any]:
    return source.query_params if isinstance(source, Request) else source


def _backend_context(source: Request | Mapping[str, Any]) -> AdminContext | None:
    if not get_backend_config().enabled:
        return None
    mapping = _mapping_from_source(source)
    identity = AuthService.get_identity(source) if isinstance(source, Request) else None
    scope_path = str(
        (identity.scope_path if identity else "") or mapping.get("scope_path") or mapping.get("home_path") or ""
    ).strip()
    if not scope_path:
        return None
    profile_key = str((identity.profile_key if identity else "") or mapping.get("profile") or "").strip()
    role_score = int((identity.role_score if identity else 0) or mapping.get("role_score") or 3)
    if not profile_key:
        profile_key = profile_key_for_score(role_score)
    role_label = str((identity.role_name if identity else "") or mapping.get("role_label") or "Worker")
    user_name = str((identity.display_name if identity else "") or mapping.get("user_name") or "Authenticated User")
    current_scope_kind = str(mapping.get("scope_kind") or _scope_kind_from_backend_path(scope_path, role_score)).strip()
    current_scope_label = str(mapping.get("scope_label") or format_scope_display_id(scope_path) or role_label).strip()
    profile = ProfileConfig(
        key=profile_key,
        level=max(3, min(role_score or 3, 9)),
        user_name=user_name,
        role_label=role_label,
        mode_label=_mode_label_for_level(max(3, min(role_score or 3, 9))),
        root_kind=current_scope_kind,
        root_label=current_scope_label,
        root_path=scope_path,
        selector_fields=(),
    )
    return AdminContext(
        profile=profile,
        selected={},
        options={},
        current_scope_kind=current_scope_kind,
        current_scope_label=current_scope_label,
        current_scope_path=scope_path,
        query_extras={
            "scope_path": scope_path,
            "scope_kind": current_scope_kind,
            "scope_label": current_scope_label,
            "user_name": user_name,
            "role_label": role_label,
            "role_score": str(profile.level),
            "home_path": str((identity.home_path if identity else "") or mapping.get("home_path") or scope_path),
        },
    )


def _demo_context(source: Request | Mapping[str, Any]) -> AdminContext:
    mapping = _mapping_from_source(source)
    requested_profile = str(mapping.get("profile", "location_pastor"))
    profile = PROFILE_CONFIGS.get(requested_profile, PROFILE_CONFIGS["location_pastor"])
    selected: dict[str, str] = {}
    options: dict[str, list[str]] = {}

    if profile.root_kind != "global":
        selected[profile.root_kind] = profile.root_label

    for field in profile.selector_fields:
        if field == profile.root_kind:
            options[field] = [profile.root_label]
            selected[field] = profile.root_label
            continue

        rows = _visible_rows(profile.root_path, selected)
        field_options = sorted({str(row[field]) for row in rows})
        options[field] = field_options
        requested = str(mapping.get(field, "")).strip()
        if requested and requested in field_options:
            selected[field] = requested

    current_scope_kind = profile.root_kind
    current_scope_label = profile.root_label
    for field in SEGMENT_ORDER:
        value = selected.get(field)
        if value:
            current_scope_kind = field
            current_scope_label = value

    current_scope_path = DEMO_SCOPE_PATHS[current_scope_kind][current_scope_label]
    return AdminContext(
        profile=profile,
        selected=selected,
        options=options,
        current_scope_kind=current_scope_kind,
        current_scope_label=current_scope_label,
        current_scope_path=current_scope_path,
    )


def build_context(source: Request | Mapping[str, Any]) -> AdminContext:
    """Build (or return cached) AdminContext for this request.

    Results are cached on ``request.state._admin_ctx`` so repeated calls within
    the same request lifecycle are free (no repeated cookie parsing/scope compute).
    """
    # Cache on request.state to avoid re-computing per call within one request
    if isinstance(source, Request):
        cached = getattr(source.state, "_admin_ctx", None)
        if cached is not None:
            return cached

    backend_ctx = _backend_context(source)
    if get_backend_config().enabled:
        if backend_ctx is not None:
            if isinstance(source, Request):
                source.state._admin_ctx = backend_ctx
            return backend_ctx
        if backend_ctx is None:
            # In backend mode, a missing or corrupted identity cookie must not
            # silently grant demo-scope access. Force re-authentication.
            if isinstance(source, Request):
                raise _AuthRedirectRequired("/logout")
            # Non-request sources (e.g. test mappings) fall through to demo profile.

        mapping = _mapping_from_source(source)
        requested_profile = str(mapping.get("profile", "location_pastor"))
        fallback_profile = PROFILE_CONFIGS.get(requested_profile, PROFILE_CONFIGS["location_pastor"])
        ctx = AdminContext(
            profile=ProfileConfig(
                key=fallback_profile.key,
                level=fallback_profile.level,
                user_name=str(mapping.get("user_name") or "Authenticated User"),
                role_label=str(mapping.get("role_label") or fallback_profile.role_label),
                mode_label=_mode_label_for_level(fallback_profile.level),
                root_kind=str(mapping.get("scope_kind") or fallback_profile.root_kind),
                root_label=str(mapping.get("scope_label") or "Current scope"),
                root_path=str(mapping.get("scope_path") or mapping.get("home_path") or ""),
                selector_fields=(),
            ),
            selected={},
            options={},
            current_scope_kind=str(mapping.get("scope_kind") or fallback_profile.root_kind),
            current_scope_label=str(mapping.get("scope_label") or "Current scope"),
            current_scope_path=str(mapping.get("scope_path") or mapping.get("home_path") or ""),
            query_extras={
                "scope_path": str(mapping.get("scope_path") or mapping.get("home_path") or ""),
                "scope_kind": str(mapping.get("scope_kind") or fallback_profile.root_kind),
                "scope_label": str(mapping.get("scope_label") or "Current scope"),
                "user_name": str(mapping.get("user_name") or "Authenticated User"),
                "role_label": str(mapping.get("role_label") or fallback_profile.role_label),
                "role_score": str(mapping.get("role_score") or fallback_profile.level),
                "home_path": str(mapping.get("home_path") or mapping.get("scope_path") or ""),
            },
        )
        if isinstance(source, Request):
            source.state._admin_ctx = ctx
        return ctx
    ctx = _demo_context(source)
    if isinstance(source, Request):
        source.state._admin_ctx = ctx
    return ctx
