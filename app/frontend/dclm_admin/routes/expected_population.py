"""State-only maintenance screen for versioned Sunday attendance estimates."""
from __future__ import annotations

import csv
import io
from datetime import date
from html import escape

from fasthtml.common import A, Div, Form, H1, H2, Input, P, Table, Tbody, Td, Textarea, Th, Thead, Tr
from faststrap import Alert, Button, Input as FsInput
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse

from ..auth_context import build_context
from ..backend import BackendClientError
from ..communication.active_scope import active_scope_context
from ..communication.api_client import get_api_client
from ..communication.async_compat import async_client
from ..communication.auth_service import AuthService
from ..components.shell import shell_layout
from ..components.ui import empty_state, page_intro, page_stack, section_card


def _can_manage_expected_population(ctx) -> bool:
    return ctx.level == 5 and ctx.has_permission("population_estimates:manage")


def _expected_population_template_csv(payload: dict) -> str:
    """Build an editable State template using full paths to disambiguate codes."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("location_code", "location_display_code", "location_name", "expected_attendance", "effective_from", "note"))
    for location in payload.get("locations", []):
        writer.writerow((
            location.get("path") or location.get("location_code") or "",
            location.get("location_code") or "",
            location.get("location_name") or "",
            "" if location.get("expected_value") is None else location.get("expected_value"),
            "",
            "",
        ))
    return output.getvalue()


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


def _bulk_preview_content(payload: dict) -> Div:
    summary = payload.get("summary") or {}
    rows = payload.get("rows") or []
    preview_rows = [
        Tr(
            Td(str(row.get("line") or "")),
            Td(str(row.get("path") or row.get("location_code") or "")),
            Td(str(row.get("location_name") or "—")),
            Td("No prior estimate" if row.get("old_value") is None else f"{int(row['old_value']):,}", cls="text-end"),
            Td("—" if row.get("new_value") is None else f"{int(row['new_value']):,}", cls="text-end"),
            Td(str(row.get("effective_from") or "—")),
            Td(f"{row.get('status')}: {row.get('message') or ''}"),
        )
        for row in rows
    ]
    errors = payload.get("errors") or []
    result = [Alert(
        f"Matched {int(summary.get('matched_locations') or 0)} locations; "
        f"{int(summary.get('unknown_codes') or 0)} unknown codes; "
        f"{int(summary.get('invalid_rows') or 0)} invalid rows; "
        f"{int(summary.get('locations_changing') or 0)} values changing; "
        f"{int(summary.get('versions_to_add') or 0)} versions would be added.",
        variant="info", role="status",
    )]
    if rows:
        result.append(Table(
            Thead(Tr(Th("CSV row"), Th("Location code / full path"), Th("Location"), Th("Old value", cls="text-end"), Th("New value", cls="text-end"), Th("Effective from"), Th("Preview result"))),
            Tbody(*preview_rows), cls="table table-sm table-hover align-middle",
        ))
    if errors:
        result.append(Alert(Div(*(P(str(error), cls="mb-1") for error in errors)), variant="danger", role="alert"))
    if payload.get("can_apply") and payload.get("preview_token"):
        result.append(Form(
            Input(type="hidden", name="preview_token", value=payload["preview_token"]),
            Button(f"Confirm and add {int(summary.get('versions_to_add') or 0)} versions", type="submit", variant="primary", size="sm"),
            P("Each row adds a new dated version and an audit entry. No earlier version is replaced.", cls="small text-muted mt-2 mb-0"),
            method="post", action="/analytics/expected-population/bulk-apply",
            hx_post="/analytics/expected-population/bulk-apply",
            hx_target="#expected-population-bulk-preview", hx_swap="innerHTML",
            hx_confirm=f"Add {int(summary.get('versions_to_add') or 0)} new estimate versions?",
        ))
    return Div(*result)


def register_expected_population_routes(app) -> None:
    @app.get("/analytics/expected-population")
    async def expected_population_page(request: Request):
        ctx = active_scope_context(request, build_context(request))
        if not _can_manage_expected_population(ctx):
            content = empty_state("shield-lock", "State leadership access required", "Your account cannot maintain expected Sunday attendance estimates.")
        else:
            client = async_client(get_api_client())
            try:
                payload = await client.get_expected_population(
                    AuthService.get_access_token(request), include_history=True,
                )
                locations = payload.get("locations") or []
                estimate_count = sum(1 for item in locations if item.get("expected_value") is not None)
                body = (
                    Div(
                        Table(
                            Thead(Tr(Th("Location"), Th("Current estimate", cls="text-end"), Th("Effective from"), Th("Add a version"), Th("Version history"))),
                            Tbody(*_estimate_rows(locations)),
                            cls="table table-hover align-middle",
                        ),
                        P("Swipe to see all estimate columns", cls="analytics-scroll-hint small text-muted"),
                        cls="table-responsive expected-population-table",
                    )
                    if locations else empty_state("geo-alt", "No locations in this State", "Add locations to the hierarchy before setting attendance estimates.")
                )
                content = page_stack(
                    page_intro("Expected Sunday attendance", "Set a dated estimate for each location. Saving always adds a version and preserves the earlier history.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
                    P("Estimates are used only for Sunday Worship. The percentage is pooled from counted location reports that have an estimate; missing reports are not treated as zero.", cls="text-muted"),
                    Alert("No estimates yet. Enter each location's expected Sunday attendance below.", variant="info", role="status") if estimate_count == 0 and locations else None,
                    section_card(
                        "Bulk upload expected attendance",
                        "Paste CSV or upload a CSV file. Use a full hierarchy path when a local location code is repeated. Preview checks every code and value before saving.",
                        Div(
                            A("Download CSV template", href="/analytics/expected-population/template.csv", cls="btn btn-outline-secondary btn-sm mb-3"),
                            Form(
                                Textarea(name="csv_text", placeholder="location_code,expected_attendance,effective_from,note", rows="5", cls="form-control mb-3", aria_label="Paste expected attendance CSV"),
                                FsInput("file", input_type="file", label="Or upload a CSV file", accept=".csv,text/csv"),
                                Button("Preview CSV", type="submit", variant="outline-primary", size="sm", cls="mt-3"),
                                method="post", action="/analytics/expected-population/bulk-preview",
                                enctype="multipart/form-data", hx_post="/analytics/expected-population/bulk-preview",
                                hx_encoding="multipart/form-data", hx_target="#expected-population-bulk-preview",
                                hx_swap="innerHTML",
                            ),
                            Div(P("A preview is required before applying. Unknown codes, duplicate codes, invalid values, or stale previews block the entire import.", cls="small text-muted mt-2"), id="expected-population-bulk-preview", aria_live="polite"),
                        ),
                    ),
                    section_card("Location estimates", f"{len(locations)} locations · current as of {payload.get('as_of') or date.today().isoformat()}", body),
                    A("Back to dashboard", href="/dashboard", cls="btn btn-outline-primary admin-inline-btn"),
                )
            except BackendClientError as exc:
                content = section_card("Expected Sunday attendance", "Estimates could not be loaded.", P(str(exc), role="alert", cls="text-danger mb-0"))
        return shell_layout(
            ctx, request_path=request.url.path, active_key="expected-population",
            title="Expected Sunday attendance", subtitle="Versioned location estimates.",
            primary_action=None, content=content, show_shell_intro=False,
        )

    @app.post("/analytics/expected-population")
    async def expected_population_save(request: Request):
        ctx = active_scope_context(request, build_context(request))
        if not _can_manage_expected_population(ctx):
            return Div(P("Your account cannot change expected Sunday attendance.", role="alert", cls="text-danger"))
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

    @app.get("/analytics/expected-population/template.csv")
    async def expected_population_csv_template(request: Request):
        ctx = active_scope_context(request, build_context(request))
        if not _can_manage_expected_population(ctx):
            return Div(P("Your account cannot download the expected-attendance template.", role="alert", cls="text-danger"))
        try:
            client = async_client(get_api_client())
            payload = await client.get_expected_population(
                AuthService.get_access_token(request), include_history=False,
            )
            csv_text = _expected_population_template_csv(payload)
        except BackendClientError as exc:
            return Div(P(f"Template could not be loaded: {escape(str(exc))}", role="alert", cls="text-danger"))
        return PlainTextResponse(
            csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="expected-sunday-attendance-template.csv"'},
        )

    @app.post("/analytics/expected-population/bulk-preview")
    async def expected_population_bulk_preview(request: Request):
        ctx = active_scope_context(request, build_context(request))
        if not _can_manage_expected_population(ctx):
            return Alert("Your account cannot preview this import.", variant="danger", role="alert")
        form = await request.form()
        upload = form.get("file")
        csv_text = str(form.get("csv_text") or "")
        if upload and hasattr(upload, "read") and getattr(upload, "filename", ""):
            raw = await upload.read(1_000_001)
            if len(raw) > 1_000_000:
                return Alert("CSV file exceeds the 1 MB limit.", variant="danger", role="alert")
            try:
                csv_text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                return Alert("CSV must be UTF-8 encoded.", variant="danger", role="alert")
        if not csv_text.strip():
            return Alert("Paste CSV content or choose a CSV file.", variant="danger", role="alert")
        try:
            client = async_client(get_api_client())
            preview = await client.preview_expected_population_csv(AuthService.get_access_token(request), csv_text)
        except BackendClientError as exc:
            return Alert(f"CSV preview failed: {exc}", variant="danger", role="alert")
        return _bulk_preview_content(preview)

    @app.post("/analytics/expected-population/bulk-apply")
    async def expected_population_bulk_apply(request: Request):
        ctx = active_scope_context(request, build_context(request))
        if not _can_manage_expected_population(ctx):
            return Alert("Your account cannot apply this import.", variant="danger", role="alert")
        form = await request.form()
        preview_token = str(form.get("preview_token") or "")
        if not preview_token:
            return Alert("Preview token is missing. Preview the CSV again.", variant="danger", role="alert")
        try:
            client = async_client(get_api_client())
            result = await client.apply_expected_population_csv(AuthService.get_access_token(request), preview_token)
        except BackendClientError as exc:
            return Alert(f"CSV was not applied: {exc}", variant="danger", role="alert")
        return Div(
            Alert(f"Added {int(result.get('versions_added') or 0)} estimate versions with matching audit entries.", variant="success", role="status"),
            A("Reload estimate history", href="/analytics/expected-population", cls="btn btn-outline-primary btn-sm"),
        )
