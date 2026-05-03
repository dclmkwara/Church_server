import os
from pathlib import Path
import sys

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import deps as shared_deps
from app.api.v1 import deps as v1_deps


def test_v1_dependency_module_reexports_shared_dependencies():
    assert v1_deps.get_current_user is shared_deps.get_current_user
    assert v1_deps.PermissionChecker is shared_deps.PermissionChecker
    assert v1_deps.resolve_scope_path is shared_deps.resolve_scope_path
