"""add program event operational metadata

Revision ID: d1e2f3a4b5c6
Revises: c9d2e3f4a5b6
Create Date: 2026-03-30 17:45:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1e2f3a4b5c6'
down_revision = 'c9d2e3f4a5b6'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('program_events', sa.Column('event_mode', sa.String(), nullable=False, server_default='regular'))
    op.add_column('program_events', sa.Column('reporting_scope', sa.String(), nullable=False, server_default='location'))
    op.add_column('program_events', sa.Column('campaign_code', sa.String(), nullable=True))
    op.add_column('program_events', sa.Column('alpha_location_id', sa.String(), nullable=True))
    op.add_column('program_events', sa.Column('is_alpha_event', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('program_events', sa.Column('collection_window_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('program_events', sa.Column('collection_window_end', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_program_events_event_mode'), 'program_events', ['event_mode'], unique=False)
    op.create_index(op.f('ix_program_events_reporting_scope'), 'program_events', ['reporting_scope'], unique=False)
    op.create_index(op.f('ix_program_events_campaign_code'), 'program_events', ['campaign_code'], unique=False)
    op.create_index(op.f('ix_program_events_alpha_location_id'), 'program_events', ['alpha_location_id'], unique=False)
    op.create_index(op.f('ix_program_events_is_alpha_event'), 'program_events', ['is_alpha_event'], unique=False)
    op.alter_column('program_events', 'event_mode', server_default=None)
    op.alter_column('program_events', 'reporting_scope', server_default=None)
    op.alter_column('program_events', 'is_alpha_event', server_default=None)

def downgrade() -> None:
    op.drop_index(op.f('ix_program_events_is_alpha_event'), table_name='program_events')
    op.drop_index(op.f('ix_program_events_alpha_location_id'), table_name='program_events')
    op.drop_index(op.f('ix_program_events_campaign_code'), table_name='program_events')
    op.drop_index(op.f('ix_program_events_reporting_scope'), table_name='program_events')
    op.drop_index(op.f('ix_program_events_event_mode'), table_name='program_events')
    op.drop_column('program_events', 'collection_window_end')
    op.drop_column('program_events', 'collection_window_start')
    op.drop_column('program_events', 'is_alpha_event')
    op.drop_column('program_events', 'alpha_location_id')
    op.drop_column('program_events', 'campaign_code')
    op.drop_column('program_events', 'reporting_scope')
    op.drop_column('program_events', 'event_mode')
