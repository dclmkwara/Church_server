"""add official appointments

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-03-31 00:20:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'official_appointments',
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('worker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('worker_name', sa.String(), nullable=False),
        sa.Column('location_id', sa.String(), nullable=False),
        sa.Column('location_name', sa.String(), nullable=False),
        sa.Column('appointed_role', sa.String(), nullable=False),
        sa.Column('assigned_scope_label', sa.String(), nullable=False),
        sa.Column('appointment_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('note', sa.String(), nullable=True),
        sa.Column('appointed_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('appointed_by_name', sa.String(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('revoked_note', sa.String(), nullable=True),
        sa.Column('path', postgresql.TEXT(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_modify', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('operation', sa.String(), server_default='CREATE', nullable=False),
        sa.ForeignKeyConstraint(['appointed_by_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['revoked_by_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.worker_id']),
        sa.PrimaryKeyConstraint('appointment_id'),
        sa.UniqueConstraint('worker_id', 'appointed_role', 'path', name='uq_official_appointment_worker_role_path'),
    )
    op.create_index(op.f('ix_official_appointments_worker_id'), 'official_appointments', ['worker_id'], unique=False)
    op.create_index(op.f('ix_official_appointments_worker_name'), 'official_appointments', ['worker_name'], unique=False)
    op.create_index(op.f('ix_official_appointments_location_id'), 'official_appointments', ['location_id'], unique=False)
    op.create_index(op.f('ix_official_appointments_appointed_role'), 'official_appointments', ['appointed_role'], unique=False)
    op.create_index(op.f('ix_official_appointments_appointment_date'), 'official_appointments', ['appointment_date'], unique=False)
    op.create_index(op.f('ix_official_appointments_status'), 'official_appointments', ['status'], unique=False)
    op.create_index(op.f('ix_official_appointments_appointed_by_id'), 'official_appointments', ['appointed_by_id'], unique=False)
    op.create_index(op.f('ix_official_appointments_revoked_by_id'), 'official_appointments', ['revoked_by_id'], unique=False)
    op.create_index(op.f('ix_official_appointments_path'), 'official_appointments', ['path'], unique=False)
    op.create_index(op.f('ix_official_appointments_is_deleted'), 'official_appointments', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_official_appointments_operation'), 'official_appointments', ['operation'], unique=False)
    op.alter_column('official_appointments', 'status', server_default=None)
    op.alter_column('official_appointments', 'operation', server_default=None)


def downgrade() -> None:
    op.drop_index(op.f('ix_official_appointments_operation'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_is_deleted'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_path'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_revoked_by_id'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_appointed_by_id'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_status'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_appointment_date'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_appointed_role'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_location_id'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_worker_name'), table_name='official_appointments')
    op.drop_index(op.f('ix_official_appointments_worker_id'), table_name='official_appointments')
    op.drop_table('official_appointments')
