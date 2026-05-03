"""
RefreshToken model — tracks issued refresh tokens in Postgres.

Used for token rotation: every time a refresh token is consumed, the old JTI
is revoked and a new token (with a new JTI) is issued.  This ensures a stolen
refresh token cannot be reused after the legitimate user has refreshed once.

No Redis or external service is required — Postgres is the single source of
truth for token validity.

A migration must be run (or `Base.metadata.create_all` called at startup) to
create this table before the auth routes are usable.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.core import TimestampMixin


class RefreshToken(Base, TimestampMixin):
    """
    Persisted record of every issued refresh token.

    Fields
    ------
    jti         Unique JWT ID embedded in the token payload.
    user_id     Owner of the token.
    expires_at  When the token naturally expires (mirrors JWT exp claim).
    revoked     Set to True when the token has been consumed (rotated) or
                explicitly invalidated (logout / security event).
    revoked_at  Timestamp of revocation for audit purposes.
    """

    __tablename__ = "refresh_tokens"

    # Primary key is the JTI itself — no surrogate needed, already unique.
    jti = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship — optional, useful for user.refresh_tokens queries
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        # Fast lookup: "is this jti still valid?"
        Index("ix_refresh_tokens_jti_revoked", "jti", "revoked"),
        # Housekeeping: find all tokens for a user (e.g., logout-all)
        Index("ix_refresh_tokens_user_id_revoked", "user_id", "revoked"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RefreshToken jti={self.jti} user_id={self.user_id} "
            f"revoked={self.revoked}>"
        )

    @property
    def is_expired(self) -> bool:
        """True if the token's natural expiry has passed."""
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        """True only when the token is neither revoked nor expired."""
        return not self.revoked and not self.is_expired
