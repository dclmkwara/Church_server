from types import SimpleNamespace

import pytest

from app.db.init_rbac import DEFAULT_PERMISSIONS, DEFAULT_ROLES


def test_count_review_permission_is_seeded_for_the_approving_pastors():
    """Keep count review available through the canonical RBAC initializer."""
    permission_names = {item["permission"] for item in DEFAULT_PERMISSIONS}
    assert "counts:review" in permission_names
    required_roles = {"Group Pastor", "Region Pastor", "State Overseer"}
    actual_roles = {
        name for name, role in DEFAULT_ROLES.items()
        if "counts:review" in role["permissions"]
    }
    assert required_roles <= actual_roles
    assert "Group Admin" not in actual_roles


def test_count_reminder_permission_is_separate_and_seeded_for_governance_roles():
    permission_names = {item["permission"] for item in DEFAULT_PERMISSIONS}
    assert "counts:remind" in permission_names
    required_roles = {
        "Location Admin", "Location Pastor", "Group Admin", "Group Pastor",
        "Region Admin", "Region Pastor", "State Admin", "State Overseer",
    }
    higher_authorities = {name for name, role in DEFAULT_ROLES.items() if role["score_id"] >= 6}
    actual_roles = {
        name for name, role in DEFAULT_ROLES.items()
        if "counts:remind" in role["permissions"]
    }
    assert required_roles <= actual_roles
    assert actual_roles <= required_roles | higher_authorities


def test_admin_roles_prepare_operations_without_pastor_approval_permissions():
    for admin_name in ("Location Admin", "Group Admin", "Region Admin", "State Admin"):
        permissions = set(DEFAULT_ROLES[admin_name]["permissions"])
        assert "counts:remind" in permissions
        assert "workers:request_changes" in permissions
        assert "counts:review" not in permissions
        assert "offerings:review" not in permissions
        assert "workers:approve" not in permissions
        assert "users:assign_roles" not in permissions

    for pastor_name in ("Location Pastor", "Group Pastor", "Region Pastor", "State Overseer"):
        permissions = set(DEFAULT_ROLES[pastor_name]["permissions"])
        assert "users:assign_roles" in permissions
        assert "workers:approve" in permissions
        assert "offerings:review" in permissions


def test_state_admin_and_overseer_can_manage_expected_population():
    assert "population_estimates:manage" in DEFAULT_ROLES["State Admin"]["permissions"]
    assert "population_estimates:manage" in DEFAULT_ROLES["State Overseer"]["permissions"]
    for role_name in ("Location Admin", "Group Admin", "Region Admin"):
        assert "population_estimates:manage" not in DEFAULT_ROLES[role_name]["permissions"]


@pytest.mark.parametrize(
    ("admin_name", "pastor_name"),
    [
        ("Location Admin", "Location Pastor"),
        ("Group Admin", "Group Pastor"),
        ("Region Admin", "Region Pastor"),
        ("State Admin", "State Overseer"),
    ],
)
def test_each_pastor_inherits_all_admin_permissions_at_the_same_level(admin_name, pastor_name):
    admin = DEFAULT_ROLES[admin_name]
    pastor = DEFAULT_ROLES[pastor_name]
    assert admin["score_id"] == pastor["score_id"]
    assert set(admin["permissions"]) <= set(pastor["permissions"])


@pytest.mark.parametrize("admin_name", [
    "Location Admin", "Group Admin", "Region Admin", "State Admin",
])
def test_each_admin_can_prepare_worker_changes_but_cannot_approve(admin_name):
    from app.api.v1.routes.approvals import _require_worker_change_requester

    role = DEFAULT_ROLES[admin_name]
    user = SimpleNamespace(roles=[SimpleNamespace(
        score_value=role["score_id"],
        permissions=[SimpleNamespace(permission=permission) for permission in role["permissions"]],
    )])
    _require_worker_change_requester(user)
    permissions = set(role["permissions"])
    assert "workers:request_changes" in permissions
    assert "workers:approve" not in permissions
    assert "users:assign_roles" not in permissions


@pytest.mark.parametrize("pastor_name", [
    "Location Pastor", "Group Pastor", "Region Pastor", "State Overseer",
])
def test_each_pastor_can_prepare_worker_changes(pastor_name):
    from app.api.v1.routes.approvals import _require_worker_change_requester

    role = DEFAULT_ROLES[pastor_name]
    user = SimpleNamespace(roles=[SimpleNamespace(
        score_value=role["score_id"],
        permissions=[SimpleNamespace(permission=permission) for permission in role["permissions"]],
    )])
    _require_worker_change_requester(user)


def test_field_worker_cannot_prepare_governance_worker_changes():
    from fastapi import HTTPException
    from app.api.v1.routes.approvals import _require_worker_change_requester

    role = DEFAULT_ROLES["Location Worker"]
    user = SimpleNamespace(roles=[SimpleNamespace(
        score_value=role["score_id"],
        permissions=[SimpleNamespace(permission=permission) for permission in role["permissions"]],
    )])
    with pytest.raises(HTTPException) as exc:
        _require_worker_change_requester(user)
    assert exc.value.status_code == 403


def test_fellowship_hierarchy_creation_is_granted_at_region_and_above():
    permission_names = {item["permission"] for item in DEFAULT_PERMISSIONS}
    assert "hierarchy:create_fellowship" in permission_names

    expected_roles = {"Region Admin", "Region Pastor", "State Admin", "State Overseer",
                      "Zonal Coordinator", "National Admin", "National Overseer",
                      "Continental Admin", "Continental Overseer", "Global Admin"}
    actual_roles = {
        role_name
        for role_name, role in DEFAULT_ROLES.items()
        if "hierarchy:create_fellowship" in role["permissions"]
    }
    assert actual_roles == expected_roles

    # Fellowship records are location-scoped; location workers need activity
    # capture permissions, not authority to create the hierarchy entity.
    assert "hierarchy:create_fellowship" not in DEFAULT_ROLES["Location Worker"]["permissions"]
    assert "hierarchy:create_fellowship" not in DEFAULT_ROLES["Group Pastor"]["permissions"]


def test_fellowship_deletion_is_reserved_to_state_and_higher_authority():
    permission_names = {item["permission"] for item in DEFAULT_PERMISSIONS}
    assert "hierarchy:delete_fellowship" in permission_names
    expected_roles = {"State Admin", "State Overseer", "Zonal Coordinator", "National Admin",
                      "National Overseer", "Continental Admin", "Continental Overseer", "Global Admin"}
    actual_roles = {
        role_name
        for role_name, role in DEFAULT_ROLES.items()
        if "hierarchy:delete_fellowship" in role["permissions"]
    }
    assert actual_roles == expected_roles
