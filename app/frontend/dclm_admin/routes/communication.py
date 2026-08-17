from __future__ import annotations

import asyncio
from html import escape
from typing import Any
from urllib.parse import quote

from fasthtml.common import A, Div, Form, H3, H4, Input, Option, P, Select, Span, Textarea
from starlette.requests import Request
from starlette.responses import RedirectResponse

from faststrap import Accordion, AccordionItem, Button, Card, FilterBar, Image, PlaceholderCard, Spinner, TabPane, Tabs, ToggleGroup

from ..auth_context import build_context
from ..communication import CommunicationService
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, shell_layout
from ..components.ui import empty_state, filter_field, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE, in_scope


STATUS_FILTERS = [
    ("all", "All"),
    ("published", "Published"),
    ("draft", "Drafts"),
    ("archived", "Archived"),
]

MEETING_OPTIONS = [
    ("workers_meeting", "Workers Meeting"),
    ("leaders_briefing", "Leaders Briefing"),
    ("sunday_service", "Sunday Service"),
    ("special_notice", "Special Notice"),
]

MEDIA_VISIBILITY_OPTIONS = [
    ("all", "All visibility"),
    ("scope_only", "This scope only"),
    ("national_share", "Shared upward"),
    ("private_review", "Private review"),
]

MEDIA_TYPE_OPTIONS = [
    ("all", "All items"),
    ("photo", "Photos"),
    ("video", "Videos"),
]


async def _communication_live(request: Request) -> bool:
    return await CommunicationService.live_enabled(request)


async def _announcement_summary_data(request: Request, ctx) -> dict[str, int]:
    live_mode = await _communication_live(request)
    return (
        await CommunicationService.announcement_summary(request, ctx)
        if live_mode
        else STORE.announcement_summary(ctx.current_scope_path)
    )


async def _announcement_rows(request: Request, ctx, *, search: str = "", status: str = "all", meeting: str = "") -> list[dict[str, Any]]:
    live_mode = await _communication_live(request)
    return (
        await CommunicationService.list_announcements(request, ctx, search=search, status=status, meeting=meeting)
        if live_mode
        else STORE.list_announcements(ctx.current_scope_path, search=search, status=status, meeting=meeting)
    )


async def _announcement_row(request: Request, ctx, announcement_id: str) -> dict[str, Any] | None:
    live_mode = await _communication_live(request)
    row = (
        await CommunicationService.get_announcement(request, announcement_id)
        if live_mode
        else STORE.get_announcement(announcement_id)
    )
    if row is None:
        return None
    if not live_mode and not in_scope(row["path"], ctx.current_scope_path):
        return None
    return row


async def _media_summary_data(request: Request, ctx) -> dict[str, int]:
    live_mode = await _communication_live(request)
    return (
        await CommunicationService.media_summary(request, ctx)
        if live_mode
        else STORE.media_gallery_summary(ctx.current_scope_path)
    )


async def _gallery_rows(request: Request, ctx, *, search: str = "", visibility: str = "all") -> list[dict[str, Any]]:
    live_mode = await _communication_live(request)
    return (
        await CommunicationService.list_galleries(request, ctx, search=search, visibility=visibility)
        if live_mode
        else STORE.list_media_galleries(ctx.current_scope_path, search=search, visibility=visibility)
    )


async def _gallery_row(request: Request, ctx, gallery_id: str) -> dict[str, Any] | None:
    live_mode = await _communication_live(request)
    row = (
        await CommunicationService.get_gallery(request, ctx, gallery_id)
        if live_mode
        else STORE.get_media_gallery(gallery_id)
    )
    if row is None:
        return None
    if not live_mode and not in_scope(row["path"], ctx.current_scope_path):
        return None
    return row


async def _media_items(request: Request, ctx, *, search: str = "", media_type: str = "all", gallery_id: str = "") -> list[dict[str, Any]]:
    live_mode = await _communication_live(request)
    return (
        await CommunicationService.list_media_items(request, ctx, search=search, media_type=media_type, gallery_id=gallery_id)
        if live_mode
        else STORE.list_media_items(ctx.current_scope_path, search=search, media_type=media_type, gallery_id=gallery_id)
    )


async def _media_item_row(request: Request, ctx, item_id: str) -> dict[str, Any] | None:
    live_mode = await _communication_live(request)
    row = (
        await CommunicationService.get_media_item(request, ctx, item_id)
        if live_mode
        else STORE.get_media_item(item_id)
    )
    if row is None:
        return None
    if not live_mode and not in_scope(row["path"], ctx.current_scope_path):
        return None
    return row


def _communication_section_nav(ctx, active_key: str) -> Div:
    return Div(
        Button(
            "Weekly Notes",
            href=ctx.url_for("/communication"),
            variant="primary" if active_key == "notes" else "outline-primary",
            size="md",
            pill=True,
            cls="admin-inline-btn",
            **({"aria_current": "page"} if active_key == "notes" else {}),
        ),
        Button(
            "Media Galleries",
            href=ctx.url_for("/communication/media"),
            variant="primary" if active_key == "media" else "outline-primary",
            size="md",
            pill=True,
            cls="admin-inline-btn",
            **({"aria_current": "page"} if active_key == "media" else {}),
        ),
        cls="workspace-tab-strip section-nav-strip mb-3",
    )


def _communication_loading_shell(
    ctx,
    *,
    active_key: str,
    title: str,
    subtitle: str,
    section_title: str,
    section_note: str,
    target_url: str,
) -> Div:
    return page_stack(
        _communication_section_nav(ctx, active_key),
        page_intro(
            title,
            subtitle,
            scope_label=ctx.current_scope_label,
            scope_kind=ctx.current_scope_kind,
        ),
        Div(
            Div(
                H3(section_title, cls="h5 fw-semibold mb-1"),
                P(section_note, cls="text-muted mb-0"),
                cls="d-grid gap-1",
            ),
            Div(Spinner(size="sm"), P("Loading communication records...", cls="text-muted mb-0"), cls="d-flex align-items-center gap-2"),
            PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
            PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
            id="communication-page-content",
            hx_get=target_url,
            hx_trigger="load",
            hx_swap="innerHTML",
            cls="d-grid gap-3",
        ),
    )


def _svg_placeholder(title: str, subtitle: str, accent: str) -> str:
    safe_title = escape(title)
    safe_subtitle = escape(subtitle)
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 420" role="img" aria-label="{safe_title}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{accent}" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
  </defs>
  <rect width="800" height="420" rx="32" fill="url(#bg)" />
  <circle cx="680" cy="82" r="84" fill="rgba(255,255,255,0.12)" />
  <circle cx="120" cy="360" r="120" fill="rgba(255,255,255,0.10)" />
  <text x="56" y="248" fill="#ffffff" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="42" font-weight="700">{safe_title}</text>
  <text x="56" y="298" fill="rgba(255,255,255,0.84)" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="24">{safe_subtitle}</text>
</svg>
""".strip()
    return f"data:image/svg+xml;utf8,{quote(svg)}"


def _gallery_cover_src(row: dict[str, Any]) -> str:
    accents = {
        "scope_only": "#1d4ed8",
        "national_share": "#059669",
        "private_review": "#d97706",
    }
    return _svg_placeholder(row["title"], row["event_name"], accents.get(row["visibility"], "#1d4ed8"))


def _media_item_thumb_src(item: dict[str, Any]) -> str:
    accents = {"photo": "#1d4ed8", "video": "#7c3aed"}
    subtitle = item.get("gallery_title", item.get("file_label", ""))
    return _svg_placeholder(item["title"], subtitle, accents.get(item["media_type"], "#1d4ed8"))


async def _communication_summary(request: Request, ctx, *, oob: bool = False) -> Div:
    summary = await _announcement_summary_data(request, ctx)
    attrs = {"id": "communication-summary"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#communication-summary"
    return Div(
        stat_card("Notes", str(summary["total"]), "Communication entries", "megaphone", tone="primary"),
        stat_card("Published", str(summary["published"]), "Already ready to share", "check2-circle", tone="success"),
        stat_card("Drafts", str(summary["drafts"]), "Still waiting for final review", "pencil-square", tone="warning"),
        stat_card("Archived", str(summary["archived"]), "Older notes kept for reference", "archive", tone="info"),
        cls="counts-stat-grid",
        **attrs,
    )


def _communication_mobile_card(ctx, row: dict[str, Any], *, search: str = "", status: str = "all", meeting: str = "") -> Div:
    return Div(
        Div(
            H4(row["title"], cls="h6 fw-semibold mb-1"),
            status_badge(row["status"]),
            cls="d-flex justify-content-between gap-3 mb-2",
        ),
        P(f"{row['meeting_label']} - {row['meeting_date']}", cls="text-muted mb-2"),
        P(row["summary"], cls="small text-muted mb-3"),
        Div(
            Button(
                "Open",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(
                    f"/communication/{row['announcement_id']}/drawer",
                    search_filter=search,
                    status_filter=status,
                    meeting_filter=meeting,
                ),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="w-100",
            ),
            A("Edit", href=ctx.url_for(f"/communication/{row['announcement_id']}/edit"), cls="btn btn-primary"),
            cls="d-grid gap-2",
        ),
        cls="mobile-worker-card",
    )


async def _communication_workspace(request: Request, ctx, *, search: str = "", status: str = "all", meeting: str = "", oob: bool = False) -> Div:
    rows = await _announcement_rows(request, ctx, search=search, status=status, meeting=meeting)
    active_index = next((index for index, row in enumerate(STATUS_FILTERS) if row[0] == status), 0)
    status_toggle = ToggleGroup(
        *[
            Button(
                label,
                variant="outline-primary",
                size="md",
                hx_get=ctx.url_for("/communication/list", search=search, status=key, meeting=meeting),
                hx_target="#communication-workspace",
                hx_swap="outerHTML",
                cls="inbox-filter-chip",
            )
            for key, label in STATUS_FILTERS
        ],
        active_index=active_index,
        active_cls="active",
        cls="filter-chip-row admin-toggle-group",
    )

    filter_form = Form(
        *hidden_context_inputs(ctx),
        Input(type="hidden", name="status", value=status),
        filter_field(
            "Search communication",
            Input(
                type="search",
                name="search",
                value=search,
                placeholder="Search title, meeting, audience, or summary",
                cls="form-control",
            ),
            field_id="communication-search",
        ),
        filter_field(
            "Meeting",
            Select(
                Option("All meetings", value=""),
                *[Option(label, value=key, selected=meeting == key) for key, label in MEETING_OPTIONS],
                name="meeting",
                cls="form-select",
            ),
            field_id="communication-meeting",
        ),
        hx_get=ctx.url_for("/communication/list"),
        hx_target="#communication-workspace",
        hx_swap="outerHTML",
        hx_trigger="keyup changed delay:350ms from:input, change from:select",
        cls="admin-filter-grid",
    )

    if rows:
        desktop_rows = []
        mobile_cards = []
        for row in rows:
            desktop_rows.append(
                [
                    Div(P(row["title"], cls="fw-semibold mb-1"), P(row["summary"], cls="small text-muted mb-0")),
                    row["meeting_label"],
                    row["meeting_date"],
                    row["audience"],
                    status_badge(row["status"]),
                    Div(
                        Button(
                            "Open",
                            variant="outline-primary",
                            size="md",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#detail-drawer",
                            hx_get=ctx.url_for(
                                f"/communication/{row['announcement_id']}/drawer",
                                search_filter=search,
                                status_filter=status,
                                meeting_filter=meeting,
                            ),
                            hx_target="#detail-drawer-body",
                            hx_swap="innerHTML",
                        ),
                        A("Edit", href=ctx.url_for(f"/communication/{row['announcement_id']}/edit"), cls="btn btn-primary btn-sm"),
                        cls="d-grid gap-2",
                    ),
                ]
            )
            mobile_cards.append(_communication_mobile_card(ctx, row, search=search, status=status, meeting=meeting))
        results = responsive_table(
            ["Title", "Meeting", "Date", "Audience", "Status", "Action"],
            desktop_rows,
            mobile_cards,
            results_id="communication-results",
        )
    else:
        results = empty_state(
            "megaphone",
            "No communication entries match this view",
            "Adjust the filters or create a fresh weekly note.",
        )

    attrs = {"id": "communication-workspace"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#communication-workspace"
    return Div(status_toggle, filter_form, results, **attrs)


def _communication_status_action(row: dict[str, Any]) -> tuple[str, str, str, str]:
    if row["status"] == "draft":
        return ("publish", "Publish now", "success", "Publish note")
    if row["status"] == "published":
        return ("archive", "Archive note", "outline-warning", "Archive note")
    return ("draft", "Return to draft", "outline-primary", "Return note to draft")


async def _communication_drawer_content(
    ctx,
    row: dict[str, Any],
    *,
    search_filter: str = "",
    status_filter: str = "all",
    meeting_filter: str = "",
) -> Div:
    items = row["items"] or ["No extra reminders were added."]
    action_key, action_label, action_variant, action_title = _communication_status_action(row)
    return Div(
        H3(row["title"], cls="h5 fw-semibold"),
        P(f"{row['meeting_label']} - {row['meeting_date']}", cls="text-muted"),
        Div(
            status_badge(row["status"]),
            P(row["audience"], cls="small text-muted mb-0"),
            cls="d-flex flex-wrap gap-2 align-items-center mb-3",
        ),
        Div(
            Button(
                "Edit note",
                href=ctx.url_for(f"/communication/{row['announcement_id']}/edit"),
                variant="primary",
                size="md",
            ),
            Button(
                action_label,
                variant=action_variant,
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(
                    f"/communication/{row['announcement_id']}/status",
                    action=action_key,
                    title=action_title,
                    search_filter=search_filter,
                    status_filter=status_filter,
                    meeting_filter=meeting_filter,
                ),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
            ),
            cls="d-grid gap-2 d-md-flex mb-3",
        ),
        Div(
            H4("Summary", cls="h6 fw-semibold mb-2"),
            P(row["summary"], cls="mb-0"),
            cls="drawer-note-box mb-3",
        ),
        Div(
            H4("Main message", cls="h6 fw-semibold mb-2"),
            P(row["body"], cls="mb-0"),
            cls="drawer-note-box mb-3",
        ),
        Div(
            H4("Extra points", cls="h6 fw-semibold mb-2"),
            *[P(f"{index}. {item}", cls="mb-2") for index, item in enumerate(items, start=1)],
            cls="drawer-note-box",
        ),
    )


def _items_values(source: dict[str, str], item_count: int) -> list[str]:
    return [source.get(f"item_{index}", "").strip() for index in range(1, item_count + 1)]


def _editor_items_block(ctx, item_count: int, values: list[str]) -> Div:
    limited_count = max(2, min(item_count, 8))
    fields = [
        Input(
            type="text",
            name=f"item_{index}",
            value=values[index - 1] if index - 1 < len(values) else "",
            placeholder=f"Additional point {index}",
            cls="form-control mb-3",
        )
        for index in range(1, limited_count + 1)
    ]
    add_button = ""
    if limited_count < 8:
        add_button = Button(
            "Add another point",
            variant="outline-primary",
            size="md",
            type="button",
            hx_get=ctx.url_for("/communication/editor/items", item_count=str(limited_count + 1)),
            hx_target="#communication-items-block",
            hx_swap="outerHTML",
            hx_include="closest form",
            cls="w-100",
        )
    return Div(
        H4("Additional points", cls="h6 fw-semibold mb-2"),
        P("Add short points for the message body.", cls="text-muted mb-3"),
        *fields,
        add_button,
        id="communication-items-block",
    )


def _editor_help(row: dict[str, Any] | None) -> Div:
    outline = row["items"] if row else []
    outline_body = (
        Div(*[P(f"{index}. {item}", cls="mb-2") for index, item in enumerate(outline, start=1)])
        if outline
        else P("Add a few short points to make the message easier to scan.", cls="text-muted mb-0")
    )
    return Accordion(
        AccordionItem(
            P("Keep the note plain, short, and practical."),
            title="Guidance",
            expanded=True,
        ),
        AccordionItem(outline_body, title="Outline"),
    )


async def _communication_editor_page(request: Request, row: dict[str, Any] | None = None):
    ctx = build_context(request)
    if ctx.level < 5:
        body = page_stack(section_card(
                "Communication",
                "Weekly communication opens from Level 5 upward.",
                empty_state("megaphone", "Communication unavailable", "This role cannot manage communication records."),
        ))
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="communication",
            title="Communication",
            subtitle="Weekly notes and announcements.",
            primary_action=None,
            content=body,
        )

    item_count = max(2, len(row["items"]) if row else 3)
    item_values = row["items"] if row else []
    action = ctx.url_for("/communication/create") if row is None else ctx.url_for(f"/communication/{row['announcement_id']}/update")
    subtitle = "Create a clear weekly note."
    if row is not None:
        subtitle = "Edit the note, keep the message plain, and publish only when it is ready to share."

    form = Form(
        *hidden_context_inputs(ctx),
        section_card(
            "Basic details",
            "Begin with the meeting, date, and who needs to receive this note.",
            Div(
                Input(type="text", name="title", value=row["title"] if row else "", placeholder="Communication title", cls="form-control", required=True),
                Select(
                    Option("Select meeting", value=""),
                    *[Option(label, value=key, selected=row is not None and row["meeting"] == key) for key, label in MEETING_OPTIONS],
                    name="meeting",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="date", name="meeting_date", value=row["meeting_date"] if row else "", cls="form-control", required=True),
                Input(type="text", name="audience", value=row["audience"] if row else "", placeholder="Audience", cls="form-control", required=True),
                cls="drawer-two-up",
            ),
        ),
        section_card(
            "Main message",
            "Lead with the action people should take, then give only the details needed to act.",
            Textarea(
                row["summary"] if row else "",
                name="summary",
                placeholder="Short summary",
                cls="form-control mb-3",
                rows="3",
                required=True,
            ),
            Textarea(
                row["body"] if row else "",
                name="body",
                placeholder="Full message body",
                cls="form-control",
                rows="8",
                required=True,
            ),
        ),
        section_card(
            "Extra reminders",
            "Keep supporting points short and practical.",
            _editor_items_block(ctx, item_count, item_values),
        ),
        section_card(
            "Editor help",
            "Keep the note clear and concise.",
            _editor_help(row),
        ),
        Div(
            Button("Save Draft", variant="outline-primary", size="md", type="submit", name="submit_action", value="draft"),
            Button("Publish Now", variant="primary", size="md", type="submit", name="submit_action", value="publish"),
            cls="editor-action-bar d-grid d-md-flex gap-2",
        ),
        method="post",
        action=action,
        cls="d-grid gap-4",
    )

    title = "New Communication" if row is None else "Edit Communication"
    body = page_stack(
        _communication_section_nav(ctx, "notes"),
        A("Back to communication list", href=ctx.url_for("/communication"), cls="btn btn-outline-primary admin-inline-btn mb-3"),
        page_intro(
            title,
            subtitle,
            scope_label=ctx.current_scope_label,
            scope_kind=ctx.current_scope_kind,
        ),
        form,
    )
    return shell_layout(
        ctx,
        request_path=request.url.path,
        active_key="communication",
        title=title,
        subtitle="Weekly information and announcement editor.",
        primary_action=Button("Media Galleries", href=ctx.url_for("/communication/media"), variant="outline-primary", size="md"),
        content=body,
    )


async def _media_summary(request: Request, ctx, *, oob: bool = False) -> Div:
    summary = await _media_summary_data(request, ctx)
    attrs = {"id": "media-summary"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#media-summary"
    return Div(
        stat_card("Galleries", str(summary["galleries"]), "Media collections", "images", tone="primary"),
        stat_card("Uploaded items", str(summary["items"]), "Photos and clips already recorded", "card-image", tone="success"),
        stat_card("Video clips", str(summary["videos"]), "Short clips ready for review", "camera-video", tone="warning"),
        stat_card("Shared upward", str(summary["shared_upward"]), "Galleries marked for higher visibility", "share", tone="info"),
        cls="counts-stat-grid",
        **attrs,
    )


def _media_gallery_card(ctx, row: dict[str, Any]) -> Any:
    return Card(
        Div(
            Image(
                src=_gallery_cover_src(row),
                alt=row["title"],
                fluid=True,
                rounded=True,
                loading="lazy",
                cls="media-gallery-cover",
            ),
            Div(
                Div(
                    status_badge(row["visibility"]),
                    Span(f"{row['item_count']} items", cls="small text-muted fw-semibold"),
                    cls="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2",
                ),
                H4(row["title"], cls="h5 fw-semibold mb-1"),
                P(f"{row['event_name']} - {row['event_date']}", cls="text-muted mb-2"),
                P(row["description"], cls="small text-muted mb-3"),
                Div(
                    Span(f"{row['photo_count']} photos", cls="media-meta-chip"),
                    Span(f"{row['video_count']} videos", cls="media-meta-chip"),
                    Span(row["scope_label"], cls="media-meta-chip"),
                    cls="d-flex flex-wrap gap-2",
                ),
                cls="d-grid gap-1",
            ),
        ),
        footer=Div(
            Button(
                "Open gallery",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/communication/media/galleries/{row['gallery_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
            ),
            Button(
                "Upload item",
                variant="primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for(f"/communication/media/galleries/{row['gallery_id']}/items/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            Button(
                "Delete",
                variant="outline-danger",
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(f"/communication/media/galleries/{row['gallery_id']}/delete"),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
            ),
            cls="d-grid gap-2 d-xl-flex",
        ),
        cls="media-gallery-card h-100 border-0 shadow-sm",
        body_cls="d-grid gap-3",
    )


async def _media_gallery_workspace(request: Request, ctx, *, search: str = "", visibility: str = "all", oob: bool = False) -> Div:
    rows = await _gallery_rows(request, ctx, search=search, visibility=visibility)
    filters = FilterBar(
        *hidden_context_inputs(ctx),
        Div(
            filter_field(
                "Search galleries",
                Input(type="search", name="search", value=search, placeholder="Search title, event, or scope", cls="form-control"),
                field_id="media-gallery-search",
            ),
            cls="media-filter-field",
        ),
        Div(
            filter_field(
                "Visibility",
                Select(
                    *[Option(label, value=value, selected=visibility == value) for value, label in MEDIA_VISIBILITY_OPTIONS],
                    name="visibility",
                    cls="form-select",
                ),
                field_id="media-gallery-visibility",
            ),
            cls="media-filter-field",
        ),
        endpoint=ctx.url_for("/communication/media/galleries/list"),
        mode="auto",
        hx_target="#media-galleries-panel",
        hx_swap="outerHTML",
        filters_cls="w-100 gap-3",
        form_cls="d-grid gap-3 mb-3",
    )
    results = (
        Div(*[_media_gallery_card(ctx, row) for row in rows], cls="media-gallery-grid")
        if rows
        else empty_state("images", "No galleries match this view", "Try a different visibility filter or create a new gallery.")
    )
    attrs = {"id": "media-galleries-panel"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#media-galleries-panel"
    return Div(filters, results, **attrs)


def _media_item_mobile_card(ctx, item: dict[str, Any]) -> Div:
    return Div(
        Image(
            src=_media_item_thumb_src(item),
            alt=item["title"],
            fluid=True,
            rounded=True,
            loading="lazy",
            cls="media-item-thumb mb-3",
        ),
        H4(item["title"], cls="h6 fw-semibold mb-1"),
        P(item["gallery_title"], cls="text-muted mb-2"),
        Div(status_badge(item["media_type"]), status_badge(item["gallery_visibility"]), cls="d-flex flex-wrap gap-2 mb-2"),
        P(item["caption"], cls="small text-muted mb-2"),
        P(f"{item['uploaded_at']} - {item['uploaded_by']}", cls="small text-muted mb-3"),
        Div(
            Button(
                "Open gallery",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/communication/media/galleries/{item['gallery_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="w-100",
            ),
            Button(
                "Delete item",
                variant="outline-danger",
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(f"/communication/media/items/{item['item_id']}/delete"),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
                cls="w-100",
            ),
            cls="d-grid gap-2",
        ),
        cls="mobile-count-card",
    )


async def _media_items_workspace(request: Request, ctx, *, search: str = "", media_type: str = "all", oob: bool = False) -> Div:
    items = await _media_items(request, ctx, search=search, media_type=media_type)
    filters = FilterBar(
        *hidden_context_inputs(ctx),
        Div(
            P("Search", cls="small text-muted mb-1"),
            Input(type="search", name="search", value=search, placeholder="Search title, caption, or file label", cls="form-control"),
            cls="media-filter-field",
        ),
        Div(
            P("Item type", cls="small text-muted mb-1"),
            Select(
                *[Option(label, value=value, selected=media_type == value) for value, label in MEDIA_TYPE_OPTIONS],
                name="media_type",
                cls="form-select",
            ),
            cls="media-filter-field",
        ),
        endpoint=ctx.url_for("/communication/media/items/list"),
        mode="auto",
        hx_target="#media-items-panel",
        hx_swap="outerHTML",
        filters_cls="w-100 gap-3",
        form_cls="d-grid gap-3 mb-3",
    )

    if items:
        desktop_rows = []
        mobile_cards = []
        for item in items:
            desktop_rows.append(
                [
                    Div(P(item["title"], cls="fw-semibold mb-1"), P(item["caption"], cls="small text-muted mb-0")),
                    item["gallery_title"],
                    status_badge(item["media_type"]),
                    status_badge(item["gallery_visibility"]),
                    item["uploaded_at"],
                    item["uploaded_by"],
                    Div(
                        Button(
                            "Open gallery",
                            variant="outline-primary",
                            size="md",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#detail-drawer",
                            hx_get=ctx.url_for(f"/communication/media/galleries/{item['gallery_id']}/drawer"),
                            hx_target="#detail-drawer-body",
                            hx_swap="innerHTML",
                        ),
                        Button(
                            "Delete item",
                            variant="outline-danger",
                            size="md",
                            data_bs_toggle="modal",
                            data_bs_target="#confirm-modal",
                            hx_get=ctx.url_for(f"/communication/media/items/{item['item_id']}/delete"),
                            hx_target="#confirm-modal-body",
                            hx_swap="innerHTML",
                        ),
                        cls="d-grid gap-2",
                    ),
                ]
            )
            mobile_cards.append(_media_item_mobile_card(ctx, item))
        results = responsive_table(
            ["Title", "Gallery", "Type", "Visibility", "Uploaded", "By", "Action"],
            desktop_rows,
            mobile_cards,
            results_id="media-items-results",
        )
    else:
        results = empty_state("card-image", "No media items", "No gallery items match the filters.")

    attrs = {"id": "media-items-panel"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#media-items-panel"
    return Div(filters, results, **attrs)


async def _gallery_detail_items(request: Request, ctx, gallery_id: str, *, oob: bool = False) -> Div:
    items = await _media_items(request, ctx, gallery_id=gallery_id)
    attrs = {"id": "media-detail-gallery-items"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#media-detail-gallery-items"
    if not items:
        return Div(
            empty_state("camera", "No gallery items", "No photos or clips are attached to this gallery."),
            **attrs,
        )
    return Div(
        *[
            Div(
                Image(
                    src=_media_item_thumb_src(item),
                    alt=item["title"],
                    fluid=True,
                    rounded=True,
                    loading="lazy",
                    cls="media-detail-thumb",
                ),
                Div(
                    H4(item["title"], cls="h6 fw-semibold mb-1"),
                    P(item["caption"], cls="small text-muted mb-2"),
                    Div(status_badge(item["media_type"]), cls="d-flex flex-wrap gap-2 mb-2"),
                    P(f"{item['uploaded_at']} - {item['uploaded_by']}", cls="small text-muted mb-0"),
                    cls="flex-grow-1",
                ),
                Button(
                    "Delete",
                    variant="outline-danger",
                    size="md",
                    data_bs_toggle="modal",
                    data_bs_target="#confirm-modal",
                    hx_get=ctx.url_for(f"/communication/media/items/{item['item_id']}/delete"),
                    hx_target="#confirm-modal-body",
                    hx_swap="innerHTML",
                ),
                cls="media-detail-item",
            )
            for item in items
        ],
        cls="d-grid gap-3",
        **attrs,
    )


def register_communication_routes(app) -> None:
    @app.get("/communication")
    async def communication_page(request: Request, search: str = "", status: str = "all", meeting: str = ""):
        ctx = build_context(request)
        if ctx.level < 5:
            body = page_stack(section_card(
                "Communication",
                "Weekly communication opens from Level 5 upward.",
                empty_state("megaphone", "Communication unavailable", "This role cannot manage communication records."),
            ))
            return shell_layout(
                ctx,
                request_path=request.url.path,
                active_key="communication",
                title="Communication",
                subtitle="Weekly notes and announcements.",
                primary_action=None,
                content=body,
            )

        body = _communication_loading_shell(
            ctx,
            active_key="notes",
            title="Communication",
            subtitle="Weekly notes and announcements.",
            section_title="Weekly communication list",
            section_note="Filtered weekly notes and announcements.",
            target_url=ctx.url_for("/communication/content", search=search, status=status, meeting=meeting),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="communication",
            title="Communication",
            subtitle="Weekly notes and scoped announcements.",
            primary_action=Div(
                Button("Media Galleries", href=ctx.url_for("/communication/media"), variant="outline-primary", size="md"),
                Button("New Communication", href=ctx.url_for("/communication/new"), variant="primary", size="md"),
                cls="d-grid d-sm-flex gap-2",
            ),
            content=body,
        )

    @app.get("/communication/content")
    async def communication_content(request: Request, search: str = "", status: str = "all", meeting: str = ""):
        ctx = build_context(request)
        summary_div, workspace = await asyncio.gather(
            _communication_summary(request, ctx),
            _communication_workspace(request, ctx, search=search, status=status, meeting=meeting),
        )
        return Div(summary_div, workspace)

    @app.get("/communication/list")
    async def communication_list(request: Request, search: str = "", status: str = "all", meeting: str = ""):
        ctx = build_context(request)
        return await _communication_workspace(request, ctx, search=search, status=status, meeting=meeting)

    @app.get("/communication/{announcement_id}/drawer")
    async def communication_drawer(request: Request, announcement_id: str):
        ctx = build_context(request)
        row = await _announcement_row(request, ctx, announcement_id)
        if row is None:
            return P("Communication entry not found.", cls="text-muted")
        return await _communication_drawer_content(
            ctx,
            row,
            search_filter=str(request.query_params.get("search_filter", "")),
            status_filter=str(request.query_params.get("status_filter", "all")),
            meeting_filter=str(request.query_params.get("meeting_filter", "")),
        )

    @app.get("/communication/new")
    async def new_communication_page(request: Request):
        return await _communication_editor_page(request)

    @app.get("/communication/{announcement_id}/edit")
    async def edit_communication_page(request: Request, announcement_id: str):
        ctx = build_context(request)
        row = await _announcement_row(request, ctx, announcement_id)
        if row is None:
            return RedirectResponse(ctx.url_for("/communication"))
        return await _communication_editor_page(request, row)

    @app.get("/communication/editor/items")
    async def communication_editor_items(request: Request, item_count: int = 3):
        ctx = build_context(request)
        values = _items_values(dict(request.query_params), item_count)
        return _editor_items_block(ctx, item_count, values)

    @app.post("/communication/create")
    async def create_communication(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        if ctx.level < 5:
            return RedirectResponse(ctx.url_for("/communication"), status_code=303)
        if await _communication_live(request):
            await CommunicationService.create_announcement(request, ctx, data)
        else:
            STORE.add_announcement(data, scope_path=ctx.current_scope_path, author_name=ctx.profile.user_name)
        return RedirectResponse(ctx.url_for("/communication"), status_code=303)

    @app.post("/communication/{announcement_id}/update")
    async def update_communication(request: Request, announcement_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = await _announcement_row(request, ctx, announcement_id)
        if ctx.level < 5 or row is None:
            return RedirectResponse(ctx.url_for("/communication"), status_code=303)
        if await _communication_live(request):
            await CommunicationService.update_announcement(request, ctx, announcement_id, data)
        else:
            STORE.update_announcement(announcement_id, data, actor_name=ctx.profile.user_name)
        return RedirectResponse(ctx.url_for("/communication"), status_code=303)

    @app.get("/communication/{announcement_id}/status")
    async def communication_status_confirm(request: Request, announcement_id: str, action: str = "publish", title: str = ""):
        ctx = build_context(request)
        row = await _announcement_row(request, ctx, announcement_id)
        if row is None:
            return P("Communication entry not found.", cls="text-muted")
        title = title or {
            "publish": "Publish note",
            "archive": "Archive note",
            "draft": "Return note to draft",
        }.get(action, "Update note")
        button_variant = "success" if action == "publish" else "warning" if action == "archive" else "primary"
        help_text = {
            "publish": "This note becomes visible as a ready-to-share communication.",
            "archive": "This note leaves the active list but stays available for record purposes.",
            "draft": "This moves the note back to draft so it can be edited again.",
        }.get(action, "Confirm the update for this note.")
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="action", value=action),
            Input(type="hidden", name="search_filter", value=str(request.query_params.get("search_filter", ""))),
            Input(type="hidden", name="status_filter", value=str(request.query_params.get("status_filter", "all"))),
            Input(type="hidden", name="meeting_filter", value=str(request.query_params.get("meeting_filter", ""))),
            H3(title, cls="h5 fw-semibold"),
            P(row["title"], cls="text-muted"),
            P(help_text, cls="small text-muted mb-3"),
            Textarea(name="note", placeholder="Add a short record note if needed", cls="form-control mb-3", rows="4"),
            Button(title, variant=button_variant, type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/communication/{announcement_id}/status"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/communication/{announcement_id}/status")
    async def communication_status_update(request: Request, announcement_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = await _announcement_row(request, ctx, announcement_id)
        if row is None:
            return P("Communication entry not found.", cls="text-muted")
        updated = (
            await CommunicationService.set_announcement_status(request, announcement_id, action=data.get("action", "publish"))
            if await _communication_live(request)
            else STORE.set_announcement_status(
                announcement_id,
                action=data.get("action", "publish"),
                actor_name=ctx.profile.user_name,
                note=data.get("note", ""),
            )
        )
        if updated is None:
            return P("Communication entry not found.", cls="text-muted")
        search_filter = data.get("search_filter", "")
        status_filter = data.get("status_filter", "all")
        meeting_filter = data.get("meeting_filter", "")
        message_map = {
            "publish": "Communication published.",
            "archive": "Communication archived.",
            "draft": "Communication returned to draft.",
        }
        action = data.get("action", "publish")
        variant = "success" if action == "publish" else "warning" if action == "archive" else "info"
        return simple_toast_response(
            content=(
                Div(
                    H3("Communication updated", cls="h5 fw-semibold"),
                    P(message_map.get(action, "Communication updated."), cls="mb-0"),
                ),
                await _communication_summary(request, ctx, oob=True),
                await _communication_workspace(
                    request,
                    ctx,
                    search=search_filter,
                    status=status_filter,
                    meeting=meeting_filter,
                    oob=True,
                ),
                Div(
                    await _communication_drawer_content(
                        ctx,
                        updated,
                        search_filter=search_filter,
                        status_filter=status_filter,
                        meeting_filter=meeting_filter,
                    ),
                    id="detail-drawer-body",
                    hx_swap_oob="innerHTML:#detail-drawer-body",
                ),
            ),
            message=message_map.get(action, "Communication updated."),
            variant=variant,
        )

    @app.get("/communication/media")
    async def communication_media_page(request: Request, gallery_search: str = "", visibility: str = "all", item_search: str = "", media_type: str = "all"):
        ctx = build_context(request)
        if ctx.level < 5:
            body = section_card(
                "Communication Media",
                "Media galleries open from Level 5 upward.",
                empty_state("images", "Communication media unavailable", "This role cannot manage media galleries."),
            )
            return shell_layout(
                ctx,
                request_path=request.url.path,
                active_key="communication",
                title="Communication Media",
                subtitle="Scoped media galleries and uploads.",
                primary_action=None,
                content=body,
            )

        body = _communication_loading_shell(
            ctx,
            active_key="media",
            title="Communication Media",
            subtitle="Media galleries and uploads.",
            section_title="Media galleries",
            section_note="Gallery records and media items.",
            target_url=ctx.url_for("/communication/media/content", gallery_search=gallery_search, visibility=visibility, item_search=item_search, media_type=media_type),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="communication",
            title="Communication Media",
            subtitle="Galleries, uploads, and scoped sharing.",
            primary_action=Div(
                Button("Weekly Notes", href=ctx.url_for("/communication"), variant="outline-primary", size="md"),
                Button(
                    "New Gallery",
                    variant="primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#form-drawer",
                    hx_get=ctx.url_for("/communication/media/galleries/new"),
                    hx_target="#form-drawer-body",
                    hx_swap="innerHTML",
                ),
                cls="d-grid d-sm-flex gap-2",
            ),
            content=body,
        )

    @app.get("/communication/media/content")
    async def communication_media_content(request: Request, gallery_search: str = "", visibility: str = "all", item_search: str = "", media_type: str = "all"):
        ctx = build_context(request)
        gallery_ws, items_ws, summary_div = await asyncio.gather(
            _media_gallery_workspace(request, ctx, search=gallery_search, visibility=visibility),
            _media_items_workspace(request, ctx, search=item_search, media_type=media_type),
            _media_summary(request, ctx),
        )
        tabs = Div(
            Tabs(
                ("media-galleries-tab", "Galleries", True),
                ("media-items-tab", "Recent Uploads"),
                variant="pills",
                cls="mb-3",
            ),
            Div(
                TabPane(gallery_ws, tab_id="media-galleries-tab", active=True),
                TabPane(items_ws, tab_id="media-items-tab"),
                cls="tab-content",
            ),
        )
        return Div(
            summary_div,
            tabs,
        )

    @app.get("/communication/media/galleries/list")
    async def communication_media_galleries_list(request: Request, search: str = "", visibility: str = "all"):
        ctx = build_context(request)
        return await _media_gallery_workspace(request, ctx, search=search, visibility=visibility)

    @app.get("/communication/media/items/list")
    async def communication_media_items_list(request: Request, search: str = "", media_type: str = "all"):
        ctx = build_context(request)
        return await _media_items_workspace(request, ctx, search=search, media_type=media_type)

    @app.get("/communication/media/galleries/new")
    async def communication_media_new_gallery(request: Request):
        ctx = build_context(request)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Create gallery", cls="h5 fw-semibold"),
            P("Enter the gallery name and event details.", cls="text-muted"),
            Input(type="text", name="title", placeholder="Gallery title", cls="form-control mb-3", required=True),
            Div(
                Input(type="text", name="event_name", placeholder="Event or meeting name", cls="form-control", required=True),
                Input(type="date", name="event_date", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Select(
                Option("Select visibility", value=""),
                *[Option(label, value=value) for value, label in MEDIA_VISIBILITY_OPTIONS if value != "all"],
                name="visibility",
                cls="form-select mb-3",
                required=True,
            ),
            Textarea("", name="description", placeholder="Short description of what this gallery contains", cls="form-control mb-3", rows="4"),
            Button("Create gallery", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/communication/media/galleries/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/communication/media/galleries/create")
    async def communication_media_create_gallery(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        gallery = await CommunicationService.create_gallery(request, ctx, data) if await _communication_live(request) else STORE.add_media_gallery(
            data,
            scope_path=ctx.current_scope_path,
            scope_label=ctx.current_scope_label,
            actor_name=ctx.profile.user_name,
        )
        return simple_toast_response(
            content=(
                Div(H3("Gallery created", cls="h5 fw-semibold"), P(f"{gallery['title']} is now available for uploads.", cls="mb-0")),
                await _media_summary(request, ctx, oob=True),
                await _media_gallery_workspace(request, ctx, oob=True),
            ),
            message="Media gallery created.",
            variant="success",
        )

    @app.get("/communication/media/galleries/{gallery_id}/drawer")
    async def communication_media_gallery_drawer(request: Request, gallery_id: str):
        ctx = build_context(request)
        gallery = await _gallery_row(request, ctx, gallery_id)
        if gallery is None:
            return P("Gallery not found.", cls="text-muted")
        return Div(
            H3(gallery["title"], cls="h5 fw-semibold"),
            P(f"{gallery['event_name']} - {gallery['event_date']}", cls="text-muted"),
            Image(src=_gallery_cover_src(gallery), alt=gallery["title"], fluid=True, rounded=True, loading="lazy", cls="media-gallery-cover mb-3"),
            Div(
                status_badge(gallery["visibility"]),
                Span(gallery["scope_label"], cls="small text-muted"),
                Span(f"Created by {gallery['created_by']}", cls="small text-muted"),
                cls="d-flex flex-wrap gap-2 align-items-center mb-3",
            ),
            Div(H4("Description", cls="h6 fw-semibold mb-2"), P(gallery["description"] or "No description added.", cls="mb-0"), cls="drawer-note-box mb-3"),
            Div(
                H4("At a glance", cls="h6 fw-semibold mb-2"),
                Div(
                    Span(f"{gallery['item_count']} items", cls="media-meta-chip"),
                    Span(f"{gallery['photo_count']} photos", cls="media-meta-chip"),
                    Span(f"{gallery['video_count']} videos", cls="media-meta-chip"),
                    cls="d-flex flex-wrap gap-2",
                ),
                cls="drawer-note-box mb-3",
            ),
            Div(
                Button(
                    "Upload item",
                    variant="primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#form-drawer",
                    hx_get=ctx.url_for(f"/communication/media/galleries/{gallery_id}/items/new"),
                    hx_target="#form-drawer-body",
                    hx_swap="innerHTML",
                ),
                Button(
                    "Delete gallery",
                    variant="outline-danger",
                    size="md",
                    data_bs_toggle="modal",
                    data_bs_target="#confirm-modal",
                    hx_get=ctx.url_for(f"/communication/media/galleries/{gallery_id}/delete"),
                    hx_target="#confirm-modal-body",
                    hx_swap="innerHTML",
                ),
                cls="d-grid gap-2 d-md-flex mb-3",
            ),
            Div(H4("Gallery items", cls="h6 fw-semibold mb-3"), _gallery_detail_items(request, ctx, gallery_id)),
        )

    @app.get("/communication/media/galleries/{gallery_id}/items/new")
    async def communication_media_new_item(request: Request, gallery_id: str):
        ctx = build_context(request)
        gallery = await _gallery_row(request, ctx, gallery_id)
        if gallery is None:
            return P("Gallery not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Upload media item", cls="h5 fw-semibold"),
            P(f"{gallery['title']} - {gallery['event_name']}", cls="text-muted"),
            Input(type="text", name="title", placeholder="Item title", cls="form-control mb-3", required=True),
            Div(
                Select(
                    Option("Select type", value=""),
                    *[Option(label, value=value) for value, label in MEDIA_TYPE_OPTIONS if value != "all"],
                    name="media_type",
                    cls="form-select",
                    required=True,
                ),
                Input(type="text", name="file_label", placeholder="File label or storage note", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Input(type="text", name="duration", placeholder="Video duration, if any", cls="form-control mb-3"),
            Textarea("", name="caption", placeholder="Short caption", cls="form-control mb-3", rows="4"),
            Button("Save item", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/communication/media/galleries/{gallery_id}/items/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/communication/media/galleries/{gallery_id}/items/create")
    async def communication_media_create_item(request: Request, gallery_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        gallery = await _gallery_row(request, ctx, gallery_id)
        if gallery is None:
            return P("Gallery not found.", cls="text-muted")
        item = await CommunicationService.create_media_item(request, ctx, gallery_id, data) if await _communication_live(request) else STORE.add_media_item(gallery_id, data, actor_name=ctx.profile.user_name)
        if item is None:
            return P("Unable to save media item.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(H3("Media item saved", cls="h5 fw-semibold"), P(f"{item['title']} was added to {item['gallery_title']}.", cls="mb-0")),
                await _media_summary(request, ctx, oob=True),
                await _media_gallery_workspace(request, ctx, oob=True),
                await _media_items_workspace(request, ctx, oob=True),
                _gallery_detail_items(request, ctx, gallery_id, oob=True),
            ),
            message="Media item saved.",
            variant="success",
        )

    @app.get("/communication/media/galleries/{gallery_id}/delete")
    async def communication_media_delete_gallery_confirm(request: Request, gallery_id: str):
        ctx = build_context(request)
        gallery = await _gallery_row(request, ctx, gallery_id)
        if gallery is None:
            return P("Gallery not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Delete gallery", cls="h5 fw-semibold"),
            P(gallery["title"], cls="text-muted"),
            P("This will remove the gallery and every media item inside it.", cls="small text-muted mb-3"),
            Button("Delete gallery", variant="danger", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/communication/media/galleries/{gallery_id}/delete"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/communication/media/galleries/{gallery_id}/delete")
    async def communication_media_delete_gallery(request: Request, gallery_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        gallery = await _gallery_row(request, ctx, gallery_id)
        if gallery is None:
            return P("Gallery not found.", cls="text-muted")
        removed = await CommunicationService.delete_gallery(request, ctx, gallery_id) if await _communication_live(request) else STORE.delete_media_gallery(gallery_id, actor_name=ctx.profile.user_name)
        if removed is None:
            return P("Gallery not found.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(H3("Gallery deleted", cls="h5 fw-semibold"), P(f"{removed['title']} and its items were removed.", cls="mb-0")),
                await _media_summary(request, ctx, oob=True),
                await _media_gallery_workspace(request, ctx, oob=True),
                await _media_items_workspace(request, ctx, oob=True),
                Div(P("Select a record.", cls="text-muted"), id="detail-drawer-body", hx_swap_oob="innerHTML:#detail-drawer-body"),
            ),
            message="Gallery deleted.",
            variant="warning",
        )

    @app.get("/communication/media/items/{item_id}/delete")
    async def communication_media_delete_item_confirm(request: Request, item_id: str):
        ctx = build_context(request)
        item = await _media_item_row(request, ctx, item_id)
        if item is None:
            return P("Media item not found.", cls="text-muted")
        gallery = await _gallery_row(request, ctx, item["gallery_id"])
        gallery_label = gallery["title"] if gallery else "Unknown gallery"
        return Form(
            *hidden_context_inputs(ctx),
            H3("Delete media item", cls="h5 fw-semibold"),
            P(f"{item['title']} - {gallery_label}", cls="text-muted"),
            P("This removes the recorded item from the gallery.", cls="small text-muted mb-3"),
            Button("Delete item", variant="danger", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/communication/media/items/{item_id}/delete"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/communication/media/items/{item_id}/delete")
    async def communication_media_delete_item(request: Request, item_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        item = await _media_item_row(request, ctx, item_id)
        if item is None:
            return P("Media item not found.", cls="text-muted")
        gallery_id = item["gallery_id"]
        removed = await CommunicationService.delete_media_item(request, ctx, item_id) if await _communication_live(request) else STORE.delete_media_item(item_id, actor_name=ctx.profile.user_name)
        if removed is None:
            return P("Media item not found.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(H3("Media item deleted", cls="h5 fw-semibold"), P(f"{removed['title']} was removed from the gallery.", cls="mb-0")),
                await _media_summary(request, ctx, oob=True),
                await _media_gallery_workspace(request, ctx, oob=True),
                await _media_items_workspace(request, ctx, oob=True),
                _gallery_detail_items(request, ctx, gallery_id, oob=True),
            ),
            message="Media item deleted.",
            variant="warning",
        )
