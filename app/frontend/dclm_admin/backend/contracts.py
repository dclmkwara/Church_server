from __future__ import annotations

BACKEND_ROUTE_FAMILIES: dict[str, dict[str, object]] = {
    "auth": {
        "base_path": "/auth",
        "products": ("admin",),
        "high_value": True,
        "notes": "Login, refresh, and current-user bootstrap for every protected client.",
    },
    "users": {
        "base_path": "/users",
        "products": ("admin",),
        "high_value": True,
        "notes": "App users, role assignment, approvals, deactivation, and search.",
    },
    "workers": {
        "base_path": "/workers",
        "products": ("admin", "public"),
        "high_value": True,
        "notes": "Worker directory, registration review, search, approval, and lifecycle updates.",
    },
    "approvals": {
        "base_path": "/approvals",
        "products": ("admin",),
        "high_value": True,
        "notes": "Transfer, status change, and escalating removal workflows.",
    },
    "hierarchy": {
        "base_path": "",
        "products": ("admin", "public"),
        "high_value": True,
        "notes": "Nation, state, region, group, location, fellowship CRUD plus tree/search.",
    },
    "location_profiles": {
        "base_path": "/locations",
        "products": ("admin", "public"),
        "high_value": False,
        "notes": "Location profile metadata used by admin and public-facing church details.",
    },
    "programs": {
        "base_path": "/programs",
        "products": ("admin", "public"),
        "high_value": True,
        "notes": "Program domains, types, and event schedule data.",
    },
    "counts": {
        "base_path": "/counts",
        "products": ("admin", "utility"),
        "high_value": True,
        "notes": "Counts CRUD, aggregates, and special-program support.",
    },
    "offerings": {
        "base_path": "/offerings",
        "products": ("admin", "utility"),
        "high_value": True,
        "notes": "Offerings CRUD and finance inspection flows.",
    },
    "tithes": {
        "base_path": "/tithes",
        "products": ("admin", "utility"),
        "high_value": False,
        "notes": "Tithes remain separate in the backend even though the admin UI unifies finance.",
    },
    "records": {
        "base_path": "/records",
        "products": ("admin", "utility"),
        "high_value": True,
        "notes": "Shared records base used by newcomers, converts, and member-related follow-up.",
    },
    "newcomers": {
        "base_path": "/newcomers",
        "products": ("admin", "utility"),
        "high_value": True,
        "notes": "Newcomer-specific record flows.",
    },
    "converts": {
        "base_path": "/converts",
        "products": ("admin", "utility"),
        "high_value": False,
        "notes": "Convert-specific follow-up flows.",
    },
    "church_members": {
        "base_path": "/members",
        "products": ("admin",),
        "high_value": True,
        "notes": "Church member registry separate from workers.",
    },
    "attendance": {
        "base_path": "/attendance",
        "products": ("admin", "utility"),
        "high_value": True,
        "notes": "Worker attendance, absence notices, and history.",
    },
    "fellowship": {
        "base_path": "/fellowships",
        "products": ("admin", "utility"),
        "high_value": True,
        "notes": "Fellowship members, attendance, offerings, testimonies, and prayer requests.",
    },
    "announcements": {
        "base_path": "/announcements",
        "products": ("admin", "public"),
        "high_value": True,
        "notes": "Announcement publishing lifecycle.",
    },
    "information": {
        "base_path": "/information",
        "products": ("admin", "public"),
        "high_value": False,
        "notes": "Weekly information entries managed alongside announcements in the frontend.",
    },
    "media": {
        "base_path": "/media",
        "products": ("admin", "public"),
        "high_value": True,
        "notes": "Gallery and media-item management for public and admin use.",
    },
    "reports": {
        "base_path": "/reports",
        "products": ("admin",),
        "high_value": True,
        "notes": "Summary, financial, attendance, timeseries, breakdown, anomalies, growth, and export.",
    },
    "statistics": {
        "base_path": "/statistics",
        "products": ("admin",),
        "high_value": False,
        "notes": "Additional analytic endpoints separate from report pages.",
    },
    "notifications": {
        "base_path": "/notifications",
        "products": ("admin", "utility"),
        "high_value": False,
        "notes": "Polling endpoint for new data; thinner than the current frontend notification center.",
    },
    "app_versions": {
        "base_path": "/app-versions",
        "products": ("admin", "public", "utility"),
        "high_value": True,
        "notes": "Release records used by admin governance and mobile/public download discovery.",
    },
    "system": {
        "base_path": "/system",
        "products": ("admin",),
        "high_value": False,
        "notes": "Audit logs, metrics, metadata, and restricted seed actions.",
    },
    "rbac": {
        "base_path": "/rbac",
        "products": ("admin",),
        "high_value": False,
        "notes": "Roles, permissions, role scores, and governance configuration.",
    },
    "public": {
        "base_path": "/public",
        "products": ("public", "utility"),
        "high_value": True,
        "notes": "Events, locations, public forms, galleries, announcements, and app-version discovery.",
    },
    "sync": {
        "base_path": "/sync",
        "products": ("utility", "admin"),
        "high_value": True,
        "notes": "Offline batch sync, incremental changes, conflicts, and conflict resolution.",
    },
    "recovery": {
        "base_path": "/recovery",
        "products": ("admin", "utility"),
        "high_value": False,
        "notes": "Password reset and recovery-question flows.",
    },
    "websocket": {
        "base_path": "/ws",
        "products": ("admin", "utility"),
        "high_value": False,
        "notes": "Realtime notification channel.",
    },
}

CORE_ADMIN_FAMILIES = tuple(
    key
    for key, meta in BACKEND_ROUTE_FAMILIES.items()
    if "admin" in meta["products"] and meta["high_value"]
)

SHARED_PLATFORM_FAMILIES = tuple(
    key
    for key, meta in BACKEND_ROUTE_FAMILIES.items()
    if "public" in meta["products"] or "utility" in meta["products"]
)


def route_family_count(*, product: str | None = None) -> int:
    if product is None:
        return len(BACKEND_ROUTE_FAMILIES)
    return sum(1 for meta in BACKEND_ROUTE_FAMILIES.values() if product in meta["products"])
