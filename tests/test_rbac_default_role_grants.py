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


def test_count_reminder_permission_is_separate_and_seeded_for_pastors_and_higher_authorities():
    permission_names = {item["permission"] for item in DEFAULT_PERMISSIONS}
    assert "counts:remind" in permission_names
    required_roles = {"Group Pastor", "Region Pastor", "State Overseer"}
    higher_authorities = {
        name for name, role in DEFAULT_ROLES.items() if role["score_id"] >= 6
    }
    actual_roles = {
        name for name, role in DEFAULT_ROLES.items()
        if "counts:remind" in role["permissions"]
    }
    assert required_roles <= actual_roles
    assert actual_roles <= required_roles | higher_authorities
    assert not {"Location Pastor", "Group Admin", "Region Admin", "State Admin"} & actual_roles


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
