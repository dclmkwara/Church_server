"""enforce client submission idempotency

Revision ID: a07be837513a
Revises: f7b8c9d0e1f2
Create Date: 2026-11-01 17:35:14.102259+00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = 'a07be837513a'
down_revision = 'f7b8c9d0e1f2'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Fail safely if old clients have already produced collisions. Do not pick
    # or delete a canonical row automatically; remediation needs provenance.
    op.execute(
        """
        DO $$
        DECLARE
            table_name text;
            duplicate_groups bigint;
        BEGIN
            FOREACH table_name IN ARRAY ARRAY[
                'counts', 'offerings', 'records', 'worker_attendance', 'church_members',
                'fellowship_members', 'fellowship_attendance', 'fellowship_offerings',
                'fellowship_testimony', 'fellowship_prayer_request',
                'fellowship_attendance_summaries'
            ] LOOP
                EXECUTE format(
                    'SELECT count(*) FROM (SELECT client_id FROM %I '
                    'WHERE client_id IS NOT NULL GROUP BY client_id HAVING count(*) > 1) d',
                    table_name
                ) INTO duplicate_groups;
                IF duplicate_groups > 0 THEN
                    RAISE EXCEPTION
                        'Cannot add idempotency index on %.client_id: % duplicate client IDs exist; reconcile them first',
                        table_name, duplicate_groups;
                END IF;
                EXECUTE format(
                    'CREATE UNIQUE INDEX IF NOT EXISTS %I ON %I (client_id) WHERE client_id IS NOT NULL',
                    'uq_' || table_name || '_client_id', table_name
                );
            END LOOP;
        END $$;
        """
    )

def downgrade() -> None:
    for table_name in (
        "counts",
        "offerings",
        "records",
        "worker_attendance",
        "church_members",
        "fellowship_members",
        "fellowship_attendance",
        "fellowship_offerings",
        "fellowship_testimony",
        "fellowship_prayer_request",
        "fellowship_attendance_summaries",
    ):
        op.execute(f"DROP INDEX IF EXISTS uq_{table_name}_client_id")
