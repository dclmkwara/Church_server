from types import SimpleNamespace

from fasthtml.common import to_xml
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.init_rbac import ADMIN_PERMS, PASTOR_PERMS
from app.db.session import _AUDITED_FIELDS, _audit_governance_setup_changes
from app.frontend.dclm_admin.routes.communication import _communication_mobile_card
from app.frontend.dclm_admin.routes.system import _audit_allowed
from app.models.audit import AuditLog
from app.models.programs import ProgramCampaign
from app.services.audit_service import add_audit_record


def test_governance_setup_create_records_actor_role_path_and_safe_fields():
    session = Session()
    session.info["audit_actor"] = {
        "user_id": "actor-id",
        "actor_name": "Pastor Example",
        "role_name": "Region Pastor",
        "role_score": 4,
        "scope_path": "org.234.kw.ilr",
    }
    campaign = ProgramCampaign(
        title="Demo Retreat",
        campaign_code="DEMO-RETREAT",
        domain_id=1,
        event_mode="retreat",
        reporting_scope="region",
        status="draft",
        path="org.234.kw.ilr",
    )
    session.add(campaign)

    _audit_governance_setup_changes(session, None, None)

    audit = next(item for item in session.new if isinstance(item, AuditLog))
    assert audit.action == "CREATE_PROGRAM_CAMPAIGNS"
    assert audit.changes["actor_name"] == "Pastor Example"
    assert audit.changes["role_name"] == "Region Pastor"
    assert audit.changes["role_score"] == 4
    assert audit.changes["scope_path"] == "org.234.kw.ilr"
    assert audit.changes["fields"]["title"] == "Demo Retreat"
    assert "description" not in audit.changes["fields"]
    session.close()


def test_audit_instruments_all_requested_setup_and_change_tables():
    expected = {
        "program_campaigns", "program_events", "event_assignments",
        "worker_transfers", "transfer_requests", "worker_removal_requests",
        "status_change_requests", "nations", "states", "regions",
        "dclm_groups", "locations", "fellowships",
    }
    assert expected <= set(_AUDITED_FIELDS)


def test_scoped_audit_permission_is_pastor_only_by_default():
    assert "system:read_audit_logs" in PASTOR_PERMS
    assert "system:read_audit_logs" not in ADMIN_PERMS
    pastor = SimpleNamespace(level=4, has_permission=lambda permission: permission == "system:read_audit_logs")
    admin = SimpleNamespace(level=4, has_permission=lambda permission: False)
    assert _audit_allowed(pastor)
    assert not _audit_allowed(admin)


def test_announcement_admin_card_is_read_only():
    class Context:
        def has_permission(self, permission: str) -> bool:
            return False

        def url_for(self, path: str, **kwargs) -> str:
            return path.format(**kwargs)

    row = {
        "title": "Weekly note", "status": "published", "meeting_label": "Workers Meeting",
        "meeting_date": "2026-11-07", "summary": "Weekly information", "announcement_id": "id-1",
    }
    html = to_xml(_communication_mobile_card(Context(), row))
    assert "Open" in html
    assert "Edit" not in html
    assert "/edit" not in html


def test_export_audit_captures_actor_role_and_scope():
    actor = SimpleNamespace(
        user_id="actor-id", name="Pastor Example", path="org.234.kw.ilr",
        roles=[SimpleNamespace(role_name="Region Pastor", score_value=4)],
    )
    session = AsyncSession()
    row = add_audit_record(
        session, actor=actor, action="EXPORT_REPORT_CSV", resource_type="report_export",
        resource_id="counts", scope_path="org.234.kw.ilr",
        fields={"format": "csv", "report_type": "counts"},
    )
    assert row in session.sync_session.new
    assert row.changes["actor_name"] == "Pastor Example"
    assert row.changes["role_name"] == "Region Pastor"
    assert row.changes["scope_path"] == "org.234.kw.ilr"
    assert row.changes["fields"]["format"] == "csv"
