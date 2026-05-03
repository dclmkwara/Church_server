import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import deps


def test_path_in_scope_allows_descendants():
    assert deps.path_in_scope("org.234.KW", "org.234.KW.ILN.ILE.001")
    assert deps.path_in_scope("org.234.KW", "org.234.KW")


def test_path_in_scope_rejects_siblings():
    assert not deps.path_in_scope("org.234.KW", "org.234.LA")


def test_resolve_scope_path_rejects_escalation():
    current_user = SimpleNamespace(path="org.234.KW.ILN")

    with pytest.raises(HTTPException):
        deps.resolve_scope_path(current_user, "org.234")


def test_resolve_scope_path_accepts_descendant_scope():
    current_user = SimpleNamespace(path="org.234.KW")

    resolved = deps.resolve_scope_path(current_user, "org.234.KW.ILN")

    assert resolved == "org.234.KW.ILN"
