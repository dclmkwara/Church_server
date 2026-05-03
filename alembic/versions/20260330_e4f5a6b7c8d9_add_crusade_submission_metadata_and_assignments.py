"""add crusade submission metadata and assignments

Revision ID: e4f5a6b7c8d9
Revises: d1e2f3a4b5c6
Create Date: 2026-03-30 19:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e4f5a6b7c8d9'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('event_assignments', sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False), sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False), sa.Column('worker_id', postgresql.UUID(as_uuid=True), nullable=False), sa.Column('path', postgresql.TEXT(), nullable=False), sa.Column('assignment_label', sa.String(), nullable=True), sa.Column('assignment_type', sa.String(), nullable=False, server_default='both'), sa.Column('source_role', sa.String(), nullable=False, server_default='alpha'), sa.Column('status', sa.String(), nullable=False, server_default='pending'), sa.Column('note', sa.Text(), nullable=True), sa.Column('assigned_by_id', postgresql.UUID(as_uuid=True), nullable=False), sa.Column('approved_by_id', postgresql.UUID(as_uuid=True), nullable=True), sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True), sa.Column('submission_completed', sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=True), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()), sa.ForeignKeyConstraint(['approved_by_id'], ['users.user_id']), sa.ForeignKeyConstraint(['assigned_by_id'], ['users.user_id']), sa.ForeignKeyConstraint(['event_id'], ['program_events.id']), sa.ForeignKeyConstraint(['worker_id'], ['workers.worker_id']), sa.PrimaryKeyConstraint('id'), sa.UniqueConstraint('event_id', 'worker_id', name='uq_event_assignment_event_worker'))
    op.create_index(op.f('ix_event_assignments_event_id'), 'event_assignments', ['event_id'], unique=False)
    op.create_index(op.f('ix_event_assignments_worker_id'), 'event_assignments', ['worker_id'], unique=False)
    op.create_index(op.f('ix_event_assignments_path'), 'event_assignments', ['path'], unique=False)
    op.create_index(op.f('ix_event_assignments_assignment_label'), 'event_assignments', ['assignment_label'], unique=False)
    op.create_index(op.f('ix_event_assignments_assignment_type'), 'event_assignments', ['assignment_type'], unique=False)
    op.create_index(op.f('ix_event_assignments_source_role'), 'event_assignments', ['source_role'], unique=False)
    op.create_index(op.f('ix_event_assignments_status'), 'event_assignments', ['status'], unique=False)
    op.create_index(op.f('ix_event_assignments_submission_completed'), 'event_assignments', ['submission_completed'], unique=False)
    op.add_column('counts', sa.Column('assignment_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('counts', sa.Column('source_role', sa.String(), nullable=False, server_default='regular'))
    op.add_column('counts', sa.Column('campaign_code', sa.String(), nullable=True))
    op.add_column('counts', sa.Column('submission_channel', sa.String(), nullable=False, server_default='admin_web'))
    op.create_foreign_key(None, 'counts', 'event_assignments', ['assignment_id'], ['id'])
    op.create_index(op.f('ix_counts_assignment_id'), 'counts', ['assignment_id'], unique=False)
    op.create_index(op.f('ix_counts_source_role'), 'counts', ['source_role'], unique=False)
    op.create_index(op.f('ix_counts_campaign_code'), 'counts', ['campaign_code'], unique=False)
    op.create_index(op.f('ix_counts_submission_channel'), 'counts', ['submission_channel'], unique=False)
    op.add_column('records', sa.Column('assignment_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('records', sa.Column('source_role', sa.String(), nullable=False, server_default='regular'))
    op.add_column('records', sa.Column('campaign_code', sa.String(), nullable=True))
    op.add_column('records', sa.Column('submission_channel', sa.String(), nullable=False, server_default='admin_web'))
    op.create_foreign_key(None, 'records', 'event_assignments', ['assignment_id'], ['id'])
    op.create_index(op.f('ix_records_assignment_id'), 'records', ['assignment_id'], unique=False)
    op.create_index(op.f('ix_records_source_role'), 'records', ['source_role'], unique=False)
    op.create_index(op.f('ix_records_campaign_code'), 'records', ['campaign_code'], unique=False)
    op.create_index(op.f('ix_records_submission_channel'), 'records', ['submission_channel'], unique=False)
    op.alter_column('event_assignments', 'assignment_type', server_default=None)
    op.alter_column('event_assignments', 'source_role', server_default=None)
    op.alter_column('event_assignments', 'status', server_default=None)
    op.alter_column('event_assignments', 'submission_completed', server_default=None)
    op.alter_column('counts', 'source_role', server_default=None)
    op.alter_column('counts', 'submission_channel', server_default=None)
    op.alter_column('records', 'source_role', server_default=None)
    op.alter_column('records', 'submission_channel', server_default=None)

def downgrade() -> None:
    op.drop_index(op.f('ix_records_submission_channel'), table_name='records')
    op.drop_index(op.f('ix_records_campaign_code'), table_name='records')
    op.drop_index(op.f('ix_records_source_role'), table_name='records')
    op.drop_index(op.f('ix_records_assignment_id'), table_name='records')
    op.drop_constraint(None, 'records', type_='foreignkey')
    op.drop_column('records', 'submission_channel')
    op.drop_column('records', 'campaign_code')
    op.drop_column('records', 'source_role')
    op.drop_column('records', 'assignment_id')
    op.drop_index(op.f('ix_counts_submission_channel'), table_name='counts')
    op.drop_index(op.f('ix_counts_campaign_code'), table_name='counts')
    op.drop_index(op.f('ix_counts_source_role'), table_name='counts')
    op.drop_index(op.f('ix_counts_assignment_id'), table_name='counts')
    op.drop_constraint(None, 'counts', type_='foreignkey')
    op.drop_column('counts', 'submission_channel')
    op.drop_column('counts', 'campaign_code')
    op.drop_column('counts', 'source_role')
    op.drop_column('counts', 'assignment_id')
    op.drop_index(op.f('ix_event_assignments_submission_completed'), table_name='event_assignments')
    op.drop_index(op.f('ix_event_assignments_status'), table_name='event_assignments')
    op.drop_index(op.f('ix_event_assignments_source_role'), table_name='event_assignments')
    op.drop_index(op.f('ix_event_assignments_assignment_type'), table_name='event_assignments')
    op.drop_index(op.f('ix_event_assignments_assignment_label'), table_name='event_assignments')
    op.drop_index(op.f('ix_event_assignments_path'), table_name='event_assignments')
    op.drop_index(op.f('ix_event_assignments_worker_id'), table_name='event_assignments')
    op.drop_index(op.f('ix_event_assignments_event_id'), table_name='event_assignments')
    op.drop_table('event_assignments')
