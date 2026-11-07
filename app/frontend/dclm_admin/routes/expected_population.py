"""State-only maintenance screen for versioned Sunday attendance estimates."""
from __future__ import annotations

from datetime import date
from html import escape

from fasthtml.common import A, Div, Form, H1, H2, Input, P, Table, Tbody, Td, Th, Thead, Tr
from faststrap import Alert, Button
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..auth_context import build_context
from ..backend import BackendClientError
from ..communication.active_scope import active_scope_context
from ..communication.api_client import get_api_client
from ..communication.async_compat import async_client
from ..communication.auth_service import AuthService
from ..components.shell import shell_layout
from ..components.ui import empty_state, page_intro, page_stack, section_card


def _is_state_overseer(ctx) -> bool:
    return ctx.level == 5 and ctx.profile.role_label == "State Overseer"


def _estimate_rows(locations: list[dict]) -> list:
    rows = []
    for location in locations:
        history = location.get("history") or []
        history_rows = [
            Tr(
                Td(item.get("effective_from") or "—"),
                Td(f"{int(item.get('expected_value') or 0):,}", cls="text-end"),
                Td(item.get("set_by") or "—"),
                Td(item.get("note") or "—"),
            )
            for item in history
        ]
        history_table = (
            Table(
                Thead(Tr(Th("Effective from"), Th("Expected attendance", cls="text-end"), Th("Set by"), Th("Note"))),
                Tbody(*history_rows),
                cls="table table-sm align-middle",
            )
            if history_rows else P("No previous estimate versions.", cls="small text-muted mb-0")
        )
        current = location.get("expected_value")
        location_id = str(location.get("location_id") or "")
        rows.append(Tr(
            Td(
                P(str(location.get("location_name") or "Location"), cls="fw-semibold mb-1"),
                P(str(location.get("location_code") or ""), cls="small text-muted mb-0"),
            ),
            Td("No estimate yet" if current is None else f"{int(current):,}", cls="text-end"),
            Td(location.get("effective_from") or "—"),
            Td(
                Form(
                    Input(type="hidden", name="location_id", value=location_id),
                    Input(type="number", name="expected_value", min="0", max="10000000", required=True, value="" if current is None else str(current), cls="form-control form-control-sm", aria_label=f"Expected Sunday attendance for {location.get('location_name')}"),
                    Input(type="date", name="effective_from", required=True, value=date.today().isoformat(), cls="form-control form-control-sm mt-2", aria_label="Effective from date"),
                    Input(type="text", name="note", maxlength="2000", placeholder="Reason or source (optional)", cls="form-control form-control-sm mt-2", aria_label="Note"),
                    Button("Save new version", type="submit", variant="primary", size="sm", cls="mt-2"),
                    method="post",
                    action="/analytics/expected-population",
                    cls="expected-population-edit-form",
                ),
            ),
            Td(
                Div("History", cls="visually-hidden"),
                Div(history_table, cls="pt-2"),
            ),
        ))
    return rows


def register_expected_population_routes(app) -> None:
    @app.get("/analytics/expected-population")
    async def expected_population_page(request: Request):
        ctx = active_scope_context(request, build_context(request))
        if not _is_state_overseer(ctx):
            content = empty_state("shield-lock", "State Overseer access required", "Only the State Overseer can maintain expected Sunday attendance estimates.")
        else:
            client = async_client(get_api_client())
            try:
                payload = await client.get_expected_population(
                    AuthService.get_access_token(request), include_history=True,
                )
                locations = payload.get("locations") or []
                estimate_count = sum(1 for item in locations if item.get("expected_value") is not None)
                body = (
                    Table(
                        Thead(Tr(Th("Location"), Th("Current estimate", cls="text-end"), Th("Effective from"), Th("Add a version"), Th("Version history"))),
                        Tbody(*_estimate_rows(locations)),
                        cls="table table-hover align-middle expected-population-table",
                    )
                    if locations else empty_state("geo-alt", "No locations in this State", "Add locations to the hierarchy before setting attendance estimates.")
                )
                content = page_stack(
                    page_intro("Expected Sunday attendance", "Set a dated estimate for each location. Saving always adds a version and preserves the earlier history.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
                    P("Estimates are used only for Sunday Worship. The percentage is pooled from counted location reports that have an estimate; missing reports are not treated as zero.", cls="text-muted"),
                    Alert("No estimates yet. Enter each location's expected Sunday attendance below.", variant="info", role="status") if estimate_count == 0 and locations else None,
                    section_card("Location estimates", f"{len(locations)} locations · current as of {payload.get('as_of') or date.today().isoformat()}", body),
                    A("Back to dashboard", href="/dashboard", cls="btn btn-outline-primary admin-inline-btn"),
                )
            except BackendClientError as exc:
                content = section_card("Expected Sunday attendance", "Estimates could not be loaded.", P(str(exc), role="alert", cls="text-danger mb-0"))
        return shell_layout(
            ctx, request_path=request.url.path, active_key="dashboard",
            title="Expected Sunday attendance", subtitle="Versioned location estimates.",
            primary_action=None, content=content, show_shell_intro=False,
        )

    @app.post("/analytics/expected-population")
    async def expected_population_save(request: Request):
        ctx = active_scope_context(request, build_context(request))
        if not _is_state_overseer(ctx):
            return Div(P("Only the State Overseer can change expected Sunday attendance.", role="alert", cls="text-danger"))
        form = await request.form()
        try:
            location_id = str(form.get("location_id") or "")
            expected_value = int(str(form.get("expected_value") or ""))
            effective_from = date.fromisoformat(str(form.get("effective_from") or ""))
            note = str(form.get("note") or "").strip()
            if expected_value < 0 or expected_value > 10_000_000:
                raise ValueError("Enter an estimate from 0 to 10,000,000.")
            client = async_client(get_api_client())
            await client.create_expected_population_version(
                AuthService.get_access_token(request), location_id=location_id,
                expected_value=expected_value, effective_from=effective_from.isoformat(), note=note,
            )
        except (ValueError, BackendClientError) as exc:
            return Div(P(f"Estimate was not saved: {escape(str(exc))}", role="alert", cls="text-danger mb-0"))
        return RedirectResponse("/analytics/expected-population?saved=1", status_code=303)
