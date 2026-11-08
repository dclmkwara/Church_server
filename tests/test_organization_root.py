from types import SimpleNamespace

from app.frontend.dclm_admin.routes.organization import _location_home_id


def test_location_organization_root_uses_location_uuid_not_path_segment():
    ctx = SimpleNamespace(level=2, current_scope_path="org.234.KW.ILR.ILE.003")
    identity = SimpleNamespace(user={"location_id": "9fcb3ead-014c-4f6f-8a92-27293fcbd31f"})

    assert _location_home_id(ctx, identity) == "9fcb3ead-014c-4f6f-8a92-27293fcbd31f"
    assert _location_home_id(ctx, identity) != ctx.current_scope_path.split(".")[-1]


def test_organization_root_fails_closed_when_location_id_is_missing():
    ctx = SimpleNamespace(level=2, current_scope_path="org.234.KW.ILR.ILE.003")

    assert _location_home_id(ctx, SimpleNamespace(user={})) == ""
