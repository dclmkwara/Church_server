import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.frontend.dclm_admin.auth_context import build_context


def test_generated_urls_omit_user_name_and_role_label_but_keep_view_scope():
    context = build_context({
        "profile": "region_pastor",
        "user_name": "Private Person",
        "role_label": "Region Pastor",
        "scope_path": "dcl.234.kw.ilr",
        "scope_kind": "region",
        "scope_label": "Example Region",
        "home_path": "dcl.234.kw",
        "period": "4w",
    })

    params = parse_qs(urlparse(context.url_for("/reports")).query)

    assert "user_name" not in params
    assert "role_label" not in params
    assert params["profile"] == ["region_pastor"]
    assert params["scope_path"] == ["dcl.234.kw.ilr"]
    assert params["period"] == ["4w"]
