from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fasthtml.common import A, Div, Footer, Form, H1, Img, Input, Link, P, Script, Title
from starlette.requests import Request
from starlette.responses import RedirectResponse

from faststrap import Alert, Badge, Button, Card, Icon

from ..backend import BackendClientError, get_backend_config
from ..communication import AuthService
from ..components.feedback import toast_stack


def _auth_layout(
    *,
    content,
    accent: str = "Secure admin access",
    toast_message: str | None = None,
    toast_variant: str = "info",
    toast_title: str | None = None,
):
    header = Div(
        Img(
            src="/assets/img/dclm-logo.png",
            alt="Deeper Life Bible Church",
            width="72",
            height="72",
            cls="mb-3 mx-auto d-block shadow-sm rounded-circle p-1 bg-body",
        ),
        Div(
            Badge("DCLM Operations", variant="primary", cls="border-0 px-3 py-1 fw-semibold"),
            P(accent, cls="small text-secondary fw-semibold mb-0"),
            cls="d-flex flex-wrap align-items-center justify-content-center gap-2 mb-3",
        ),
        cls="text-center w-100",
    )
    return (
        Title("DCLM Admin | Sign In"),
        Link(rel="icon", type="image/png", href="/assets/favicon.png"),
        Link(rel="apple-touch-icon", href="/assets/apple-touch-icon.png"),
        Link(rel="manifest", href="/manifest.json"),
        Link(rel="stylesheet", href="/assets/css/admin.css"),
        Script(src="/assets/js/admin-interactions.js", defer=True),
        Div(
            Div(
                Div(header, content, cls="admin-auth-panel mx-auto"),
                Footer(P("Powered by: Kwara State ICT Unit", cls="small text-secondary text-center mb-0 mt-4"), role="contentinfo"),
                cls="w-100",
            ),
            toast_stack(toast_message, variant=toast_variant, title=toast_title),
            cls="admin-auth-shell",
        ),
    )




def _append_profile(path: str, profile_key: str) -> str:
    parts = urlsplit(path)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params["profile"] = profile_key
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def _login_form(*, next_path: str, error: str | None = None):
    return Card(
        Div(
            P(error, cls="small text-danger fw-semibold mb-3") if error else "",
            Form(
                Input(type="hidden", name="next", value=next_path),
                Div(
                    P("Email address", cls="small text-muted mb-1"),
                    Input(type="email", name="email", placeholder="name@example.com", required=True, cls="form-control form-control-lg"),
                    cls="mb-3",
                ),
                Div(
                    P("Password", cls="small text-muted mb-1"),
                    Input(type="password", name="password", placeholder="Enter your password", required=True, cls="form-control form-control-lg"),
                    cls="mb-3",
                ),
                Button(
                    "Sign in",
                    Icon("box-arrow-in-right", cls="ms-2"),
                    type="submit",
                    variant="primary",
                    size="md",
                    cls="w-100",
                    data_loading_text="Signing in",
                ),
                action="/login",
                method="post",
            ),
            Div(
                Div(
                    Icon("shield-lock", cls="text-primary"),
                    P("Your session follows your assigned role and church level.", cls="small text-muted mb-0"),
                    cls="d-flex align-items-start gap-2",
                ),
                cls="admin-auth-note mt-3",
            ),
        ),
        cls="admin-auth-card border-0 shadow-lg p-2 p-sm-3",
    )


def _mock_mode_card():
    return Card(
        Div(
            Alert("Backend connection is not enabled.", variant="warning", cls="mb-3"),
            P("Sign-in becomes available when the backend connection is enabled.", cls="text-muted"),
            Div(
                A("Open dashboard", href="/dashboard", cls="btn btn-primary admin-primary-btn"),
                A("System status", href="/dashboard?profile=state_overseer", cls="btn btn-outline-primary admin-inline-btn"),
                cls="d-flex flex-wrap gap-2",
            ),
            cls="d-grid gap-2",
        ),
        cls="admin-auth-card border-0 shadow-lg p-2 p-sm-3",
    )


def register_auth_routes(app) -> None:
    @app.get("/login")
    async def login_page(request: Request, next: str = "", error: str = ""):
        config = get_backend_config()
        if config.enabled and AuthService.is_authenticated(request):
            return RedirectResponse(AuthService.with_profile_query(request, next or "/dashboard"), status_code=303)
        next_path = AuthService.sanitize_next_path(next) or "/dashboard"
        content = _login_form(next_path=next_path, error=error or None) if config.enabled else _mock_mode_card()
        subtitle = (
            "Sign in with your admin account."
            if config.enabled
            else "Backend connection is required for sign-in."
        )
        return _auth_layout(
            content=content,
            toast_message=error or None,
            toast_variant="danger" if error else "info",
            toast_title="Sign in failed" if error else None,
        )

    @app.post("/login")
    async def login_submit(request: Request, email: str = "", password: str = "", next: str = ""):
        config = get_backend_config()
        if not config.enabled:
            target = AuthService.sanitize_next_path(next) or "/dashboard"
            return RedirectResponse(target, status_code=303)
        try:
            identity = await AuthService.authenticate(email=email.strip(), password=password)
        except (BackendClientError, ValueError) as exc:
            next_path = AuthService.sanitize_next_path(next) or "/dashboard"
            error_message = str(exc)
            if not error_message or "Client error" in error_message or "401" in error_message:
                error_message = "Invalid email or password. Please check your credentials and try again."
            return _auth_layout(
                content=_login_form(next_path=next_path, error=error_message),
                toast_message=error_message,
                toast_variant="danger",
                toast_title="Sign in failed",
            )
        target = AuthService.sanitize_next_path(next) or "/dashboard"
        response = RedirectResponse(_append_profile(target, identity.profile_key), status_code=303)
        await AuthService.persist_identity(response, identity)
        return response

    @app.get("/logout")
    async def logout(request: Request):
        destination = "/login" if get_backend_config().enabled else "/dashboard"
        response = RedirectResponse(destination, status_code=303)
        refresh_token = AuthService.get_refresh_token(request)
        if get_backend_config().enabled and refresh_token:
            try:
                from ..communication.api_client import get_api_client

                await get_api_client().logout(refresh_token)
            except BackendClientError:
                # Always clear browser credentials even when the backend is
                # unavailable; revocation is best effort during logout.
                pass
        await AuthService.clear_identity(response)
        return response
