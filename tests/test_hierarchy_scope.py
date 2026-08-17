import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-suite-32-chars-min")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.routes import hierarchy


def test_hierarchy_read_allows_ancestor_node():
    current_user = SimpleNamespace(path="org.234.KW.ILR.ILE.003")
    node = SimpleNamespace(path="org.234.KW")

    hierarchy._ensure_hierarchy_visible(current_user, node)


def test_hierarchy_read_rejects_unrelated_node():
    current_user = SimpleNamespace(path="org.234.KW.ILR")
    node = SimpleNamespace(path="org.234.LA")

    with pytest.raises(HTTPException):
        hierarchy._ensure_hierarchy_visible(current_user, node)


def test_hierarchy_write_rejects_ancestor_node():
    current_user = SimpleNamespace(path="org.234.KW.ILR")
    node = SimpleNamespace(path="org.234.KW")

    with pytest.raises(HTTPException):
        hierarchy._ensure_hierarchy_mutable(current_user, node)
