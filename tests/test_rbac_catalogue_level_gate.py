from types import SimpleNamespace

from app.frontend.dclm_admin.routes.system import SYSTEM_ITEMS, _system_allowed


def test_rbac_catalogue_is_state_level_only_in_levels_two_to_five_app():
    def context(level):
        return SimpleNamespace(level=level, has_permission=lambda permission: permission == "rbac:read")

    assert not _system_allowed(context(2), 5)
    assert not _system_allowed(context(3), 5)
    assert not _system_allowed(context(4), 5)
    assert _system_allowed(context(5), 5)
    assert next(item for item in SYSTEM_ITEMS if item[0] == "rbac")[3] == 5
