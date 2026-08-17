"""
Seed permissions used across the codebase.

Run:
  python scripts/seed_permissions.py
"""
import asyncio
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import AsyncSessionLocal, engine
from app.models.user import Permission


PERMISSION_PATTERNS = [
    re.compile(r"PermissionChecker\(\"([^\"]+)\"\)"),
    re.compile(r"PermissionChecker\('([^']+)'\)"),
    re.compile(r"has_permission\(\"([^\"]+)\"\)"),
    re.compile(r"has_permission\('([^']+)'\)"),
]

ACTION_TITLE_MAP = {
    "create": "Create",
    "read": "Read",
    "update": "Update",
    "delete": "Delete",
    "manage": "Manage",
    "assign_roles": "Assign Roles",
    "refresh": "Refresh",
    "seed": "Seed",
    "batch": "Batch",
    "read_changes": "Read Changes",
    "conflicts": "View Conflicts",
    "resolve": "Resolve Conflicts",
    "approve": "Approve",
    "reject": "Reject",
    "stats": "View Stats",
    "verify": "Verify",
    "export": "Export",
}

ACTION_DESC_MAP = {
    "create": "create",
    "read": "read",
    "update": "update",
    "delete": "delete",
    "manage": "manage",
    "assign_roles": "assign roles for",
    "refresh": "refresh",
    "seed": "seed",
    "batch": "batch create",
    "read_changes": "read changes for",
    "conflicts": "view conflicts for",
    "resolve": "resolve conflicts for",
    "approve": "approve",
    "reject": "reject",
    "stats": "view stats for",
    "verify": "verify",
    "export": "export",
}


def _titleize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def discover_permissions(root: Path) -> List[str]:
    permissions: Set[str] = set()
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in PERMISSION_PATTERNS:
            for match in pattern.findall(text):
                permissions.add(match.strip())
    return sorted(permissions)


def build_name_and_description(permission: str) -> Tuple[str, str]:
    if ":" in permission:
        resource, action = permission.split(":", 1)
    else:
        resource, action = permission, "manage"

    action_key = action.lower()
    resource_title = _titleize(resource)
    action_title = ACTION_TITLE_MAP.get(action_key, _titleize(action_key))

    name = f"{resource_title} {action_title}"
    action_desc = ACTION_DESC_MAP.get(action_key, action_key)
    desc = f"Can {action_desc} {resource_title.lower()}"
    return name, desc


async def seed_permissions() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    app_root = repo_root / "app"

    permissions = discover_permissions(app_root)
    if not permissions:
        print("No permissions discovered.")
        return

    created = 0
    updated = 0

    async with AsyncSessionLocal() as db:
        for perm in permissions:
            name, desc = build_name_and_description(perm)
            existing = (await db.execute(
                select(Permission).where(Permission.permission == perm)
            )).scalars().first()

            if existing:
                changed = False
                if existing.name != name:
                    existing.name = name
                    changed = True
                if existing.description != desc:
                    existing.description = desc
                    changed = True
                if changed:
                    db.add(existing)
                    updated += 1
            else:
                db.add(Permission(permission=perm, name=name, description=desc))
                created += 1

        await db.commit()

    print(f"Permissions discovered: {len(permissions)}")
    print(f"Created: {created}")
    print(f"Updated: {updated}")


if __name__ == "__main__":
    async def main() -> None:
        try:
            await seed_permissions()
        finally:
            await engine.dispose()

    asyncio.run(main())
