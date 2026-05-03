import os
from pathlib import Path
import re
import sys

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.init_rbac import DEFAULT_PERMISSIONS, DEFAULT_ROLES


ROUTE_PERMISSION_PATTERN = re.compile(r'PermissionChecker\("([^"]+)"\)')


def _route_permissions() -> set[str]:
    route_dir = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "routes"
    permissions: set[str] = set()
    for route_file in route_dir.glob("*.py"):
        text = route_file.read_text(encoding="utf-8")
        permissions.update(ROUTE_PERMISSION_PATTERN.findall(text))
    return permissions


def test_seeded_permissions_cover_route_checks():
    seeded_permissions = {perm["permission"] for perm in DEFAULT_PERMISSIONS}
    missing = sorted(_route_permissions() - seeded_permissions)
    assert missing == []


def test_default_roles_only_reference_seeded_permissions():
    seeded_permissions = {perm["permission"] for perm in DEFAULT_PERMISSIONS}
    unknown_by_role = {
        role_name: sorted(set(config["permissions"]) - seeded_permissions)
        for role_name, config in DEFAULT_ROLES.items()
        if set(config["permissions"]) - seeded_permissions
    }
    assert unknown_by_role == {}
