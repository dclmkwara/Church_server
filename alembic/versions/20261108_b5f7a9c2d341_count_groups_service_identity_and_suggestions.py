"""Revise split count groups for session identity and optional label suggestions.

Revision ID: b5f7a9c2d341
Revises: b5e6f8a1c234
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b5f7a9c2d341"
down_revision = "b5e6f8a1c234"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("count_groups", "group_key", existing_type=sa.String(255), type_=sa.String(400), existing_nullable=False)
    op.add_column("count_groups", sa.Column("service_id", sa.String(60), nullable=False, server_default="main"))
    op.add_column("count_groups", sa.Column("count_mode", sa.String(12), nullable=True))
    op.add_column("count_groups", sa.Column("lead_usher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=True))
    op.add_column("count_groups", sa.Column("close_reason", sa.Text(), nullable=True))
    op.add_column("count_groups", sa.Column("auto_closed_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_column("count_groups", "configured_zones")
    # Map old groups to the new key shape. A former group spanning multiple
    # scheduled events cannot be split without guessing which service parts
    # belong together, so quarantine it as a conflict for explicit resolution.
    op.execute("""
        WITH event_map AS (
            SELECT count_group_id, COUNT(DISTINCT event_id) AS event_count,
                   MIN(event_id::text) FILTER (WHERE event_id IS NOT NULL) AS event_id
            FROM counts
            WHERE count_group_id IS NOT NULL AND is_deleted IS FALSE
            GROUP BY count_group_id
        )
        UPDATE count_groups AS grp
        SET group_key = grp.group_key || chr(58) ||
            CASE WHEN event_map.event_count > 1 THEN 'legacy-conflict'
                 ELSE COALESCE(event_map.event_id, 'none') END || chr(58) || 'main',
            state = CASE WHEN event_map.event_count > 1 THEN 'conflict' ELSE grp.state END
        FROM event_map
        WHERE grp.id = event_map.count_group_id
    """)
    op.execute("""
        UPDATE count_groups
        SET group_key = group_key || chr(58) || 'none' || chr(58) || 'main'
        WHERE NOT EXISTS (SELECT 1 FROM counts WHERE counts.count_group_id = count_groups.id)
    """)
    op.execute("""
        UPDATE count_groups AS grp SET lead_usher_id = first_submitter.entered_by_id
        FROM (
            SELECT DISTINCT ON (count_group_id) count_group_id, entered_by_id
            FROM counts WHERE count_group_id IS NOT NULL AND is_deleted IS FALSE
            ORDER BY count_group_id, created_at, id
        ) AS first_submitter
        WHERE grp.id = first_submitter.count_group_id
    """)
    op.execute("""
        UPDATE count_groups AS grp
        SET count_mode = modes.count_mode
        FROM (
            SELECT count_group_id, min(count_mode) AS count_mode
            FROM counts WHERE count_group_id IS NOT NULL AND count_mode IS NOT NULL
            GROUP BY count_group_id
        ) AS modes
        WHERE grp.id = modes.count_group_id
    """)
    op.create_table(
        "count_section_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("label_key", sa.String(120), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("location_id", "label_key", name="uq_count_section_suggestion_location_label"),
    )
    op.create_index("ix_count_section_suggestions_location_id", "count_section_suggestions", ["location_id"])
    # Existing unambiguous groups map to the default service; ambiguous groups
    # spanning events remain excluded until a lead usher resolves them.


def downgrade() -> None:
    connection = op.get_bind()
    collision = connection.execute(sa.text("""
        SELECT regexp_replace(group_key, ':[^:]*:[^:]*$', '') AS old_key
        FROM count_groups GROUP BY old_key HAVING COUNT(*) > 1 LIMIT 1
    """)).first()
    if collision:
        raise RuntimeError("Cannot downgrade count groups while multiple services share an occurrence; resolve or export those groups first")
    op.execute("UPDATE count_groups SET group_key = regexp_replace(group_key, ':[^:]*:[^:]*$', '')")
    op.drop_index("ix_count_section_suggestions_location_id", table_name="count_section_suggestions")
    op.drop_table("count_section_suggestions")
    op.add_column("count_groups", sa.Column("configured_zones", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.drop_column("count_groups", "auto_closed_at")
    op.drop_column("count_groups", "close_reason")
    op.drop_column("count_groups", "count_mode")
    op.drop_column("count_groups", "lead_usher_id")
    op.drop_column("count_groups", "service_id")
    op.alter_column("count_groups", "group_key", existing_type=sa.String(400), type_=sa.String(255), existing_nullable=False)
