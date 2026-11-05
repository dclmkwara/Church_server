"""Align RBAC role scores with the canonical church hierarchy.

Revision ID: 0d8f6a2b4c91
Revises: aa71b5c49d20
Create Date: 2026-11-04
"""

from alembic import context, op
import sqlalchemy as sa


revision = "0d8f6a2b4c91"
down_revision = "aa71b5c49d20"
branch_labels = None
depends_on = None


SCORE_NAMES = {
    1: "Church Worker / Usher",
    2: "Location Pastor",
    3: "Group Pastor",
    4: "Regional Pastor",
    5: "State Pastor / Overseer",
    6: "Zonal Coordinator",
    7: "National Overseer",
    8: "Continental Leader",
    9: "General Overseer / Global Admin",
}

ROLE_SCORES = {
    "House Fellowship Leader": 1,
    "Location Worker": 1,
    "Location Usher": 1,
    "Group Usher": 1,
    "Region Usher": 1,
    "State Usher": 1,
    "Location Admin": 2,
    "Location Pastor": 2,
    "Group Admin": 3,
    "Group Pastor": 3,
    "Region Admin": 4,
    "Region Pastor": 4,
    "State Admin": 5,
    "State Overseer": 5,
    "National Admin": 7,
    "National Overseer": 7,
    "Continental Admin": 8,
    "Continental Overseer": 8,
    "Global Admin": 9,
}

def upgrade() -> None:
    bind = op.get_bind()
    if not context.is_offline_mode():
        migration_role = bind.execute(sa.text("SELECT current_user")).scalar_one()
        flags = bind.execute(sa.text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        if migration_role == "church_app_runtime" or not (flags.rolsuper or flags.rolbypassrls):
            raise RuntimeError("Role hierarchy migration requires the privileged migration role")
        missing_scores = bind.execute(sa.text("SELECT score FROM generate_series(1,9) score EXCEPT SELECT score FROM role_scores")).scalars().all()
        if missing_scores:
            raise RuntimeError(f"Missing role_scores rows: {missing_scores}")
        required = sorted(set(ROLE_SCORES) - {"Zonal Coordinator"})
        existing = set(bind.execute(sa.text("SELECT role_name FROM roles WHERE is_deleted = FALSE")).scalars().all())
        if set(required) - existing:
            raise RuntimeError(f"Missing expected roles: {sorted(set(required) - existing)}")
    descriptions = {
        1: "Worker or usher. Field collection access is limited by approved event assignment.",
        2: "Location Pastor; scope is one physical location.",
        3: "Group Pastor; scope is one group and its descendants.",
        4: "Regional Pastor; scope is one region and its descendants.",
        5: "State Pastor or Overseer; scope is one state and its descendants.",
        6: "Zonal Coordinator; reserved for the separate future levels 6-9 application.",
        7: "National Overseer; reserved for the separate future levels 6-9 application.",
        8: "Continental and general administrator; continent-scoped authority for the separate higher-level application.",
        9: "General Overseer or Global Admin; reserved for the separate future levels 6-9 application.",
    }
    # Rename through unique temporary values, then restore canonical labels.
    bind.execute(sa.text("""
        UPDATE role_scores SET score_name = 'church_score_temp_' || score::text
    """))
    bind.execute(sa.text("""
        UPDATE role_scores SET
            score_name = CASE score
                WHEN 1 THEN 'Church Worker / Usher'
                WHEN 2 THEN 'Location Pastor'
                WHEN 3 THEN 'Group Pastor'
                WHEN 4 THEN 'Regional Pastor'
                WHEN 5 THEN 'State Pastor / Overseer'
                WHEN 6 THEN 'Zonal Coordinator'
                WHEN 7 THEN 'National Overseer'
                WHEN 8 THEN 'Continental Leader'
                WHEN 9 THEN 'General Overseer / Global Admin'
            END,
            description = CASE score
                WHEN 1 THEN 'Worker or usher. Special collection is limited by approved event assignment.'
                WHEN 2 THEN 'Location Pastor; scope is one physical location.'
                WHEN 3 THEN 'Group Pastor; scope is one group and its descendants.'
                WHEN 4 THEN 'Regional Pastor; scope is one region and its descendants.'
                WHEN 5 THEN 'State Pastor or Overseer; scope is one state and its descendants.'
                WHEN 6 THEN 'Zonal Coordinator; higher-tier authority. Zone mapping is pending.'
                WHEN 7 THEN 'National Overseer; overrides state-level authority within assigned nation.'
                WHEN 8 THEN 'Continental and general administrator; overrides national and state authority within assigned continent.'
                WHEN 9 THEN 'Super administrator and superintendent with global authority.'
            END
        WHERE score BETWEEN 1 AND 9
    """))
    bind.execute(sa.text("""
        UPDATE roles r SET score_id = rs.id
        FROM role_scores rs
        WHERE rs.score = CASE r.role_name
            WHEN 'House Fellowship Leader' THEN 1
            WHEN 'Location Worker' THEN 1 WHEN 'Location Usher' THEN 1
            WHEN 'Group Usher' THEN 1 WHEN 'Region Usher' THEN 1 WHEN 'State Usher' THEN 1
            WHEN 'Location Admin' THEN 2 WHEN 'Location Pastor' THEN 2
            WHEN 'Group Admin' THEN 3 WHEN 'Group Pastor' THEN 3
            WHEN 'Region Admin' THEN 4 WHEN 'Region Pastor' THEN 4
            WHEN 'State Admin' THEN 5 WHEN 'State Overseer' THEN 5
            WHEN 'Zonal Coordinator' THEN 6
            WHEN 'National Admin' THEN 7 WHEN 'National Overseer' THEN 7
            WHEN 'Continental Admin' THEN 8 WHEN 'Continental Overseer' THEN 8
            WHEN 'Global Admin' THEN 9
        END
          AND r.is_deleted = FALSE
    """))

    # Existing removal requests were stored with legacy values 4-6 for
    # group/region/state. Convert those holding levels to new review scores 3-5.
    bind.execute(sa.text("UPDATE worker_removal_requests SET current_level = current_level - 1 WHERE current_level BETWEEN 4 AND 6"))

    # Seed a non-privileged reserved role for deployment alignment.
    bind.execute(sa.text("""
        INSERT INTO roles (role_name, description, score_id, created_at, last_modify, is_deleted, operation)
        SELECT 'Zonal Coordinator', 'Reserved for future enterprise application', id, now(), now(), false, 'CREATE'
        FROM role_scores WHERE score = 6
        ON CONFLICT (role_name) DO NOTHING
    """))

    # Rebuild grants from the approved matrix so old tier permissions cannot survive.
    bind.execute(sa.text("DELETE FROM role_permissions"))
    bind.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.is_deleted = FALSE
          AND p.is_deleted = FALSE
          AND (
            (r.role_name IN ('Location Admin','Group Admin','Region Admin','State Admin') AND p.permission IN (
              'workers:read','users:read','programs:read','counts:read','offerings:read','records:read','attendance:read','fellowship:read','announcements:read','notifications:read','rbac:read',
              'counts:create','counts:update','offerings:create','offerings:update','records:create','records:update','attendance:create','attendance:update','fellowship:create','fellowship:update','sync:batch',
              'users:create','users:update','workers:create','workers:update','programs:manage','users:assign_roles'
            ))
            OR (r.role_name IN ('Location Pastor','Group Pastor','Region Pastor','State Overseer') AND p.permission IN (
              'workers:read','users:read','programs:read','counts:read','offerings:read','records:read','attendance:read','fellowship:read','announcements:read','notifications:read','rbac:read',
              'counts:create','counts:update','offerings:create','offerings:update','records:create','records:update','attendance:create','attendance:update','fellowship:create','fellowship:update','sync:batch',
              'users:create','users:update','workers:create','workers:update','programs:manage','users:assign_roles','counts:delete','offerings:delete','records:delete','attendance:delete','fellowship:delete',
              'reports:read','statistics:read','offerings:review','users:approve','users:delete','users:deactivate','workers:approve','workers:delete','announcements:manage','reports:refresh'
            ))
            OR (r.role_name IN ('Group Admin','Group Pastor','Region Admin','Region Pastor','State Admin','State Overseer') AND p.permission IN ('officials:read','officials:manage'))
            OR (r.role_name IN ('State Admin','State Overseer') AND p.permission IN ('programs:assign_workers','programs:approve_assignments'))
            OR (r.role_name IN ('Location Worker','Group Usher','Region Usher','State Usher') AND p.permission IN (
              'workers:read','users:read','programs:read','counts:read','offerings:read','records:read','attendance:read','fellowship:read','announcements:read','notifications:read','sync:batch',
              'counts:create','counts:update','offerings:create','offerings:update','records:create','records:update','attendance:create','attendance:update','fellowship:create','fellowship:update'
            ))
            OR (r.role_name = 'House Fellowship Leader' AND p.permission IN ('fellowship:create','fellowship:read','fellowship:update','sync:batch'))
            OR (r.role_name IN ('Zonal Coordinator','National Admin','National Overseer','Continental Admin','Continental Overseer')
                AND p.permission NOT IN ('rbac:manage','system:seed'))
            OR (r.role_name = 'Global Admin' AND p.is_deleted = FALSE)
          )
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """))

    bind.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.role_name IN ('Location Admin','Location Pastor','Group Admin','Group Pastor','Region Admin','Region Pastor','State Admin','State Overseer') AND p.permission = 'rbac:read'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """))

    bind.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.role_name = 'State Admin'
          AND p.permission IN ('programs:assign_workers','programs:approve_assignments')
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """))

    # Preserve shared-backend governance: score 9 can administer RBAC catalogs,
    # while score 5+ can manage app releases. Lower tiers have no such policy.
    for table in ("roles", "role_scores", "role_permissions", "permissions"):
        bind.execute(sa.text(f"DROP POLICY IF EXISTS church_rls_{table}_write ON public.{table}"))
        bind.execute(sa.text(f"DROP POLICY IF EXISTS church_{table}_write ON public.{table}"))
        bind.execute(sa.text(
            f"CREATE POLICY church_{table}_write ON public.{table} FOR ALL TO PUBLIC "
            "USING (COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int >= 9) "
            "WITH CHECK (COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int >= 9)"
        ))
    # Replace legacy named role policies with policies aligned to the shared
    # score hierarchy; level 9 has global scope, level 8 gets continent-aware
    # data scope, and the RBAC catalog remains score-9 writable.
    bind.execute(sa.text("DROP POLICY IF EXISTS church_rls_roles_read ON public.roles"))
    bind.execute(sa.text("DROP POLICY IF EXISTS church_roles_read ON public.roles"))
    bind.execute(sa.text("CREATE POLICY church_roles_read ON public.roles FOR SELECT TO PUBLIC USING (true)"))
    for table in ("program_domains", "program_types"):
        bind.execute(sa.text(f"DROP POLICY IF EXISTS church_rls_{table}_write ON public.{table}"))
        bind.execute(sa.text(f"DROP POLICY IF EXISTS church_{table}_write ON public.{table}"))
        bind.execute(sa.text(f"CREATE POLICY church_{table}_write ON public.{table} FOR ALL TO PUBLIC USING (COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int >= 9) WITH CHECK (COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int >= 9)"))
    bind.execute(sa.text("DROP POLICY IF EXISTS church_rls_app_versions_write ON public.app_versions"))
    bind.execute(sa.text("DROP POLICY IF EXISTS church_app_versions_write ON public.app_versions"))
    bind.execute(sa.text(
        "CREATE POLICY church_app_versions_write ON public.app_versions FOR ALL TO PUBLIC "
        "USING (COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int >= 5) "
        "WITH CHECK (COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int >= 5)"
    ))

def downgrade() -> None:
    raise RuntimeError("Canonical church role score remapping is intentionally irreversible; restore the pre-change backup instead.")
