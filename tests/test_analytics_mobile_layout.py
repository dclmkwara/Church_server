from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from fasthtml.common import to_xml

from app.frontend.dclm_admin.routes.analytics_dashboard import _attention_panel, _children_table


ROOT = Path(__file__).resolve().parents[1]


def _ctx(path: str, kind: str):
    def url_for(url, **params):
        from urllib.parse import urlencode

        return f"{url}?{urlencode(params)}" if params else url

    return SimpleNamespace(
        current_scope_path=path,
        current_scope_kind=kind,
        current_scope_label=f"{kind} name",
        current_scope_level={"State": 5, "Region": 4, "Group": 3, "Location": 2}[kind],
        profile=SimpleNamespace(root_path=path, key="test"),
        query_extras={"scope_path": path, "home_path": path, "period": "month", "weeks": "8", "include_pending": "false"},
        url_for=url_for,
        has_permission=lambda _permission: True,
    )


def test_mobile_dashboard_row_is_a_keyboard_link_and_preserves_view_parameters():
    ctx = _ctx("org.234.kw", "State")
    child_path = "org.234.kw.region"
    html = to_xml(
        _children_table(
            [{"name": "Ilorin Region", "path": child_path}],
            [{"overview": {"n_expected": 5, "n_received": 3, "n_counted": 2, "total": 400, "coverage": {"missing": 2}}}],
            "State",
            ctx,
        )
    )
    assert 'data-dashboard-href="/dashboard?' in html
    assert "analytics-child-link" in html
    assert "Ilorin Region" in html
    href = re.search(r'<a href="([^"]+)"[^>]*analytics-child-link', html).group(1)
    href = href.replace("&amp;", "&")
    query = parse_qs(urlsplit(href).query)
    assert query["scope_path"] == [child_path]
    assert query["period"] == ["month"]
    assert query["weeks"] == ["8"]
    assert query["include_pending"] == ["false"]


def test_attention_rolls_pending_and_missing_up_to_the_child_scope():
    state_path = "org.234.kw"
    region_path = f"{state_path}.region"
    location_a = f"{region_path}.group.loc-a"
    location_b = f"{region_path}.group.loc-b"
    html = to_xml(
        _attention_panel(
            {},
            [
                {"location_id": "a", "program_scope_path": location_a, "age_hours": 12, "program_type": "Sunday Worship"},
                {"location_id": "b", "program_scope_path": location_b, "age_hours": 28, "program_type": "Sunday Worship"},
            ],
            [{"name": "Ilorin Region", "path": region_path}],
            [{"overview": {"n_expected": 4, "n_received": 3, "coverage": {"missing": 1}}}],
            {"missing_locations": [{"location_id": "c", "path": f"{region_path}.group.loc-c"}]},
            _ctx(state_path, "State"),
            __import__("datetime").date(2026, 11, 8),
            "sunday-worship",
        )
    )
    assert "Ilorin Region: 1 of 4 locations did not report" in html
    assert "Ilorin Region: 2 pending count group(s)" in html
    assert "12h" not in html
    assert "Oldest waiting 28 hours · 24+ hours" in html
    assert "Oldest waiting 2 days" not in html
    assert "analytics-attention-copy" in html
    assert "analytics-attention-meta" in html
    assert "loc-a" not in html and "loc-b" not in html


def test_mobile_css_reflows_analytics_and_does_not_clip_at_the_page_root():
    admin_css = (ROOT / "app/frontend/dclm_admin/assets/css/admin.css").read_text(encoding="utf-8")
    analytics_css = (ROOT / "app/frontend/dclm_admin/assets/css/analytics-dashboard.css").read_text(encoding="utf-8")
    assert "overflow-x: clip !important" not in admin_css
    assert "@media (max-width: 640px)" in analytics_css
    assert ".analytics-child-table-wrap .analytics-table tr.analytics-row" in analytics_css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in analytics_css
    assert "scroll-padding-top:76px" in analytics_css
    assert "padding-bottom:72px!important" in analytics_css
    assert "grid-template-columns:minmax(0,1fr)!important" in analytics_css
    assert "font-size:34px" in analytics_css
