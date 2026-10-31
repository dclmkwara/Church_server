from __future__ import annotations

import logging
from typing import Any
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from fasthtml.common import A, Body, Div, H1, H2, Head, Html, Link, Meta, P, Title, to_xml
from faststrap import Alert, Button, Card, Icon

logger = logging.getLogger(__name__)


def _error_page_layout(
    *,
    status_code: int,
    badge_label: str,
    title: str,
    message: str,
    icon: str,
    tone: str = "primary",
    request_path: str = "/",
) -> Html:
    """Renders a standalone, fully styled DCLM Admin error page matching the design system."""
    return Html(
        Head(
            Title(f"{status_code} - {title} | DCLM Admin"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1, shrink-to-fit=no"),
            Link(rel="icon", type="image/png", href="/assets/favicon.png"),
            Link(rel="stylesheet", href="/assets/css/admin.css"),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
            ),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
            ),
            Link(
                rel="stylesheet",
                href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
            ),
        ),
        Body(
            Div(
                Card(
                    Div(
                        # Top icon pill
                        Div(
                            Icon(icon, cls=f"fs-1 text-{tone}"),
                            cls=f"d-inline-flex align-items-center justify-content-center rounded-circle bg-{tone}-subtle mb-3 p-3",
                            style="width: 72px; height: 72px;",
                        ),
                        # Error Code
                        H1(str(status_code), cls=f"display-3 fw-bold text-{tone} mb-2 tracking-tight"),
                        # Title
                        H2(title, cls="h4 fw-bold text-body-emphasis mb-3"),
                        # Description
                        P(message, cls="text-secondary lead fs-6 mb-4", style="max-width: 440px; margin-inline: auto;"),
                        # Action Buttons
                        Div(
                            A(
                                Icon("house", cls="me-1"),
                                "Return to Dashboard",
                                href="/dashboard",
                                cls=f"btn btn-{tone} px-4 py-2 fw-medium shadow-sm",
                            ),
                            A(
                                Icon("arrow-clockwise", cls="me-1"),
                                "Try Again",
                                href=request_path,
                                cls="btn btn-outline-secondary px-4 py-2 fw-medium",
                            ),
                            cls="d-flex flex-wrap align-items-center justify-content-center gap-2",
                        ),
                        cls="text-center p-4 p-md-5",
                    ),
                    cls="border-0 shadow-lg mx-auto",
                    style="max-width: 520px; border-radius: 1rem;",
                ),
                cls="d-flex align-items-center justify-content-center min-vh-100 p-3 bg-body-tertiary",
            ),
            cls="bg-body-tertiary",
            **{"data-bs-theme": "light"},
        ),
    )


def not_found_response(request: Request, exc: Exception | None = None) -> Response:
    """Custom 404 Not Found response."""
    # Check if request is HTMX partial
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            to_xml(
                Alert(
                    Icon("exclamation-circle", cls="me-2 fs-5"),
                    "The requested item or section could not be found.",
                    variant="warning",
                    cls="shadow-sm border-0 my-3",
                )
            ),
            status_code=404,
        )

    content = _error_page_layout(
        status_code=404,
        badge_label="Page Not Found",
        title="Page Not Found",
        message="The page or resource you are looking for doesn't exist, has been removed, or the link has expired.",
        icon="compass",
        tone="primary",
        request_path=str(request.url.path),
    )
    return HTMLResponse(to_xml(content), status_code=404)


def server_error_response(request: Request, exc: Exception | None = None) -> Response:
    """Custom 500 Internal Server Error response."""
    # When token expires or cannot be authenticated, send user to login rather than showing 500 error
    if exc and (
        getattr(exc, "status_code", None) in (401, 403)
        or any(k in str(exc).lower() for k in ("unauthorized", "validate credentials", "expired", "not authenticated"))
    ):
        if request.headers.get("HX-Request"):
            return Response(status_code=200, headers={"HX-Redirect": "/login"})
        return RedirectResponse("/login", status_code=303)

    logger.error(
        "Unhandled server error on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=(type(exc), exc, exc.__traceback__) if exc else None,
    )

    # Check if request is HTMX partial
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            to_xml(
                Alert(
                    Icon("exclamation-triangle", cls="me-2 fs-5"),
                    "An unexpected error occurred while processing this request. Please refresh or try again.",
                    variant="danger",
                    cls="shadow-sm border-0 my-3",
                )
            ),
            status_code=500,
        )

    content = _error_page_layout(
        status_code=500,
        badge_label="Server Error",
        title="Something Went Wrong",
        message="An unexpected server error occurred while processing your request. Please try again or return to the dashboard.",
        icon="exclamation-triangle",
        tone="danger",
        request_path=str(request.url.path),
    )
    return HTMLResponse(to_xml(content), status_code=500)
