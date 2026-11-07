from app.frontend.dclm_admin.routes.analytics_dashboard import _review_attention_note
from fasthtml.common import to_xml


def test_location_persona_sees_approver_note_not_a_review_queue_error():
    panel = _review_attention_note("Location")
    assert "Reports from your location are approved by your Group Pastor." in str(panel)


def test_lazy_location_note_has_expected_out_of_band_target():
    panel = _review_attention_note("Location", panel_id="analytics-attention-panel")
    html = to_xml(panel)
    assert 'id="analytics-attention-panel"' in html
    assert "Reports from your location are approved by your Group Pastor." in html


def test_group_persona_is_told_region_pastor_approves_location_reports():
    assert "Region Pastor" in str(_review_attention_note("Group"))


def test_region_persona_is_told_state_overseer_approves_group_reports():
    assert "State Overseer" in str(_review_attention_note("Region"))


def test_state_persona_is_told_state_reports_are_auto_accepted():
    assert "auto-accepted" in str(_review_attention_note("State"))
