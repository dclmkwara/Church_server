"""Store count reminders as recipient-specific, auditable records.

Revision ID: d4a9c1e7f235
Revises: c2e5a8f14b31
Create Date: 2026-11-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4a9c1e7f235"
down_revision = "c2e5a8f14b31"
branch_labels = None
depends_on = None


def _location_scope_sql() -> str:
    scope = "NULLIF(current_setting('app.scope_path', true), '')::ltree"
    target = "l.path::ltree"
    return (
        f"({scope} IS NOT NULL AND ({target} <@ {scope} OR "
        f"(COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int <> 8 AND {scope} <@ {target})) "
        f"AND (COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int <> 8 OR "
        f"subpath({target},0,2)::text = ANY(string_to_array(NULLIF(current_setting('app.nation_paths', true), ''), '|'))))"
    )


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'permissions'
                  AND column_name = 'operation'
            ) THEN
                INSERT INTO public.permissions (permission, name, description, is_deleted, operation)
                VALUES (
                    'counts:remind', 'Remind Reporting Locations',
                    'Can send a Sunday reporting reminder to eligible users at a location within scope',
                    FALSE, 'CREATE'
                ) ON CONFLICT (permission) DO NOTHING;
            ELSE
                INSERT INTO public.permissions (permission, name, description, is_deleted)
                VALUES (
                    'counts:remind', 'Remind Reporting Locations',
                    'Can send a Sunday reporting reminder to eligible users at a location within scope',
                    FALSE
                ) ON CONFLICT (permission) DO NOTHING;
            END IF;
        END $$
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.permission = 'counts:remind'
        JOIN role_scores rs ON rs.id = r.score_id
        WHERE r.role_name IN ('Group Pastor', 'Region Pastor', 'State Overseer')
           OR rs.score >= 6
        ON CONFLICT DO NOTHING
    """)
    op.create_table(
        "count_reminder_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("reminder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sent_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("occurrence_date", sa.Date(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sent_by_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.location_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_count_reminder_recipients_reminder_id", "count_reminder_recipients", ["reminder_id"])
    op.create_index("ix_count_reminder_location_day_sent", "count_reminder_recipients", ["location_id", "occurrence_date", "sent_at"])
    op.create_index("ix_count_reminder_recipient_sent", "count_reminder_recipients", ["recipient_user_id", "sent_at"])
    op.execute("ALTER TABLE public.count_reminder_recipients ENABLE ROW LEVEL SECURITY")
    scoped_location = (
        "EXISTS (SELECT 1 FROM public.locations l "
        "WHERE l.location_id = count_reminder_recipients.location_id AND "
        f"{_location_scope_sql()})"
    )
    op.execute(
        "CREATE POLICY count_reminder_recipients_read ON public.count_reminder_recipients "
        f"FOR SELECT TO PUBLIC USING ({scoped_location})"
    )
    op.execute(
        "CREATE POLICY count_reminder_recipients_insert ON public.count_reminder_recipients "
        f"FOR INSERT TO PUBLIC WITH CHECK ({scoped_location})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS count_reminder_recipients_insert ON public.count_reminder_recipients")
    op.execute("DROP POLICY IF EXISTS count_reminder_recipients_read ON public.count_reminder_recipients")
    op.drop_index("ix_count_reminder_recipient_sent", table_name="count_reminder_recipients")
    op.drop_index("ix_count_reminder_location_day_sent", table_name="count_reminder_recipients")
    op.drop_index("ix_count_reminder_recipients_reminder_id", table_name="count_reminder_recipients")
    op.drop_table("count_reminder_recipients")
    op.execute("""
        DELETE FROM role_permissions rp
        USING permissions p
        WHERE rp.permission_id = p.id AND p.permission = 'counts:remind'
    """)
    op.execute("DELETE FROM permissions WHERE permission = 'counts:remind'")
