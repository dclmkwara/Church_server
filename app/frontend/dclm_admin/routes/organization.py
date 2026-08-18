from __future__ import annotations

import asyncio

from fasthtml.common import A, Div, Form, H3, H4, Input, P, Select, Option, Textarea
from starlette.requests import Request
from starlette.responses import RedirectResponse
from faststrap import PlaceholderCard, Spinner

from ..backend import BackendClientError
from ..auth_context import build_context
from ..communication import OrganizationService
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, primary_button, shell_layout
from ..components.ui import empty_state, filter_field, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE, in_scope


ORG_TABS = [
    ("hierarchy", "Hierarchy Explorer", "/organization/hierarchy"),
    ("locations", "Locations & Profiles", "/organization/locations"),
]


def _organization_nav(ctx, active: str):
    return Div(
        *[
            A(
                label,
                href=ctx.url_for(path),
                cls=f"btn {'btn-primary' if key == active else 'btn-outline-primary'} admin-inline-btn",
                **({"aria_current": "page"} if key == active else {}),
            )
            for key, label, path in ORG_TABS
        ],
        cls="workspace-tab-strip mb-4",
    )


async def _tree_list(ctx, focus_path: str):
    request = getattr(ctx, "_request", None)
    rows = await OrganizationService.list_hierarchy_tree(request, ctx)
    if not rows:
        return empty_state("diagram-3", "No hierarchy units", "No organization units are available.")
    return Div(
        *[
            A(
                Div(
                    P(row["label"], cls="fw-semibold text-dark mb-1"),
                    P(row.get("display_id") or row["kind"].replace("_", " ").title(), cls="small text-muted mb-0"),
                    cls="d-flex flex-column",
                ),
                href="#",
                hx_get=ctx.url_for("/organization/hierarchy/panel", focus_path=row["path"]),
                hx_target="#hierarchy-panel",
                hx_swap="outerHTML",
                cls=f"tree-node-link {'active' if row['path'] == focus_path else ''}",
                style=f"--tree-depth:{max(row['depth'], 0)};",
            )
            for row in rows
        ],
        cls="tree-list",
    )


def _child_action(ctx, row):
    if row["kind"] == "location":
        return A("Open profile", href=ctx.url_for(f"/organization/locations/{row['location_key']}"), cls="btn btn-outline-primary")
    if row["kind"] == "fellowship":
        return A("Open fellowship", href=ctx.url_for(f"/fellowship/{row['entity_id']}"), cls="btn btn-outline-primary")
    return A(
        "Inspect",
        href="#",
        hx_get=ctx.url_for("/organization/hierarchy/panel", focus_path=row["path"]),
        hx_target="#hierarchy-panel",
        hx_swap="outerHTML",
        cls="btn btn-outline-primary",
    )


async def _hierarchy_panel(ctx, focus_path: str | None, *, oob: bool = False):
    attrs = {"id": "hierarchy-panel"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#hierarchy-panel"

    if ctx.level < 4:
        return Div(
            empty_state(
                "geo-alt",
                "Hierarchy explorer opens at group level",
                "Open the location profile below.",
                action=A("Open my location", href=ctx.url_for(f"/organization/locations/{ctx.current_scope_path.split('.')[-1]}"), cls="btn btn-primary"),
            ),
            **attrs,
        )

    target_path = focus_path or ctx.current_scope_path
    request = getattr(ctx, "_request", None)
    node = await OrganizationService.get_hierarchy_node(request, ctx, target_path)
    if node is None:
        return Div(empty_state("diagram-3", "Unit not found", "Choose another unit from the tree."), **attrs)

    children = await OrganizationService.list_hierarchy_children(request, ctx, node["path"])
    if children:
        desktop_rows = []
        mobile_cards = []
        for child in children:
            action = _child_action(ctx, child)
            desktop_rows.append(
                [
                    child["label"],
                    child.get("display_id") or child["kind"].replace("_", " ").title(),
                    child["kind"].replace("_", " ").title(),
                    child["children_count"],
                    child["location_count"],
                    action,
                ]
            )
            mobile_cards.append(
                Div(
                    H4(child["label"], cls="h6 fw-semibold mb-1"),
                    P(child.get("display_id") or child["kind"].replace("_", " ").title(), cls="text-muted mb-2"),
                    P(f"Child units: {child['children_count']} • Locations: {child['location_count']}", cls="small text-muted mb-3"),
                    action,
                    cls="mobile-worker-card",
                )
            )
        children_view = responsive_table(
            ["Unit", "Scope ID", "Type", "Child Units", "Locations", "Action"],
            desktop_rows,
            mobile_cards,
            results_id="hierarchy-children-table",
        )
    else:
        children_view = empty_state("check2-circle", "No lower units here", "This unit has no lower units.")

    action = None
    if node["kind"] == "location" and node["location_key"]:
        action = A("Open location profile", href=ctx.url_for(f"/organization/locations/{node['location_key']}"), cls="btn btn-outline-primary admin-inline-btn")
    elif node["kind"] == "fellowship":
        action = A("Open fellowship", href=ctx.url_for(f"/fellowship/{node['entity_id']}"), cls="btn btn-outline-primary admin-inline-btn")

    return Div(
        Div(
            stat_card("Current Unit", node["label"], node["kind"].replace("_", " ").title(), "diagram-3", tone="primary"),
            stat_card("Lower Units", str(node["children_count"]), "Visible children under this unit", "collection", tone="info"),
            stat_card("Locations", str(node["location_count"]), "Locations connected to this unit", "geo-alt", tone="success"),
            stat_card("Members", str(node["member_count"]), "Members in this branch", "people", tone="warning"),
            cls="counts-stat-grid",
        ),
        section_card(
            "Unit detail",
            "Browse this unit and its lower levels.",
            Div(
                Div(P("Unit name", cls="small text-muted mb-1"), P(node["label"], cls="fw-semibold mb-0")),
                Div(P("Scope ID", cls="small text-muted mb-1"), P(node.get("display_id") or "Not available", cls="fw-semibold mb-0")),
                Div(P("Unit type", cls="small text-muted mb-1"), P(node["kind"].replace("_", " ").title(), cls="fw-semibold mb-0")),
                Div(P("Visible workers", cls="small text-muted mb-1"), P(str(node["worker_count"]), cls="fw-semibold mb-0")),
                Div(P("Connected fellowships", cls="small text-muted mb-1"), P(str(node["fellowship_count"]), cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            action=action,
        ),
        section_card(
            "Drill into lower units",
            "Lower units for this branch.",
            children_view,
        ),
        **attrs,
    )


async def _location_panel(ctx, location_key: str, *, oob: bool = False):
    attrs = {"id": "location-profile-panel"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#location-profile-panel"
    request = getattr(ctx, "_request", None)
    profile = await OrganizationService.get_location_profile(request, ctx, location_key)
    if profile is None:
        return Div(empty_state("geo-alt", "Location not found", "Choose another location from the list."), **attrs)
    summary = await OrganizationService.location_profile_summary(request, ctx, location_key)
    fellowships = (
        [
            {
                "fellowship_id": row["entity_id"],
                "name": row["label"],
            }
            for row in await OrganizationService.list_hierarchy_tree(request, ctx)
            if row["kind"] == "fellowship" and row["path"].startswith(f"{profile['path']}.")
        ]
        if request and await OrganizationService.live_enabled(request)
        else STORE.list_fellowships(profile["path"])
    )
    fellowship_links = (
        Div(
            *[
                A(row["name"], href=ctx.url_for(f"/fellowship/{row['fellowship_id']}"), cls="btn btn-outline-primary admin-inline-btn")
                for row in fellowships
            ],
            cls="d-flex flex-wrap gap-2",
        )
        if fellowships
        else P("No fellowship records connected.", cls="text-muted mb-0")
    )
    return Div(
        Div(
            stat_card("Workers", str(summary["worker_count"]), "Workers in this location", "people", tone="primary"),
            stat_card("Members", str(summary["member_count"]), "Members linked to this location", "person-vcard", tone="success"),
            stat_card("Fellowships", str(summary["fellowship_count"]), "Fellowship groups under this location", "house-heart", tone="warning"),
            stat_card("Latest Count", str(summary["latest_count"]), "Most recent reported attendance count", "bar-chart", tone="info"),
            cls="counts-stat-grid",
        ),
        section_card(
            "Location profile",
            "Plain-language location details and leadership information.",
            Div(
                Div(P("Church type", cls="small text-muted mb-1"), P(profile["church_type"], cls="fw-semibold mb-0")),
                Div(P("Scope ID", cls="small text-muted mb-1"), P(profile.get("display_id") or "Not available", cls="fw-semibold mb-0")),
                Div(P("Status", cls="small text-muted mb-1"), status_badge(profile["status"])),
                Div(P("Address", cls="small text-muted mb-1"), P(profile["address"], cls="fw-semibold mb-0")),
                Div(P("Pastor", cls="small text-muted mb-1"), P(profile["pastor_name"], cls="fw-semibold mb-0")),
                Div(P("Assistant", cls="small text-muted mb-1"), P(profile["assistant_name"], cls="fw-semibold mb-0")),
                Div(P("Phone", cls="small text-muted mb-1"), P(profile["phone"], cls="fw-semibold mb-0")),
                Div(P("Parent group", cls="small text-muted mb-1"), P(profile["group"], cls="fw-semibold mb-0")),
                Div(P("Parent region", cls="small text-muted mb-1"), P(profile["region"], cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
        ),
        section_card(
            "Connected fellowship units",
            "Open fellowships linked to this location.",
            fellowship_links,
        ),
        **attrs,
    )


async def _locations_table(ctx, *, search: str = "", status: str = "", church_type: str = "", oob: bool = False):
    request = getattr(ctx, "_request", None)
    rows = await OrganizationService.list_location_profiles(request, ctx, search=search, status=status, church_type=church_type)
    attrs = {"id": "locations-results"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#locations-results"
    if not rows:
        return Div(empty_state("geo-alt", "No locations match this filter", "Try another search or clear the filters."), **attrs)

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                Div(P(row["location"], cls="fw-semibold mb-1"), P(row.get("display_id") or row["address"], cls="small text-muted mb-0")),
                row["church_type"],
                Div(P(row["pastor_name"], cls="mb-1"), P(row["assistant_name"], cls="small text-muted mb-0")),
                status_badge(row["status"]),
                Div(P(f"Workers: {row['worker_count']}", cls="small mb-1"), P(f"Fellowships: {row['fellowship_count']}", cls="small text-muted mb-0")),
                A("Open profile", href=ctx.url_for(f"/organization/locations/{row['location_key']}"), cls="btn btn-outline-primary"),
            ]
        )
        mobile_cards.append(
            Div(
                H4(row["location"], cls="h6 fw-semibold mb-1"),
                P(row.get("display_id") or row["address"], cls="text-muted mb-2"),
                Div(status_badge(row["status"]), cls="d-flex flex-wrap gap-2 mb-2"),
                P(f"{row['church_type']} • Pastor: {row['pastor_name']}", cls="small text-muted mb-3"),
                A("Open profile", href=ctx.url_for(f"/organization/locations/{row['location_key']}"), cls="btn btn-outline-primary"),
                cls="mobile-worker-card",
            )
        )
    return Div(
        responsive_table(
            ["Location", "Type", "Leadership", "Status", "Connected Data", "Action"],
            desktop_rows,
            mobile_cards,
            results_id="locations-table",
        ),
        **attrs,
    )


def _organization_loading_shell(ctx, *, heading: str, target_path: str, **params: str) -> Div:
    return Div(
        Div(
            H3(heading, cls="h5 fw-semibold mb-3"),
            Div(
                Spinner(variant="primary", size="md", label="Loading organization"),
                P(
                    "Loading organization records.",
                    cls="text-muted mb-0",
                ),
                cls="d-flex align-items-center gap-3 py-2",
            ),
        ),
        Div(PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"), cls="mb-4"),
        Div(PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"), cls="mb-4"),
        id="organization-content",
        hx_get=ctx.url_for(target_path, **params),
        hx_trigger="load",
        hx_swap="innerHTML",
    )


async def _hierarchy_page_content(ctx, default_focus: str) -> Div:
    tree_div, panel_div = await asyncio.gather(
        _tree_list(ctx, default_focus),
        _hierarchy_panel(ctx, default_focus),
    )
    return page_stack(
        page_intro(
            "Organization",
            "Inspect the church structure in simple terms, then move into the next lower unit without losing your place.",
            scope_label=ctx.current_scope_label,
            scope_kind=ctx.current_scope_kind,
        ),
        _organization_nav(ctx, "hierarchy"),
        section_card(
            "Hierarchy explorer",
            "Organization tree and unit details.",
            Div(
                Div(tree_div, cls="organization-side-card"),
                Div(panel_div, cls="organization-side-card"),
                cls="organization-two-up",
            ),
        ),
    )


async def _locations_page_content(ctx, *, search: str = "", status: str = "", church_type: str = "") -> Div:
    request = getattr(ctx, "_request", None)
    live = await OrganizationService.live_enabled(request)
    summary_rows, table_div = await asyncio.gather(
        OrganizationService.list_location_profiles(request, ctx),
        _locations_table(ctx, search=search, status=status, church_type=church_type),
    )
    return page_stack(
        page_intro(
            "Organization",
            "Open location profiles, check connected data summaries, and keep profile editing straightforward on phone or desktop.",
            scope_label=ctx.current_scope_label,
            scope_kind=ctx.current_scope_kind,
        ),
        _organization_nav(ctx, "locations"),
        section_card(
            "Locations & profiles",
            f"{len(summary_rows)} location profile(s).",
            Form(
                *hidden_context_inputs(ctx),
                filter_field(
                    "Search locations",
                    Input(type="search", name="search", value=search, placeholder="Search location, DCM ID, address, pastor, or region", cls="form-control"),
                    field_id="organization-location-search",
                ),
                filter_field(
                    "Status",
                    Select(
                        Option("All status", value=""),
                        Option("Profiled", value="profiled", selected=status == "profiled") if live else Option("Active", value="active", selected=status == "active"),
                        Option("Needs profile", value="needs_profile", selected=status == "needs_profile") if live else Option("Inactive", value="inactive", selected=status == "inactive"),
                        name="status",
                        cls="form-select",
                    ),
                    field_id="organization-location-status",
                ),
                filter_field(
                    "Church type",
                    Select(
                        Option("All church types", value=""),
                        Option("DLBC", value="DLBC", selected=church_type == "DLBC"),
                        Option("DLCF", value="DLCF", selected=church_type == "DLCF"),
                        name="church_type",
                        cls="form-select",
                    ),
                    field_id="organization-location-type",
                ),
                hx_get=ctx.url_for("/organization/locations/list"),
                hx_target="#locations-results",
                hx_swap="outerHTML",
                hx_trigger="keyup changed delay:350ms from:input, change from:select",
                cls="admin-filter-grid",
            ),
            table_div,
        ),
    )


async def _location_profile_page_content(ctx, location_key: str) -> Div:
    request = getattr(ctx, "_request", None)
    profile = await OrganizationService.get_location_profile(request, ctx, location_key)
    if profile is None:
        return Div(empty_state("geo-alt", "Location not found", "Choose another location from the list."))
    panel = await _location_panel(ctx, location_key)
    return page_stack(
        A("Back to locations", href=ctx.url_for("/organization/locations"), cls="btn btn-outline-primary admin-inline-btn mb-3"),
        page_intro(
            profile["location"],
            f"{profile['address']} • {profile['group']} • {profile['region']}",
            scope_label=ctx.current_scope_label,
            scope_kind=ctx.current_scope_kind,
        ),
        _organization_nav(ctx, "locations"),
        panel,
    )


def register_organization_routes(app) -> None:
    @app.get("/organization")
    async def organization_root(request: Request):
        ctx = build_context(request)
        if ctx.level < 4:
            return RedirectResponse(ctx.url_for(f"/organization/locations/{ctx.current_scope_path.split('.')[-1]}"))
        return RedirectResponse(ctx.url_for("/organization/hierarchy"))

    @app.get("/organization/hierarchy")
    async def hierarchy_page(request: Request, focus_path: str = ""):
        ctx = build_context(request)
        object.__setattr__(ctx, "_request", request)
        default_focus = focus_path or ctx.current_scope_path
        body = page_stack(
            _organization_loading_shell(
                ctx,
                heading="Hierarchy explorer",
                target_path="/organization/hierarchy/content",
                focus_path=default_focus,
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="organization",
            title="Hierarchy Explorer",
            subtitle="Church structure and drill-down visibility.",
            primary_action=None,
            content=body,
        )

    @app.get("/organization/hierarchy/content")
    async def hierarchy_content(request: Request, focus_path: str = ""):
        ctx = build_context(request)
        object.__setattr__(ctx, "_request", request)
        default_focus = focus_path or ctx.current_scope_path
        return await _hierarchy_page_content(ctx, default_focus)

    @app.get("/organization/hierarchy/panel")
    async def hierarchy_panel(request: Request, focus_path: str = ""):
        ctx = build_context(request)
        object.__setattr__(ctx, "_request", request)
        return await _hierarchy_panel(ctx, focus_path)

    @app.get("/organization/locations")
    async def locations_page(request: Request, search: str = "", status: str = "", church_type: str = ""):
        ctx = build_context(request)
        object.__setattr__(ctx, "_request", request)
        body = page_stack(
            _organization_loading_shell(
                ctx,
                heading="Locations & profiles",
                target_path="/organization/locations/content",
                search=search,
                status=status,
                church_type=church_type,
            ),
        )
        primary = None
        if ctx.level < 4:
            primary = primary_button("Open My Location", href=ctx.url_for(f"/organization/locations/{ctx.current_scope_path.split('.')[-1]}"))
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="organization",
            title="Locations & Profiles",
            subtitle="Location metadata and connected summaries.",
            primary_action=primary,
            content=body,
        )

    @app.get("/organization/locations/content")
    async def locations_content(request: Request, search: str = "", status: str = "", church_type: str = ""):
        ctx = build_context(request)
        object.__setattr__(ctx, "_request", request)
        return await _locations_page_content(ctx, search=search, status=status, church_type=church_type)

    @app.get("/organization/locations/list")
    async def locations_list(request: Request, search: str = "", status: str = "", church_type: str = ""):
        ctx = build_context(request)
        object.__setattr__(ctx, "_request", request)
        return await _locations_table(ctx, search=search, status=status, church_type=church_type)

    @app.get("/organization/locations/{location_key}")
    async def location_profile_page(request: Request, location_key: str):
        ctx = build_context(request)
        object.__setattr__(ctx, "_request", request)
        profile = await OrganizationService.get_location_profile(request, ctx, location_key)
        if profile is None or (not await OrganizationService.live_enabled(request) and not in_scope(profile["path"], ctx.current_scope_path)):
            return RedirectResponse(ctx.url_for("/organization/locations"))
        if await OrganizationService.live_enabled(request):
            return shell_layout(
                ctx,
                request_path=request.url.path,
                active_key="organization",
                title=profile["location"],
                subtitle="Location profile and connected data.",
                primary_action=primary_button(
                    "Edit Profile",
                    href="#",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#form-drawer",
                    hx_get=ctx.url_for(f"/organization/locations/{location_key}/edit"),
                    hx_target="#form-drawer-body",
                    hx_swap="innerHTML",
                ),
                content=page_stack(
                    _organization_loading_shell(
                        ctx,
                        heading=profile["location"],
                        target_path=f"/organization/locations/{location_key}/content",
                    ),
                ),
            )
        body = page_stack(
            A("Back to locations", href=ctx.url_for("/organization/locations"), cls="btn btn-outline-primary admin-inline-btn mb-3"),
            page_intro(
                profile["location"],
                f"{profile['address']} • {profile['group']} • {profile['region']}",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            _organization_nav(ctx, "locations"),
            await _location_panel(ctx, location_key),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="organization",
            title=profile["location"],
            subtitle="Location profile and connected data.",
            primary_action=primary_button(
                "Edit Profile",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for(f"/organization/locations/{location_key}/edit"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
        )

    @app.get("/organization/locations/{location_key}/content")
    async def location_profile_content(request: Request, location_key: str):
        ctx = build_context(request)
        object.__setattr__(ctx, "_request", request)
        profile = await OrganizationService.get_location_profile(request, ctx, location_key)
        if profile is None or (not await OrganizationService.live_enabled(request) and not in_scope(profile["path"], ctx.current_scope_path)):
            return Div(empty_state("geo-alt", "Location not found", "Choose another location from the list."))
        return await _location_profile_page_content(ctx, location_key)

    @app.get("/organization/locations/{location_key}/edit")
    async def edit_location_form(request: Request, location_key: str):
        ctx = build_context(request)
        profile = await OrganizationService.get_location_profile(request, ctx, location_key)
        if profile is None or (not await OrganizationService.live_enabled(request) and not in_scope(profile["path"], ctx.current_scope_path)):
            return P("Location not found.", cls="text-muted")
        if await OrganizationService.live_enabled(request):
            return Form(
                *hidden_context_inputs(ctx),
                H3("Edit location profile", cls="h5 fw-semibold"),
                P("Backend mode uses the real location and location-profile fields only.", cls="text-muted"),
                Input(type="text", name="location_name", value=profile["location"], cls="form-control mb-3", placeholder="Location name"),
                Select(
                    Option("DLBC", value="DLBC", selected=profile["church_type"] == "DLBC"),
                    Option("DLCF", value="DLCF", selected=profile["church_type"] == "DLCF"),
                    Option("DLSO", value="DLSO", selected=profile["church_type"] == "DLSO"),
                    name="church_type",
                    cls="form-select mb-3",
                ),
                Input(type="text", name="address", value=profile["address"], cls="form-control mb-3", placeholder="Short address"),
                Input(type="text", name="associate_cord", value=profile.get("associate_cord", ""), cls="form-control mb-3", placeholder="Associate coordinator"),
                Input(type="date", name="founded_date", value=profile.get("founded_date", ""), cls="form-control mb-3"),
                Input(type="text", name="founder_name", value=profile.get("founder_name", ""), cls="form-control mb-3", placeholder="Founder or historical lead"),
                Input(type="text", name="full_address", value=profile.get("full_address", ""), cls="form-control mb-3", placeholder="Full address"),
                Input(type="text", name="landmark", value=profile.get("landmark", ""), cls="form-control mb-3", placeholder="Nearest landmark"),
                Input(type="url", name="google_maps_url", value=profile.get("google_maps_url", ""), cls="form-control mb-3", placeholder="Google Maps URL"),
                Input(type="url", name="cover_image_url", value=profile.get("cover_image_url", ""), cls="form-control mb-3", placeholder="Cover image URL"),
                Textarea(name="history", cls="form-control mb-3", rows="4", placeholder="Church history or branch story"),
                A("Save profile", href="#", cls="btn btn-success w-100", hx_post=ctx.url_for(f"/organization/locations/{location_key}/update"), hx_include="closest form", hx_target="#form-drawer-body", hx_swap="innerHTML"),
            )
        return Form(
            *hidden_context_inputs(ctx),
            H3("Edit location profile", cls="h5 fw-semibold"),
            P("Update simple profile fields without exposing technical hierarchy details.", cls="text-muted"),
            Select(
                Option("DLBC", value="DLBC", selected=profile["church_type"] == "DLBC"),
                Option("DLCF", value="DLCF", selected=profile["church_type"] == "DLCF"),
                name="church_type",
                cls="form-select mb-3",
            ),
            Select(
                Option("Active", value="active", selected=profile["status"] == "active"),
                Option("Inactive", value="inactive", selected=profile["status"] == "inactive"),
                name="status",
                cls="form-select mb-3",
            ),
            Input(type="text", name="address", value=profile["address"], cls="form-control mb-3", placeholder="Address"),
            Div(
                Input(type="text", name="pastor_name", value=profile["pastor_name"], cls="form-control", placeholder="Pastor in charge"),
                Input(type="text", name="assistant_name", value=profile["assistant_name"], cls="form-control", placeholder="Assistant leader"),
                cls="drawer-two-up mb-3",
            ),
            Input(type="text", name="phone", value=profile["phone"], cls="form-control mb-3", placeholder="Phone"),
            Input(type="hidden", name="location_key", value=location_key),
            A("Save profile", href="#", cls="btn btn-success w-100", hx_post=ctx.url_for(f"/organization/locations/{location_key}/update"), hx_include="closest form", hx_target="#form-drawer-body", hx_swap="innerHTML"),
        )

    @app.post("/organization/locations/{location_key}/update")
    async def update_location_profile(request: Request, location_key: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        object.__setattr__(ctx, "_request", request)
        if await OrganizationService.live_enabled(request):
            try:
                profile = await OrganizationService.update_location_profile(request, location_key, data)
            except BackendClientError as exc:
                return P(str(exc), cls="text-danger small")
        else:
            profile = STORE.update_location_profile(location_key, data)
        if profile is None or (not await OrganizationService.live_enabled(request) and not in_scope(profile["path"], ctx.current_scope_path)):
            return P("Location not found.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(H3("Profile updated", cls="h5 fw-semibold"), P(f"{profile['location']} profile has been updated.", cls="mb-0")),
                _location_panel(ctx, location_key, oob=True),
            ),
            message="Location profile updated.",
            variant="success",
        )
