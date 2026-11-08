from fasthtml.common import to_xml

from app.frontend.dclm_admin.routes.reports import _reports_unavailable_panel


def test_reports_service_failure_renders_inline_error_not_empty_data_state():
    rendered = to_xml(_reports_unavailable_panel())

    assert "Reports are unavailable" in rendered
    assert "role=\"alert\"" in rendered
    assert "No reports" not in rendered
