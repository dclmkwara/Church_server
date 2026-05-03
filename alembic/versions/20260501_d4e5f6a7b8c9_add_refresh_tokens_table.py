"""add refresh_tokens table for secure token rotation

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-01 16:00:00.000000

This migration creates the refresh_tokens table used by the token rotation
system introduced in the auth security hardening pass.

Each issued refresh token's JTI (JWT ID) is stored here.  On every token
refresh call:
  1. The presented JTI is looked up and validated (not revoked, not expired).
  2. The old record is marked revoked.
  3. A new token with a fresh JTI is issued and stored.

This prevents replay attacks: a stolen refresh token can only be used once.
When the legitimate holder next refreshes, the attacker's copy is already
revoked.

No external service (Redis, etc.) is required — Postgres is the single source
of truth.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'refresh_tokens',
        # JTI is the primary key — it is already a UUID embedded in the token
        sa.Column('jti', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.user_id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        # TimestampMixin columns
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            onupdate=sa.text('now()'),
            nullable=False,
        ),
    )

    # Index: fast JTI + revoked lookups (the hot path on every /auth/refresh)
    op.create_index(
        'ix_refresh_tokens_jti_revoked',
        'refresh_tokens',
        ['jti', 'revoked'],
    )
    # Index: find / revoke all tokens for a user (logout-all, account lock)
    op.create_index(
        'ix_refresh_tokens_user_id_revoked',
        'refresh_tokens',
        ['user_id', 'revoked'],
    )
    # Index: efficient expiry cleanup job (DELETE WHERE expires_at < NOW())
    op.create_index(
        'ix_refresh_tokens_expires_at',
        'refresh_tokens',
        ['expires_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_refresh_tokens_expires_at', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_user_id_revoked', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_jti_revoked', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
