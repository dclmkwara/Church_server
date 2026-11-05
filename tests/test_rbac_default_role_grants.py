from app.db.init_rbac import DEFAULT_PERMISSIONS, DEFAULT_ROLES


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
