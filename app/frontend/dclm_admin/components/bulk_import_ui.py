"""
Bulk Import / Export UI Components using Faststrap.

Provides:
- Hierarchy Import Drawer & Validation Preview
- Workers Import Drawer & Validation Preview
"""
from __future__ import annotations

import base64
from typing import Any

from fasthtml.common import A, Div, Form, H3, H4, H5, H6, Input, Li, P, Span, Ul
from faststrap import Alert, Badge, Button, FileInput, Icon, Select, Spinner

from ..components.shell import hidden_context_inputs


def hierarchy_import_drawer(ctx, states: list[dict[str, Any]], *, selected_state_id: str = "") -> Div:
    """Render the hierarchy import form inside the offcanvas drawer."""
    state_options = [
        (
            str(s.get("entity_id") or s.get("id") or s.get("state_id") or ""),
            str(s.get("label") or s.get("name") or s.get("state_name") or "State"),
            str(s.get("entity_id") or s.get("id") or s.get("state_id") or "") == selected_state_id
            or (not selected_state_id and "kwara" in str(s.get("label") or "").lower()),
        )
        for s in states
    ]
    if not state_options:
        state_options = [("", "Kwara State (Default)", True)]

    return Div(
        Div(
            H3("Bulk Hierarchy Import", cls="h5 fw-bold mb-1"),
            P(
                "Upload a structured Excel (.xlsx) or CSV spreadsheet containing Regions, Groups, and Locations. "
                "The system will automatically generate all IDs and ltree paths.",
                cls="text-muted small mb-3",
            ),
            cls="mb-3",
        ),
        Div(
            A(
                Icon("download", cls="me-1"),
                "Download Excel Template",
                href="/bulk/templates/hierarchy",
                download="DCL_Hierarchy_Import_Template.xlsx",
                cls="btn btn-outline-primary btn-sm mb-3 w-100",
            ),
        ),
        Form(
            *hidden_context_inputs(ctx),
            Div(
                Select(
                    "state_id",
                    *state_options,
                    label="Target State",
                    help_text="Choose the state where new regions, groups, and locations will be created.",
                    required=True,
                    cls="mb-3",
                ),
            ),
            Div(
                FileInput(
                    "file",
                    label="Spreadsheet File (.xlsx or .csv)",
                    accept=".xlsx,.csv",
                    required=True,
                    helper_text="Supports multi-tab workbooks (Regions, Groups, Locations) or single-table CSVs.",
                    cls="mb-3",
                ),
            ),
            Button(
                Icon("eye", cls="me-1"),
                "Validate & Preview",
                variant="primary",
                type="submit",
                cls="w-100 mt-2",
            ),
            hx_post=ctx.url_for("/organization/hierarchy/import/preview"),
            hx_target="#hierarchy-import-results",
            hx_swap="innerHTML",
            hx_encoding="multipart/form-data",
            hx_indicator="#hierarchy-import-spinner",
            cls="mb-3",
        ),
        Div(
            Div(
                Spinner(variant="primary", size="sm", label="Validating file"),
                Span(" Parsing spreadsheet and checking for duplicates...", cls="small text-muted ms-2"),
                id="hierarchy-import-spinner",
                cls="htmx-indicator my-3 text-center",
            ),
            Div(id="hierarchy-import-results"),
        ),
    )


def hierarchy_import_preview(
    ctx,
    *,
    valid: bool,
    summary: dict[str, int],
    errors: list[dict[str, Any]],
    preview: dict[str, list[str]],
    file_bytes_b64: str,
    filename: str,
    state_id: str,
) -> Div:
    """Render the dry-run validation results and commit button."""
    if not valid or errors:
        error_items = [
            Li(
                Span(f"[{e.get('sheet', 'Sheet')} - Row {e.get('row', '?')}] ", cls="fw-semibold"),
                Span(f"{e.get('column', '')}: ", cls="text-body-secondary"),
                Span(e.get("message", "Validation error")),
                cls="mb-1",
            )
            for e in errors[:15]
        ]
        if len(errors) > 15:
            error_items.append(Li(f"... and {len(errors) - 15} more errors.", cls="text-muted fst-italic"))

        return Div(
            Alert(
                H4("Validation Issues Found", cls="h6 fw-bold mb-2"),
                P(
                    f"Discovered {len(errors)} error(s). Please correct the spreadsheet and try again.",
                    cls="small mb-2",
                ),
                Ul(*error_items, cls="small mb-0 ps-3"),
                variant="danger",
                cls="mb-3",
            ),
        )

    # Valid preview
    regions = preview.get("regions", [])
    groups = preview.get("groups", [])
    locations = preview.get("locations", [])

    return Div(
        Alert(
            H4("Spreadsheet Verified Successfully", cls="h6 fw-bold mb-2 text-success"),
            P("All rows passed format and duplicate checks. Review the summary below to confirm:", cls="small mb-3"),
            Div(
                Badge(f"{summary.get('regions', len(regions))} Regions", variant="primary", cls="me-1 mb-1"),
                Badge(f"{summary.get('groups', len(groups))} Groups", variant="info", cls="me-1 mb-1"),
                Badge(f"{summary.get('locations', len(locations))} Locations", variant="success", cls="me-1 mb-1"),
                cls="d-flex flex-wrap gap-1 mb-3",
            ),
            Div(
                H5("Sample Elements to Create:", cls="h6 fw-semibold text-muted mb-2"),
                Div(
                    P(f"• Regions: {', '.join(regions[:4]) or 'None'}", cls="small mb-1"),
                    P(f"• Groups: {', '.join(groups[:4]) or 'None'}", cls="small mb-1"),
                    P(f"• Locations: {', '.join(locations[:6]) or 'None'}", cls="small mb-0"),
                    cls="p-2 bg-body-tertiary rounded mb-3",
                ),
            ),
            Form(
                *hidden_context_inputs(ctx),
                Input(type="hidden", name="file_b64", value=file_bytes_b64),
                Input(type="hidden", name="filename", value=filename),
                Input(type="hidden", name="state_id", value=state_id),
                Button(
                    Icon("check-circle", cls="me-1"),
                    "Confirm & Commit to Database",
                    variant="success",
                    type="submit",
                    cls="w-100",
                ),
                hx_post=ctx.url_for("/organization/hierarchy/import/commit"),
                hx_target="#hierarchy-import-results",
                hx_swap="innerHTML",
                hx_indicator="#hierarchy-import-spinner",
            ),
            variant="success",
            cls="mb-3",
        ),
    )


def workers_import_drawer(ctx, *, default_state_code: str = "KW") -> Div:
    """Render the workers bulk import form inside the offcanvas drawer."""
    return Div(
        Div(
            H3("Bulk Workers Import", cls="h5 fw-bold mb-1"),
            P(
                "Upload a spreadsheet of church workers. Workers will be automatically registered, "
                "assigned generated unique worker codes, and linked to their respective locations.",
                cls="text-muted small mb-3",
            ),
            cls="mb-3",
        ),
        Div(
            A(
                Icon("download", cls="me-1"),
                "Download Workers Template",
                href="/bulk/templates/workers",
                download="DCL_Workers_Import_Template.xlsx",
                cls="btn btn-outline-primary btn-sm mb-3 w-100",
            ),
        ),
        Form(
            *hidden_context_inputs(ctx),
            Div(
                FileInput(
                    "file",
                    label="Workers File (.xlsx or .csv)",
                    accept=".xlsx,.csv",
                    required=True,
                    helper_text="Headers: Full Name, Gender, Phone, Email, Location Name, Unit, Address, Occupation, Marital Status.",
                    cls="mb-3",
                ),
            ),
            Div(
                Input(
                    type="text",
                    name="state_code",
                    value=default_state_code,
                    placeholder="State Code (e.g. KW)",
                    cls="form-control mb-3",
                ),
            ),
            Button(
                Icon("eye", cls="me-1"),
                "Validate & Preview",
                variant="primary",
                type="submit",
                cls="w-100 mt-2",
            ),
            hx_post=ctx.url_for("/people/workers/import/preview"),
            hx_target="#workers-import-results",
            hx_swap="innerHTML",
            hx_encoding="multipart/form-data",
            hx_indicator="#workers-import-spinner",
            cls="mb-3",
        ),
        Div(
            Div(
                Spinner(variant="primary", size="sm", label="Validating workers"),
                Span(" Checking phone/email uniqueness and location mappings...", cls="small text-muted ms-2"),
                id="workers-import-spinner",
                cls="htmx-indicator my-3 text-center",
            ),
            Div(id="workers-import-results"),
        ),
    )


def workers_import_preview(
    ctx,
    *,
    valid: bool,
    summary: dict[str, int],
    errors: list[dict[str, Any]],
    preview: list[str],
    file_bytes_b64: str,
    filename: str,
    state_code: str,
) -> Div:
    """Render the dry-run validation results and commit button for workers."""
    if not valid or errors:
        error_items = [
            Li(
                Span(f"[Row {e.get('row', '?')}] ", cls="fw-semibold"),
                Span(f"{e.get('column', '')}: ", cls="text-body-secondary"),
                Span(e.get("message", "Validation error")),
                cls="mb-1",
            )
            for e in errors[:15]
        ]
        if len(errors) > 15:
            error_items.append(Li(f"... and {len(errors) - 15} more errors.", cls="text-muted fst-italic"))

        return Div(
            Alert(
                H4("Validation Issues Found", cls="h6 fw-bold mb-2"),
                P(
                    f"Discovered {len(errors)} error(s). Please correct phone/email duplicates or invalid location names and try again.",
                    cls="small mb-2",
                ),
                Ul(*error_items, cls="small mb-0 ps-3"),
                variant="danger",
                cls="mb-3",
            ),
        )

    return Div(
        Alert(
            H4("Workers Sheet Verified Successfully", cls="h6 fw-bold mb-2 text-success"),
            P("All worker rows passed validation checks. Ready to register into system:", cls="small mb-3"),
            Div(
                Badge(f"{summary.get('workers', len(preview))} Workers Validated", variant="success", cls="me-1 mb-2"),
                cls="d-flex flex-wrap gap-1 mb-2",
            ),
            Div(
                H5("Sample Workers in Batch:", cls="h6 fw-semibold text-muted mb-2"),
                P(f"• {', '.join(preview[:8]) or 'None'}", cls="small mb-0 p-2 bg-body-tertiary rounded"),
                cls="mb-3",
            ),
            Form(
                *hidden_context_inputs(ctx),
                Input(type="hidden", name="file_b64", value=file_bytes_b64),
                Input(type="hidden", name="filename", value=filename),
                Input(type="hidden", name="state_code", value=state_code),
                Button(
                    Icon("check-circle", cls="me-1"),
                    f"Confirm & Register {summary.get('workers', len(preview))} Workers",
                    variant="success",
                    type="submit",
                    cls="w-100",
                ),
                hx_post=ctx.url_for("/people/workers/import/commit"),
                hx_target="#workers-import-results",
                hx_swap="innerHTML",
                hx_indicator="#workers-import-spinner",
            ),
            variant="success",
            cls="mb-3",
        ),
    )
