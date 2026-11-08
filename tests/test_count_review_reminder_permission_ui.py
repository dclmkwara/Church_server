from types import SimpleNamespace

from app.frontend.dclm_admin.routes.church_data import _can_remind_counts


def test_count_review_reminder_control_uses_remind_permission():
    permissions = {"counts:review"}
    ctx = SimpleNamespace(has_permission=lambda permission: permission in permissions)

    assert not _can_remind_counts(ctx)
    permissions.add("counts:remind")
    assert _can_remind_counts(ctx)
