"""add program campaigns

Revision ID: f7a8b9c0d1e2
Revises: e4f5a6b7c8d9
Create Date: 2026-03-30 21:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'f7a8b9c0d1e2'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('program_campaigns', sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False), sa.Column('domain_id', sa.Integer(), nullable=False), sa.Column('path', postgresql.TEXT(), nullable=False), sa.Column('campaign_code', sa.String(), nullable=False), sa.Column('title', sa.String(), nullable=False), sa.Column('description', sa.Text(), nullable=True), sa.Column('event_mode', sa.String(), nullable=False, server_default='special'), sa.Column('reporting_scope', sa.String(), nullable=False, server_default='global'), sa.Column('status', sa.String(), nullable=False, server_default='draft'), sa.Column('alpha_location_id', sa.String(), nullable=True), sa.Column('start_date', sa.Date(), nullable=False), sa.Column('end_date', sa.Date(), nullable=False), sa.Column('collection_window_start', sa.DateTime(timezone=True), nullable=True), sa.Column('collection_window_end', sa.DateTime(timezone=True), nullable=True), sa.Column('flyer_url', sa.String(), nullable=True), sa.Column('publicity_note', sa.Text(), nullable=True), sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=True), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()), sa.ForeignKeyConstraint(['created_by_id'], ['users.user_id']), sa.ForeignKeyConstraint(['domain_id'], ['program_domains.id']), sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_program_campaigns_domain_id'), 'program_campaigns', ['domain_id'], unique=False)
    op.create_index(op.f('ix_program_campaigns_path'), 'program_campaigns', ['path'], unique=False)
    op.create_index(op.f('ix_program_campaigns_campaign_code'), 'program_campaigns', ['campaign_code'], unique=True)
    op.create_index(op.f('ix_program_campaigns_title'), 'program_campaigns', ['title'], unique=False)
    op.create_index(op.f('ix_program_campaigns_event_mode'), 'program_campaigns', ['event_mode'], unique=False)
    op.create_index(op.f('ix_program_campaigns_reporting_scope'), 'program_campaigns', ['reporting_scope'], unique=False)
    op.create_index(op.f('ix_program_campaigns_status'), 'program_campaigns', ['status'], unique=False)
    op.create_index(op.f('ix_program_campaigns_alpha_location_id'), 'program_campaigns', ['alpha_location_id'], unique=False)
    op.create_index(op.f('ix_program_campaigns_start_date'), 'program_campaigns', ['start_date'], unique=False)
    op.create_index(op.f('ix_program_campaigns_end_date'), 'program_campaigns', ['end_date'], unique=False)
    op.add_column('program_events', sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(None, 'program_events', 'program_campaigns', ['campaign_id'], ['id'])
    op.create_index(op.f('ix_program_events_campaign_id'), 'program_events', ['campaign_id'], unique=False)
    op.alter_column('program_campaigns', 'event_mode', server_default=None)
    op.alter_column('program_campaigns', 'reporting_scope', server_default=None)
    op.alter_column('program_campaigns', 'status', server_default=None)

def downgrade() -> None:
    op.drop_index(op.f('ix_program_events_campaign_id'), table_name='program_events')
    op.drop_constraint(None, 'program_events', type_='foreignkey')
    op.drop_column('program_events', 'campaign_id')
    op.drop_index(op.f('ix_program_campaigns_end_date'), table_name='program_campaigns')
    op.drop_index(op.f('ix_program_campaigns_start_date'), table_name='program_campaigns')
    op.drop_index(op.f('ix_program_campaigns_alpha_location_id'), table_name='program_campaigns')
    op.drop_index(op.f('ix_program_campaigns_status'), table_name='program_campaigns')
    op.drop_index(op.f('ix_program_campaigns_reporting_scope'), table_name='program_campaigns')
    op.drop_index(op.f('ix_program_campaigns_event_mode'), table_name='program_campaigns')
    op.drop_index(op.f('ix_program_campaigns_title'), table_name='program_campaigns')
    op.drop_index(op.f('ix_program_campaigns_campaign_code'), table_name='program_campaigns')
    op.drop_index(op.f('ix_program_campaigns_path'), table_name='program_campaigns')
    op.drop_index(op.f('ix_program_campaigns_domain_id'), table_name='program_campaigns')
    op.drop_table('program_campaigns')
