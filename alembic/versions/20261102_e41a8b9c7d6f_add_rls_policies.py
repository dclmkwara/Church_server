"""add fail-closed row level security policies

Revision ID: e41a8b9c7d6f
Revises: d30e17a4bc52
Create Date: 2026-11-02
"""

from alembic import op
from sqlalchemy import text


revision = "e41a8b9c7d6f"
down_revision = "d30e17a4bc52"
branch_labels = None
depends_on = None


PATH_TABLES = (
    "announcements", "church_members", "counts", "dclm_groups", "event_assignments",
    "fellowship_attendance", "fellowship_attendance_summaries", "fellowship_members",
    "fellowship_offerings", "fellowship_prayer_request", "fellowship_testimony",
    "fellowships", "locations", "media_galleries", "nations", "offerings",
    "official_appointments", "program_campaigns", "program_events", "records",
    "regions", "states", "status_change_requests", "transfer_requests", "users",
    "worker_attendance", "worker_removal_requests", "workers",
)
PROTECTED_TABLES = (
    "announcement_items", "announcements", "app_versions", "audit_logs", "church_members",
    "counts", "dclm_groups", "event_assignments", "fellowship_attendance",
    "fellowship_attendance_summaries", "fellowship_members", "fellowship_offerings",
    "fellowship_prayer_request", "fellowship_testimony", "fellowships", "idempotency_keys",
    "location_profiles", "locations", "media_galleries", "media_items", "nations",
    "notification_read_states", "offering_audits", "offerings", "official_appointments",
    "password_reset_tokens", "permissions", "program_campaigns", "program_domains",
    "program_events", "program_types", "public_contact_submissions", "public_prayer_submissions",
    "records", "refresh_tokens", "regions", "role_permissions", "role_scores", "roles",
    "states", "status_change_requests", "transfer_requests", "user_roles", "users",
    "worker_absence_notices", "worker_attendance", "worker_removal_requests",
    "worker_transfers", "workers",
)


def _scope(path_expr: str, *, ancestors: bool = True) -> str:
    scope = "NULLIF(current_setting('app.scope_path', true), '')::ltree"
    target = f"({path_expr})::ltree"
    in_scope = f"({target} <@ {scope})"
    if ancestors:
        in_scope = (
            f"({in_scope} OR (COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int <> 8 "
            f"AND {scope} <@ {target}))"
        )
    return (
        f"({scope} IS NOT NULL AND {in_scope} AND "
        "(COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int <> 8 OR "
        f"subpath({target}, 0, 2)::text = ANY(string_to_array(NULLIF(current_setting('app.nation_paths', true), ''), '|'))))"
    )


def _create_policy(name: str, table: str, command: str, using: str, check: str | None = None) -> None:
    statement = f"CREATE POLICY church_{name} ON public.{table} FOR {command} TO PUBLIC"
    if command != "INSERT":
        statement += f" USING ({using})"
    if check is not None:
        statement += f" WITH CHECK ({check})"
    op.execute(statement)


def upgrade() -> None:
    role = op.get_bind().execute(text("SELECT current_user")).scalar_one()
    flags = op.get_bind().execute(text("""
        SELECT r.rolsuper, r.rolbypassrls
        FROM pg_roles r WHERE r.rolname = current_user
    """)).one()
    if role == "church_app_runtime" or not (flags.rolsuper or flags.rolbypassrls):
        raise RuntimeError("RLS migration must run using a dedicated privileged migration role, never the API runtime role")
    tables = set(PROTECTED_TABLES)
    for table in PROTECTED_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")

    for table in PATH_TABLES:
        scope = _scope("path")
        select_policy = scope
        if table == "users":
            select_policy = (
                f"({scope} OR user_id::text = NULLIF(current_setting('app.user_id', true), '') "
                "OR lower(email) = lower(NULLIF(current_setting('app.auth_email', true), '')))"
            )
        elif table == "nations":
            own_home_nation = """
                path = (
                    SELECT subpath(u.path::ltree, 0, 2)
                    FROM public.users u
                    WHERE u.user_id::text = NULLIF(current_setting('app.user_id', true), '')
                    LIMIT 1
                )
            """
            same_continent = """
                (NULLIF(current_setting('app.continent', true), '') IS NOT NULL
                 AND lower(trim(continent)) = lower(current_setting('app.continent', true)))
            """
            select_policy = f"({scope} OR {own_home_nation} OR {same_continent})"

        public_read = {
            "announcements": "is_active IS TRUE",
            "program_events": "is_public IS TRUE AND is_deleted IS FALSE",
            "media_galleries": "is_public IS TRUE AND is_deleted IS FALSE",
        }.get(table)
        if public_read:
            select_policy = f"({select_policy} OR ({public_read}))"

        _create_policy(f"rls_{table}_read", table, "SELECT", select_policy)
        write_policy = scope
        if table == "users":
            write_policy = f"({scope} OR user_id::text = NULLIF(current_setting('app.user_id', true), ''))"
        _create_policy(f"rls_{table}_write", table, "ALL", write_policy, write_policy)

    admin = "COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int >= 9"
    scoped_admin = "COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int >= 5"

    # Shared, non-sensitive lookup data is readable; only root administrators
    # may alter it. Protected tables stay deny-by-default without a policy.
    for table in ("program_domains", "program_types", "permissions", "role_scores", "roles", "role_permissions"):
        if table in tables:
            _create_policy(f"rls_{table}_read", table, "SELECT", "TRUE")
            _create_policy(f"rls_{table}_write", table, "ALL", admin, admin)
    if "app_versions" in tables:
        _create_policy("rls_app_versions_read", "app_versions", "SELECT", "is_active IS TRUE")
        _create_policy("rls_app_versions_write", "app_versions", "ALL", admin, admin)

    related_policies = {
        "announcement_items": (
            "EXISTS (SELECT 1 FROM public.announcements a WHERE a.id = announcement_items.announcement_id)",
            "EXISTS (SELECT 1 FROM public.announcements a WHERE a.id = announcement_items.announcement_id "
            f"AND {_scope('a.path')})",
        ),
        "media_items": (
            "EXISTS (SELECT 1 FROM public.media_galleries g WHERE g.id = media_items.gallery_id)",
            "EXISTS (SELECT 1 FROM public.media_galleries g WHERE g.id = media_items.gallery_id "
            f"AND {_scope('g.path')})",
        ),
        "location_profiles": (
            "EXISTS (SELECT 1 FROM public.locations l WHERE l.location_id::text = location_profiles.location_id::text "
            f"AND {_scope('l.path')})",
            "EXISTS (SELECT 1 FROM public.locations l WHERE l.location_id::text = location_profiles.location_id::text "
            f"AND {_scope('l.path')})",
        ),
        "offering_audits": (
            "EXISTS (SELECT 1 FROM public.offerings o WHERE o.id = offering_audits.offering_id "
            f"AND {_scope('o.path')})",
            "EXISTS (SELECT 1 FROM public.offerings o WHERE o.id = offering_audits.offering_id "
            f"AND {_scope('o.path')}) AND offering_audits.actor_id::text = NULLIF(current_setting('app.user_id', true), '')",
        ),
        "worker_absence_notices": (
            "EXISTS (SELECT 1 FROM public.workers w WHERE w.worker_id = worker_absence_notices.worker_id "
            f"AND {_scope('w.path')})",
            "EXISTS (SELECT 1 FROM public.workers w WHERE w.worker_id = worker_absence_notices.worker_id "
            f"AND {_scope('w.path')})",
        ),
        "worker_transfers": (
            "(EXISTS (SELECT 1 FROM public.locations l WHERE l.location_id::text = worker_transfers.from_location_id::text "
            f"AND {_scope('l.path')}) OR EXISTS (SELECT 1 FROM public.locations l WHERE l.location_id::text = worker_transfers.to_location_id::text "
            f"AND {_scope('l.path')}))",
            "(EXISTS (SELECT 1 FROM public.locations l WHERE l.location_id::text = worker_transfers.from_location_id::text "
            f"AND {_scope('l.path')}) OR EXISTS (SELECT 1 FROM public.locations l WHERE l.location_id::text = worker_transfers.to_location_id::text "
            f"AND {_scope('l.path')}))",
        ),
        "user_roles": (
            "(user_roles.user_id::text = NULLIF(current_setting('app.user_id', true), '') OR "
            "EXISTS (SELECT 1 FROM public.users u WHERE u.user_id = user_roles.user_id))",
            "EXISTS (SELECT 1 FROM public.users u WHERE u.user_id = user_roles.user_id "
            f"AND {_scope('u.path')})",
        ),
    }
    for table, (read_predicate, write_predicate) in related_policies.items():
        if table not in tables:
            continue
        _create_policy(f"rls_{table}_read", table, "SELECT", read_predicate)
        _create_policy(f"rls_{table}_write", table, "ALL", write_predicate, write_predicate)

    if "audit_logs" in tables:
        audit_read = f"(user_id::text = NULLIF(current_setting('app.user_id', true), '') OR {admin})"
        audit_write = f"({admin} OR user_id::text = NULLIF(current_setting('app.user_id', true), ''))"
        _create_policy("rls_audit_logs_read", "audit_logs", "SELECT", audit_read)
        _create_policy("rls_audit_logs_write", "audit_logs", "ALL", audit_write, audit_write)

    for table in ("notification_read_states", "refresh_tokens"):
        if table in tables:
            own = "user_id::text = NULLIF(current_setting('app.user_id', true), '')"
            _create_policy(f"rls_{table}_own", table, "ALL", own, own)

    if "password_reset_tokens" in tables:
        reset = "token = NULLIF(current_setting('app.reset_token', true), '')"
        reset_insert = "user_id::text = NULLIF(current_setting('app.user_id', true), '')"
        _create_policy("rls_password_reset_tokens_read", "password_reset_tokens", "SELECT", reset)
        _create_policy("rls_password_reset_tokens_update", "password_reset_tokens", "UPDATE", reset, reset_insert)
        _create_policy("rls_password_reset_tokens_insert", "password_reset_tokens", "INSERT", "TRUE", reset_insert)

    for table in ("public_contact_submissions", "public_prayer_submissions"):
        if table not in tables:
            continue
        _create_policy(f"rls_{table}_insert", table, "INSERT", "TRUE", "TRUE")
        _create_policy(f"rls_{table}_review", table, "SELECT", scoped_admin)
        _create_policy(f"rls_{table}_review_write", table, "UPDATE", scoped_admin, scoped_admin)

    if "idempotency_keys" in tables:
        _create_policy("rls_idempotency_keys_admin", "idempotency_keys", "ALL", admin, admin)


def downgrade() -> None:
    op.execute("""
        DO $$
        DECLARE policy_row record;
        BEGIN
            FOR policy_row IN
                SELECT schemaname, tablename, policyname
                FROM pg_policies
                WHERE schemaname = 'public' AND left(policyname, 11) = 'church_rls_'
            LOOP
                EXECUTE format('DROP POLICY %I ON %I.%I', policy_row.policyname,
                               policy_row.schemaname, policy_row.tablename);
            END LOOP;
        END $$;
    """)
    for table in PROTECTED_TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
