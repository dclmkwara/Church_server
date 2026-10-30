import pytest
from app.frontend.dclm_admin.components.feedback import (
    simple_toast_response,
    toast_stack,
    _clean_user_message,
)
from app.frontend.dclm_admin.backend.client import BackendClientError, _format_http_error, _format_network_error
from fasthtml.common import to_xml


def test_toast_structure_error_has_single_close_button():
    _, stack = simple_toast_response(None, "Something went wrong", variant="danger")
    xml = to_xml(stack)

    # Must contain exactly ONE close button
    assert xml.count("btn-close") == 1
    # Must use exclamation-circle for error icon, NOT x-circle (to avoid 2 close X icons)
    assert "bi-exclamation-circle" in xml
    assert "bi-x-circle" not in xml
    # Must have auto-dismiss duration attribute
    assert 'data-fs-duration="3500"' in xml
    # Must have intent="error"
    assert 'data-fs-intent="error"' in xml


def test_toast_structure_success():
    _, stack = simple_toast_response(None, "Operation succeeded", variant="success")
    xml = to_xml(stack)

    assert xml.count("btn-close") == 1
    assert "bi-check-circle" in xml
    assert 'data-fs-intent="success"' in xml


def test_clean_user_message_sanitizes_http_traces():
    raw_trace = "Client error '401 Unauthorized' for url 'http://dclm.internal/api/v1/auth/login' For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401"
    cleaned = _clean_user_message(raw_trace)
    assert "Invalid email or password" in cleaned
    assert "http://dclm.internal" not in cleaned
    assert "mozilla.org" not in cleaned


def test_clean_user_message_unwraps_detail():
    raw = '{"detail": "Member phone number already exists"}'
    cleaned = _clean_user_message(raw)
    assert cleaned == "Member phone number already exists"


def test_backend_client_error_str():
    err = BackendClientError("Invalid input format", status_code=422)
    assert str(err) == "Invalid input format"
    assert err.status_code == 422
