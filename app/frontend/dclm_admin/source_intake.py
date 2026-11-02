from __future__ import annotations

from fasthtml.common import Div, H4, P
from starlette.responses import PlainTextResponse


def source_intake_notice(record_type: str) -> Div:
    return Div(
        H4("Enter this through the Level 1-2 Data Sourcing app", cls="h6 fw-semibold mb-2"),
        P(
            f"{record_type} submissions are collected in the dedicated data-sourcing app. "
            "This console is for scoped oversight, review, reporting, and technical administration.",
            cls="mb-0",
        ),
        role="status",
        cls="alert alert-info mb-0",
    )


def reject_source_submission() -> PlainTextResponse:
    return PlainTextResponse(
        "Source submissions must be entered through the Level 1-2 Data Sourcing app.",
        status_code=403,
    )
