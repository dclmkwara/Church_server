from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, RedirectResponse, Response

from fasthtml.common import FastHTML
from faststrap import add_bootstrap, add_pwa, mount_assets

from .async_render import install_async_render_resolution
from .backend import close_async_http_client
from .backend.config import get_backend_config
from .communication import AuthService
from .routes.auth import register_auth_routes
from .routes.communication import register_communication_routes
from .routes.church_data import register_church_data_routes
from .routes.dashboard import register_dashboard_routes
from .routes.fellowship import register_fellowship_routes
from .routes.inbox import register_inbox_routes
from .routes.organization import register_organization_routes
from .routes.people import register_people_routes
from .routes.placeholders import register_placeholder_routes
from .routes.programs import register_program_routes
from .routes.reports import register_report_routes
from .routes.system import register_system_routes
from .routes.workflows import register_workflow_routes
from .theme import DCLM_THEME, setup_theme_defaults


install_async_render_resolution()

app = FastHTML()
add_bootstrap(app, theme=DCLM_THEME, mode="light", include_favicon=True, favicon_url="/favicon.png")
setup_theme_defaults()
mount_assets(app, str(Path(__file__).resolve().parent / "assets"), url_path="/assets")

add_pwa(
    app,
    name="DCLM Church Management System",
    short_name="DCLM Admin",
    description="Deeper Life Bible Church Multi-Tier Management & Administrative System",
    theme_color="#0F2D5E",
    background_color="#0F2D5E",
    icon_path="/assets/img/dclm-logo.png",
    icon_192="/assets/icon-192.png",
    icon_512="/assets/icon-512.png",
    start_url="/dashboard",
    display="standalone",
    service_worker=True,
    offline_page=True,
)


class BackendAuthMiddleware(BaseHTTPMiddleware):
    EXEMPT_PREFIXES = ("/assets", "/favicon", "/_starlette")
    EXEMPT_PATHS = {
        "/health",
        "/login",
        "/logout",
        "/sw.js",
        "/offline",
        "/manifest.json",
        "/favicon.ico",
        "/favicon.png",
        "/apple-touch-icon.png",
        "/theme/toggle",
    }
    PROTECTED_PREFIXES = (

        "/dashboard",
        "/inbox",
        "/people",
        "/church-data",
        "/workflows",
        "/fellowship",
        "/organization",
        "/communication",
        "/reports",
        "/system",
        "/partials",
    )

    # Throttle token refresh checks: once per session every 5 minutes max.
    _VALIDATE_INTERVAL = 300  # seconds
    _VALIDATE_COOKIE = "_dclm_lv"  # last_validated timestamp

    async def dispatch(self, request: Request, call_next):
        config = get_backend_config()
        path = request.url.path
        # Fast-exit for static assets before any cookie parsing
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return await call_next(request)
        if not config.enabled:
            return await call_next(request)
        if path in self.EXEMPT_PATHS:
            return await call_next(request)
        if not any(path == prefix or path.startswith(f"{prefix}/") for prefix in self.PROTECTED_PREFIXES):
            return await call_next(request)
        if not AuthService.is_authenticated(request):
            # HTMX partials must not receive a full redirect — return 401 + HX-Redirect
            if request.headers.get("HX-Request"):
                login_path = await AuthService.login_redirect_path(request)
                return Response(status_code=401, headers={"HX-Redirect": login_path})
            return RedirectResponse(await AuthService.login_redirect_path(request), status_code=303)

        refreshed_identity = None
        if request.method == "GET":
            # Only call validate_and_refresh() if the per-session throttle has expired.
            import time
            last_validated = request.cookies.get(self._VALIDATE_COOKIE)
            throttle_expired = (
                last_validated is None
                or (time.time() - float(last_validated)) > self._VALIDATE_INTERVAL
            )
            if throttle_expired and AuthService.should_refresh(request):
                refreshed_identity = await AuthService.refresh_identity(request)

        if request.method == "GET" and "profile" not in request.query_params:
            profile_key = AuthService.get_profile_key(request)
            if profile_key:
                params = dict(request.query_params)
                params["profile"] = profile_key
                query = urlencode(params)
                response = RedirectResponse(f"{path}?{query}", status_code=303)
                if refreshed_identity is not None:
                    await AuthService.persist_identity(response, refreshed_identity)
                return response
        response = await call_next(request)
        if refreshed_identity is not None:
            await AuthService.persist_identity(response, refreshed_identity)
            import time
            response.set_cookie(self._VALIDATE_COOKIE, str(time.time()), max_age=self._VALIDATE_INTERVAL, httponly=True, samesite="lax")
        elif request.cookies.get(self._VALIDATE_COOKIE) is None:
            import time
            response.set_cookie(self._VALIDATE_COOKIE, str(time.time()), max_age=self._VALIDATE_INTERVAL, httponly=True, samesite="lax")
        return response


app.add_middleware(BackendAuthMiddleware)


@app.get("/")
async def root(request: Request):
    config = get_backend_config()
    if config.enabled:
        if AuthService.is_authenticated(request):
            return RedirectResponse(url=AuthService.with_profile_query(request, "/dashboard"))
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/dashboard")


@app.get("/health")
def health():
    return {"status": "ok", "service": "dclm-admin-frontend"}


@app.post("/theme/toggle")
def toggle_theme(request: Request):
    current = request.cookies.get("theme", "light")
    new_theme = "dark" if current == "light" else "light"
    resp = Response(status_code=200)
    resp.set_cookie("theme", new_theme, max_age=31536000, samesite="lax")
    return resp


@app.get("/favicon.ico")
def favicon_ico():
    return FileResponse(Path(__file__).resolve().parent / "assets" / "favicon.ico")


@app.get("/favicon.png")
def favicon_png():
    return FileResponse(Path(__file__).resolve().parent / "assets" / "favicon.png")


@app.get("/apple-touch-icon.png")
def apple_touch_icon():
    return FileResponse(Path(__file__).resolve().parent / "assets" / "apple-touch-icon.png")


async def shutdown_http_client():
    await close_async_http_client()


app.router.on_shutdown.append(shutdown_http_client)



@app.get("/sw.js")
def service_worker():
    script = """
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', () => {});
""".strip()
    return Response(content=script, media_type="application/javascript")


@app.get("/partials/notifications")
async def notifications(request: Request):
    from fasthtml.common import Div, H3, P

    from .auth_context import build_context
    from .backend.config import get_backend_config
    from .communication.system_service import SystemService
    from .mock_data import NOTIFICATIONS

    config = get_backend_config()
    if config.enabled:
        ctx = build_context(request)
        items = (await SystemService.list_notifications(request, ctx, status="all", kind="all"))[:8]
        if not items:
            return Div(P("No recent notifications.", cls="text-muted mb-0"))
        return Div(
            *[
                Div(
                    H3(item["title"], cls="h6 fw-semibold mb-1"),
                    P(item["body"], cls="text-muted mb-1"),
                    P(item["time"], cls="small text-muted mb-0"),
                    cls="drawer-note-box mb-3",
                )
                for item in items
            ]
        )

    return Div(
        *[
            Div(
                H3(item["title"], cls="h6 fw-semibold mb-1"),
                P(item["body"], cls="text-muted mb-1"),
                P(item["time"], cls="small text-muted mb-0"),
                cls="drawer-note-box mb-3",
            )
            for item in NOTIFICATIONS
        ]
    )


register_dashboard_routes(app)
register_auth_routes(app)
register_inbox_routes(app)
register_people_routes(app)
register_fellowship_routes(app)
register_organization_routes(app)
register_program_routes(app)
register_church_data_routes(app)
register_workflow_routes(app)
register_communication_routes(app)
register_report_routes(app)
register_system_routes(app)
register_placeholder_routes(app)
