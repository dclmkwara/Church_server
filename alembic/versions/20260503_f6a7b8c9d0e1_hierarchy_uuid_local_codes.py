"""move hierarchy tables to uuid primary keys and parent-scoped local codes

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-03 18:00:00.000000

This migration is intentionally conservative. It can rebuild the old hierarchy
schema only while dependent operational tables are empty. Fresh deployments that
already use the new model schema simply no-op.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


DEPENDENT_TABLES = [
    "workers",
    "users",
    "counts",
    "offerings",
    "records",
    "worker_attendance",
    "church_members",
    "location_profiles",
    "worker_transfers",
    "transfer_requests",
    "program_campaigns",
    "program_events",
    "official_appointments",
]


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _row_count(table_name: str) -> int:
    return op.get_bind().execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()


def _require_empty_dependents(inspector) -> None:
    populated = [
        table_name
        for table_name in DEPENDENT_TABLES
        if _table_exists(inspector, table_name) and _row_count(table_name) > 0
    ]
    if populated:
        raise RuntimeError(
            "Hierarchy UUID/local-code migration requires empty dependent tables. "
            "Reset the fresh deployment database or migrate data explicitly first. "
            f"Populated tables: {', '.join(populated)}"
        )


def _alter_location_reference_columns(inspector) -> None:
    for table_name, column_names in {
        "workers": ["location_id"],
        "users": ["location_id"],
        "counts": ["location_id"],
        "offerings": ["location_id"],
        "records": ["location_id"],
        "worker_attendance": ["location_id"],
        "church_members": ["location_id", "fellowship_id"],
        "location_profiles": ["location_id"],
        "worker_transfers": ["from_location_id", "to_location_id"],
        "transfer_requests": ["from_location_id", "to_location_id"],
        "program_campaigns": ["alpha_location_id"],
        "program_events": ["alpha_location_id"],
        "official_appointments": ["location_id"],
    }.items():
        if not _table_exists(inspector, table_name):
            continue
        for column_name in column_names:
            if _column_exists(inspector, table_name, column_name):
                nullable = column_name in {"fellowship_id", "alpha_location_id"}
                op.alter_column(
                    table_name,
                    column_name,
                    type_=postgresql.UUID(),
                    postgresql_using=f"NULL::{column_name and 'uuid'}",
                    existing_nullable=nullable,
                )


def _drop_old_hierarchy_tables() -> None:
    op.execute("DROP TABLE IF EXISTS fellowships CASCADE")
    op.execute("DROP TABLE IF EXISTS locations CASCADE")
    op.execute("DROP TABLE IF EXISTS dclm_groups CASCADE")
    op.execute("DROP TABLE IF EXISTS regions CASCADE")
    op.execute("DROP TABLE IF EXISTS states CASCADE")
    op.execute("DROP TABLE IF EXISTS nations CASCADE")


def _create_hierarchy_tables() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "nations",
        sa.Column("nation_id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nation_code", sa.String(), nullable=False),
        sa.Column("continent", sa.String(), nullable=False),
        sa.Column("country_name", sa.String(), nullable=False),
        sa.Column("capital", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("church_hq", sa.String(), nullable=True),
        sa.Column("national_pastor", sa.String(), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("nation_code", name="uq_nations_nation_code"),
    )
    op.execute("ALTER TABLE nations ALTER COLUMN path TYPE ltree USING path::ltree")
    op.create_index("ix_nations_nation_code", "nations", ["nation_code"])
    op.create_index("ix_nations_created_by", "nations", ["created_by"])
    op.create_index("ix_nations_path", "nations", ["path"], postgresql_using="gist")

    op.create_table(
        "states",
        sa.Column("state_id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nation_id", postgresql.UUID(), sa.ForeignKey("nations.nation_id"), nullable=False),
        sa.Column("state_code", sa.String(), nullable=False),
        sa.Column("state_name", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("state_hq", sa.String(), nullable=True),
        sa.Column("state_pastor", sa.String(), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("nation_id", "state_code", name="uq_states_nation_code"),
    )
    op.execute("ALTER TABLE states ALTER COLUMN path TYPE ltree USING path::ltree")
    op.create_index("ix_states_nation_id", "states", ["nation_id"])
    op.create_index("ix_states_state_code", "states", ["state_code"])
    op.create_index("ix_states_created_by", "states", ["created_by"])
    op.create_index("ix_states_path", "states", ["path"], postgresql_using="gist")

    op.create_table(
        "regions",
        sa.Column("region_id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("state_id", postgresql.UUID(), sa.ForeignKey("states.state_id"), nullable=False),
        sa.Column("region_code", sa.String(), nullable=False),
        sa.Column("region_name", sa.String(), nullable=False),
        sa.Column("region_head", sa.String(), nullable=True),
        sa.Column("regional_pastor", sa.String(), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("state_id", "region_code", name="uq_regions_state_code"),
    )
    op.execute("ALTER TABLE regions ALTER COLUMN path TYPE ltree USING path::ltree")
    op.create_index("ix_regions_state_id", "regions", ["state_id"])
    op.create_index("ix_regions_region_code", "regions", ["region_code"])
    op.create_index("ix_regions_created_by", "regions", ["created_by"])
    op.create_index("ix_regions_path", "regions", ["path"], postgresql_using="gist")

    op.create_table(
        "dclm_groups",
        sa.Column("group_id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("region_id", postgresql.UUID(), sa.ForeignKey("regions.region_id"), nullable=False),
        sa.Column("group_code", sa.String(), nullable=False),
        sa.Column("group_name", sa.String(), nullable=False),
        sa.Column("group_head", sa.String(), nullable=True),
        sa.Column("group_pastor", sa.String(), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("region_id", "group_code", name="uq_groups_region_code"),
    )
    op.execute("ALTER TABLE dclm_groups ALTER COLUMN path TYPE ltree USING path::ltree")
    op.create_index("ix_dclm_groups_region_id", "dclm_groups", ["region_id"])
    op.create_index("ix_dclm_groups_group_code", "dclm_groups", ["group_code"])
    op.create_index("ix_dclm_groups_created_by", "dclm_groups", ["created_by"])
    op.create_index("ix_dclm_groups_path", "dclm_groups", ["path"], postgresql_using="gist")

    op.create_table(
        "locations",
        sa.Column("location_id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_id", postgresql.UUID(), sa.ForeignKey("dclm_groups.group_id"), nullable=False),
        sa.Column("location_code", sa.String(), nullable=False),
        sa.Column("location_name", sa.String(), nullable=False),
        sa.Column("church_type", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("associate_cord", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("group_id", "location_code", name="uq_locations_group_code"),
    )
    op.execute("ALTER TABLE locations ALTER COLUMN path TYPE ltree USING path::ltree")
    op.create_index("ix_locations_group_id", "locations", ["group_id"])
    op.create_index("ix_locations_location_code", "locations", ["location_code"])
    op.create_index("ix_locations_created_by", "locations", ["created_by"])
    op.create_index("ix_locations_path", "locations", ["path"], postgresql_using="gist")

    op.create_table(
        "fellowships",
        sa.Column("fellowship_id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("location_id", postgresql.UUID(), sa.ForeignKey("locations.location_id"), nullable=False),
        sa.Column("fellowship_code", sa.String(), nullable=False),
        sa.Column("fellowship_name", sa.String(), nullable=False),
        sa.Column("fellowship_address", sa.String(), nullable=True),
        sa.Column("associate_church", sa.String(), nullable=True),
        sa.Column("location_name", sa.String(), nullable=True),
        sa.Column("church_type", sa.String(), nullable=True),
        sa.Column("leader_in_charge", sa.String(), nullable=True),
        sa.Column("leader_contact", sa.String(), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("location_id", "fellowship_code", name="uq_fellowships_location_code"),
    )
    op.execute("ALTER TABLE fellowships ALTER COLUMN path TYPE ltree USING path::ltree")
    op.create_index("ix_fellowships_location_id", "fellowships", ["location_id"])
    op.create_index("ix_fellowships_fellowship_code", "fellowships", ["fellowship_code"])
    op.create_index("ix_fellowships_created_by", "fellowships", ["created_by"])
    op.create_index("ix_fellowships_path", "fellowships", ["path"], postgresql_using="gist")


def _restore_location_foreign_keys(inspector) -> None:
    if _table_exists(inspector, "workers") and _column_exists(inspector, "workers", "location_id"):
        op.create_foreign_key("fk_workers_location_id_locations", "workers", "locations", ["location_id"], ["location_id"], ondelete="RESTRICT")
    if _table_exists(inspector, "location_profiles") and _column_exists(inspector, "location_profiles", "location_id"):
        op.create_foreign_key("fk_location_profiles_location_id_locations", "location_profiles", "locations", ["location_id"], ["location_id"], ondelete="CASCADE")
    if _table_exists(inspector, "church_members") and _column_exists(inspector, "church_members", "location_id"):
        op.create_foreign_key("fk_church_members_location_id_locations", "church_members", "locations", ["location_id"], ["location_id"], ondelete="RESTRICT")
    if _table_exists(inspector, "church_members") and _column_exists(inspector, "church_members", "fellowship_id"):
        op.create_foreign_key("fk_church_members_fellowship_id_fellowships", "church_members", "fellowships", ["fellowship_id"], ["fellowship_id"], ondelete="SET NULL")
    if _table_exists(inspector, "worker_transfers"):
        op.create_foreign_key("fk_worker_transfers_from_location_id_locations", "worker_transfers", "locations", ["from_location_id"], ["location_id"], ondelete="RESTRICT")
        op.create_foreign_key("fk_worker_transfers_to_location_id_locations", "worker_transfers", "locations", ["to_location_id"], ["location_id"], ondelete="RESTRICT")


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if _column_exists(inspector, "nations", "nation_code"):
        return
    if not _table_exists(inspector, "nations"):
        return

    _require_empty_dependents(inspector)
    _drop_old_hierarchy_tables()
    inspector = inspect(op.get_bind())
    _alter_location_reference_columns(inspector)
    _create_hierarchy_tables()
    inspector = inspect(op.get_bind())
    _restore_location_foreign_keys(inspector)


def downgrade() -> None:
    raise RuntimeError("Downgrade is not supported for the hierarchy UUID/local-code migration.")
