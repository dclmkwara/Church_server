"""Store usher attendance captures atomically while retaining worker rows.

Revision ID: aa71b5c49d20
Revises: 9d4c2f1a6b80
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "aa71b5c49d20"
down_revision = "9d4c2f1a6b80"
branch_labels = None
depends_on = None


def _scope(path_expr: str) -> str:
    scope = "NULLIF(current_setting('app.scope_path', true), '')::ltree"
    target = f"({path_expr})::ltree"
    in_scope = f"({target} <@ {scope} OR {scope} <@ {target})"
    nation_scope = (
        "COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int <> 8 OR "
        f"subpath({target}, 0, 2)::text = ANY(string_to_array(NULLIF(current_setting('app.nation_paths', true), ''), '|'))"
    )
    return f"({scope} IS NOT NULL AND {in_scope} AND ({nation_scope}))"


def upgrade() -> None:
    op.create_table(
        "worker_attendance_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("church_type", sa.String(length=40), nullable=False),
        sa.Column("program_domain", sa.String(length=80), nullable=True),
        sa.Column("program_type", sa.String(length=120), nullable=False),
        sa.Column("expected_workers_count", sa.Integer(), nullable=False),
        sa.Column("present_count", sa.Integer(), nullable=False),
        sa.Column("present_workers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("entered_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by_worker_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_by_name", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("operation", sa.String(), server_default="CREATE", nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.location_id"]),
        sa.ForeignKeyConstraint(["event_id"], ["program_events.id"]),
        sa.ForeignKeyConstraint(["entered_by_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["submitted_by_worker_id"], ["workers.worker_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", name="uq_worker_attendance_submissions_client_id"),
        sa.CheckConstraint("expected_workers_count >= 0", name="ck_attendance_submission_expected_nonnegative"),
        sa.CheckConstraint("present_count > 0 AND present_count <= expected_workers_count", name="ck_attendance_submission_present_count"),
    )
    op.execute("ALTER TABLE worker_attendance_submissions ALTER COLUMN path TYPE LTREE USING path::ltree")
    op.add_column(
        "worker_attendance",
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_worker_attendance_submission_id",
        "worker_attendance",
        "worker_attendance_submissions",
        ["submission_id"], ["id"], ondelete="SET NULL",
    )
    for index, table, columns in (
        ("ix_worker_attendance_submissions_path", "worker_attendance_submissions", ["path"]),
        ("ix_worker_attendance_submissions_location_id", "worker_attendance_submissions", ["location_id"]),
        ("ix_worker_attendance_submissions_event_id", "worker_attendance_submissions", ["event_id"]),
        ("ix_worker_attendance_submissions_date", "worker_attendance_submissions", ["date"]),
        ("ix_worker_attendance_submissions_church_type", "worker_attendance_submissions", ["church_type"]),
        ("ix_worker_attendance_submissions_program_domain", "worker_attendance_submissions", ["program_domain"]),
        ("ix_worker_attendance_submissions_program_type", "worker_attendance_submissions", ["program_type"]),
        ("ix_worker_attendance_submissions_created_at", "worker_attendance_submissions", ["created_at"]),
        ("ix_worker_attendance_submissions_is_deleted", "worker_attendance_submissions", ["is_deleted"]),
        ("ix_worker_attendance_submissions_operation", "worker_attendance_submissions", ["operation"]),
        ("ix_worker_attendance_submissions_entered_by_id", "worker_attendance_submissions", ["entered_by_id"]),
        ("ix_worker_attendance_submissions_submitted_by_worker_id", "worker_attendance_submissions", ["submitted_by_worker_id"]),
        ("ix_worker_attendance_submission_id", "worker_attendance", ["submission_id"]),
    ):
        op.create_index(index, table, columns)

    op.execute("ALTER TABLE public.worker_attendance_submissions ENABLE ROW LEVEL SECURITY")
    scope = _scope("path")
    op.execute(
        "CREATE POLICY church_attendance_submissions_read ON public.worker_attendance_submissions "
        f"FOR SELECT TO PUBLIC USING ({scope})"
    )
    op.execute(
        "CREATE POLICY church_attendance_submissions_write ON public.worker_attendance_submissions "
        f"FOR ALL TO PUBLIC USING ({scope}) WITH CHECK ({scope})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS church_attendance_submissions_write ON public.worker_attendance_submissions")
    op.execute("DROP POLICY IF EXISTS church_attendance_submissions_read ON public.worker_attendance_submissions")
    op.drop_index("ix_worker_attendance_submission_id", table_name="worker_attendance")
    for index in (
        "ix_worker_attendance_submissions_submitted_by_worker_id", "ix_worker_attendance_submissions_entered_by_id",
        "ix_worker_attendance_submissions_operation", "ix_worker_attendance_submissions_is_deleted",
        "ix_worker_attendance_submissions_created_at", "ix_worker_attendance_submissions_program_type",
        "ix_worker_attendance_submissions_program_domain", "ix_worker_attendance_submissions_church_type",
        "ix_worker_attendance_submissions_date", "ix_worker_attendance_submissions_event_id",
        "ix_worker_attendance_submissions_location_id", "ix_worker_attendance_submissions_path",
    ):
        op.drop_index(index, table_name="worker_attendance_submissions")
    op.drop_constraint("fk_worker_attendance_submission_id", "worker_attendance", type_="foreignkey")
    op.drop_column("worker_attendance", "submission_id")
    op.drop_table("worker_attendance_submissions")
