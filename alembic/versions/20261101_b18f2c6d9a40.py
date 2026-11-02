"""enforce attendance and record integrity rules

Revision ID: b18f2c6d9a40
Revises: a07be837513a
Create Date: 2026-11-01
"""

from alembic import op
import sqlalchemy as sa


revision = "b18f2c6d9a40"
down_revision = "a07be837513a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Never deduplicate attendance automatically. Existing collisions need review.
    op.execute("""
        DO $$
        DECLARE duplicate_groups bigint;
        BEGIN
            SELECT count(*) INTO duplicate_groups FROM (
                SELECT event_id, worker_id FROM worker_attendance
                WHERE is_deleted = false
                GROUP BY event_id, worker_id HAVING count(*) > 1
            ) duplicates;
            IF duplicate_groups > 0 THEN
                RAISE EXCEPTION 'Cannot enforce one active worker attendance per event: % duplicate groups require reconciliation', duplicate_groups;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        DECLARE invalid_rows bigint;
        BEGIN
            SELECT count(*) INTO invalid_rows FROM counts
            WHERE adult_male < 0 OR adult_female < 0 OR youth_male < 0
               OR youth_female < 0 OR boys < 0 OR girls < 0
               OR total <> adult_male + adult_female + youth_male
                            + youth_female + boys + girls;
            IF invalid_rows > 0 THEN
                RAISE EXCEPTION 'Cannot enforce count integrity: % rows have negative values or incorrect totals', invalid_rows;
            END IF;
            SELECT count(*) INTO invalid_rows FROM offerings WHERE amount <= 0;
            IF invalid_rows > 0 THEN
                RAISE EXCEPTION 'Cannot enforce positive offering amounts: % invalid rows require review', invalid_rows;
            END IF;
            SELECT count(*) INTO invalid_rows FROM worker_attendance
            WHERE status NOT IN ('present', 'absent', 'late', 'excused');
            IF invalid_rows > 0 THEN
                RAISE EXCEPTION 'Cannot enforce attendance statuses: % invalid rows require review', invalid_rows;
            END IF;
            SELECT count(*) INTO invalid_rows FROM program_campaigns
            WHERE start_date > end_date
               OR (collection_window_start IS NOT NULL AND collection_window_end IS NOT NULL
                   AND collection_window_start > collection_window_end);
            IF invalid_rows > 0 THEN
                RAISE EXCEPTION 'Cannot enforce campaign windows: % invalid rows require review', invalid_rows;
            END IF;
            SELECT count(*) INTO invalid_rows FROM program_events
            WHERE collection_window_start IS NOT NULL AND collection_window_end IS NOT NULL
              AND collection_window_start > collection_window_end;
            IF invalid_rows > 0 THEN
                RAISE EXCEPTION 'Cannot enforce event windows: % invalid rows require review', invalid_rows;
            END IF;
        END $$;
    """)
    op.create_index(
        "uq_worker_attendance_active_event_worker",
        "worker_attendance",
        ["event_id", "worker_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    for name, table, condition in (
        ("ck_counts_nonnegative_categories", "counts", "adult_male >= 0 AND adult_female >= 0 AND youth_male >= 0 AND youth_female >= 0 AND boys >= 0 AND girls >= 0"),
        ("ck_counts_total_matches_components", "counts", "total = adult_male + adult_female + youth_male + youth_female + boys + girls"),
        ("ck_offerings_positive_amount", "offerings", "amount > 0"),
        ("ck_worker_attendance_status", "worker_attendance", "status IN ('present', 'absent', 'late', 'excused')"),
        ("ck_program_campaign_date_order", "program_campaigns", "start_date <= end_date"),
        ("ck_program_campaign_window_order", "program_campaigns", "collection_window_start IS NULL OR collection_window_end IS NULL OR collection_window_start <= collection_window_end"),
        ("ck_program_event_window_order", "program_events", "collection_window_start IS NULL OR collection_window_end IS NULL OR collection_window_start <= collection_window_end"),
    ):
        op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    for name, table in (
        ("ck_program_event_window_order", "program_events"),
        ("ck_program_campaign_window_order", "program_campaigns"),
        ("ck_program_campaign_date_order", "program_campaigns"),
        ("ck_worker_attendance_status", "worker_attendance"),
        ("ck_offerings_positive_amount", "offerings"),
        ("ck_counts_total_matches_components", "counts"),
        ("ck_counts_nonnegative_categories", "counts"),
    ):
        op.drop_constraint(name, table, type_="check")
    op.drop_index("uq_worker_attendance_active_event_worker", table_name="worker_attendance")
