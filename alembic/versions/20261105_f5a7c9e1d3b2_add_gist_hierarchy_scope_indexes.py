"""Add GiST indexes for hierarchy path filters.

Revision ID: f5a7c9e1d3b2
Revises: f4c1d8a6b203
Create Date: 2026-11-05
"""

from alembic import op


revision = "f5a7c9e1d3b2"
down_revision = "f4c1d8a6b203"
branch_labels = None
depends_on = None


PATH_TABLES = (
    "announcements",
    "broadcast_messages",
    "church_members",
    "counts",
    "dclm_groups",
    "event_assignments",
    "fellowship_attendance",
    "fellowship_attendance_summaries",
    "fellowship_members",
    "fellowship_offerings",
    "fellowship_prayer_request",
    "fellowship_testimony",
    "fellowships",
    "locations",
    "media_galleries",
    "nations",
    "offerings",
    "official_appointments",
    "program_campaigns",
    "program_events",
    "records",
    "regions",
    "states",
    "status_change_requests",
    "transfer_requests",
    "users",
    "worker_attendance",
    "worker_attendance_submissions",
    "worker_removal_requests",
    "workers",
)

PROGRAM_SCOPE_TABLES = (
    "counts",
    "offerings",
    "records",
    "worker_attendance",
    "worker_attendance_submissions",
)


def _create_index(table: str, column: str, index_name: str) -> None:
    # Runtime scope predicates cast text-backed paths to LTREE. Index that same
    # expression so both native-LTREE and VARCHAR columns use matching plans.
    op.execute(
        f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" '
        f'ON public."{table}" USING gist (("{column}"::ltree))'
    )


def upgrade() -> None:
    # CONCURRENTLY avoids blocking report submissions while indexes build on a
    # populated deployment. Alembic must leave its DDL transaction for this.
    with op.get_context().autocommit_block():
        for table in PATH_TABLES:
            _create_index(table, "path", f"ix_{table}_path_gist")
        for table in PROGRAM_SCOPE_TABLES:
            _create_index(table, "program_scope_path", f"ix_{table}_program_scope_path_gist")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for table in reversed(PROGRAM_SCOPE_TABLES):
            op.execute(
                f'DROP INDEX CONCURRENTLY IF EXISTS '
                f'public."ix_{table}_program_scope_path_gist"'
            )
        for table in reversed(PATH_TABLES):
            op.execute(
                f'DROP INDEX CONCURRENTLY IF EXISTS public."ix_{table}_path_gist"'
            )
