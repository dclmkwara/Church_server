"""
User and authentication related database models.

This module contains all models related to user management, authentication,
workers, roles, permissions, and RBAC.
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, AuditMixin, LTreePathMixin


# Junction tables for many-to-many relationships
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
)

user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
)


class RoleScore(Base, TimestampMixin, SoftDeleteMixin):
    """
    Role score model for hierarchical access levels (1-9).
    
    Score hierarchy:
        1-2: Worker/Usher (location level)
        3: Location Pastor (location level)
        4: Group Pastor (group level)
        5: Regional Pastor (regional level)
        6: State Pastor (state level)
        7: National Admin (national level)
        8: Continental Leader (continental level)
        9: Global Admin (global level)
    """
    __tablename__ = "role_scores"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    score = Column(Integer, unique=True, nullable=False, index=True)
    score_name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    
    # Relationships
    roles = relationship("Role", back_populates="score")
    
    def __repr__(self):
        return f"<RoleScore(score={self.score}, name='{self.score_name}')>"


class Permission(Base, TimestampMixin, SoftDeleteMixin):
    """
    Permission model for defining granular permissions.
    
    Permissions are assigned to roles, which are then assigned to users.
    """
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    permission = Column(String, unique=True, nullable=False, index=True)  # e.g., 'counts:create'
    name = Column(String, nullable=False)  # Human-readable name
    description = Column(String, nullable=True)
    
    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    
    def __repr__(self):
        return f"<Permission(permission='{self.permission}')>"


class Role(Base, TimestampMixin, SoftDeleteMixin):
    """
    Role model for user roles.
    
    Each role has a score that determines hierarchical access level.
    """
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    score_id = Column(Integer, ForeignKey("role_scores.id"), nullable=False, index=True)
    
    # Relationships
    score = relationship("RoleScore", back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship("User", secondary=user_roles, back_populates="roles")
    
    @property
    def score_value(self) -> int:
        """Helper to get integer score value."""
        return self.score.score if self.score else 0

    def __repr__(self):
        return f"<Role(name='{self.role_name}', score={self.score.score if self.score else None})>"


class Worker(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Worker model - Church workers registry.
    
    This is the primary table for all church workers. Workers must be registered
    here BEFORE they can be assigned as application users.
    
    Key points:
    - Workers are registered through the system website
    - Only after worker registration can they become app users
    - This is the canonical source for worker information
    """
    __tablename__ = "workers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True, default=uuid.uuid4)
    user_id = Column(String, unique=True, nullable=False, index=True)  # Custom ID (e.g., W001)
    
    # Location information - STRICT ENFORCEMENT: Worker MUST belong to a location
    location_id = Column(
        String, 
        ForeignKey("locations.location_id", ondelete="RESTRICT"),  # Prevent location deletion if workers exist
        nullable=False,  # REQUIRED field
        index=True
    )
    location_name = Column(String, nullable=False, index=True)  # Denormalized for quick access
    church_type = Column(String, nullable=False, index=True)  # DLBC, DLCF, DLSO
    state = Column(String, nullable=False)
    region = Column(String, nullable=False, index=True)
    group = Column(String, nullable=False, index=True)
    
    # Personal information
    name = Column(String, nullable=False)
    gender = Column(String, nullable=False)  # Male, Female
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    address = Column(String, nullable=True)
    occupation = Column(String, nullable=True)
    marital_status = Column(String, nullable=True)  # Single, Married, Widowed, Divorced
    
    # Worker details
    unit = Column(String, nullable=False)  # Ushering, Choir, etc.
    status = Column(String, nullable=True, index=True)  # Active, Inactive, Suspended
    
    # Relationships
    user = relationship("User", back_populates="worker", uselist=False)  # One-to-one
    location = relationship("Location", foreign_keys=[location_id])  # Link to Location table
    # attendance_records = relationship("WorkerAttendance", back_populates="worker")
    
    __table_args__ = (
        UniqueConstraint('phone', name='uq_worker_phone'),
        UniqueConstraint('email', name='uq_worker_email'),
    )
    
    def __repr__(self):
        return f"<Worker(user_id='{self.user_id}', name='{self.name}', phone='{self.phone}')>"


class User(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    User model - Application users for authentication.
    
    This table is strictly for authentication. Users are created AFTER worker
    registration and only assigned users can access the application.
    
    Key points:
    - Depends on Worker table (worker must exist first)
    - Used for authentication only
    - Profile data comes from Worker table
    - Only assigned users can access the application
    """
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.worker_id"), unique=True, nullable=False, index=True)
    
    # Authentication
    password = Column(String, nullable=False)  # Hashed password
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Approval Workflow - NEW: Users must be approved by location admin before full access
    approval_status = Column(
        String, 
        nullable=False, 
        default="pending",  # pending, approved, rejected
        index=True
    )
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)  # Admin who approved
    approved_at = Column(DateTime(timezone=True), nullable=True)  # When approved
    rejection_reason = Column(String, nullable=True)  # If rejected, why?
    
    # Inherited from worker (denormalized for quick access)
    location_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    
    # Relationships
    worker = relationship("Worker", back_populates="user", foreign_keys=[worker_id])
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user")
    approver = relationship("User", remote_side=[user_id], foreign_keys=[approved_by])  # Self-referential
    
    __table_args__ = (
        UniqueConstraint('worker_id', name='uq_user_worker'),
        UniqueConstraint('phone', name='uq_user_phone'),
        UniqueConstraint('email', name='uq_user_email'),
    )
    
    def __repr__(self):
        return f"<User(name='{self.name}', phone='{self.phone}', active={self.is_active}, status='{self.approval_status}')>"


class PasswordResetToken(Base, TimestampMixin):
    """
    Password reset token model.
    
    Stores tokens for password recovery with security questions.
    """
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    expiration = Column(Integer, nullable=False)  # Unix timestamp
    
    # Security questions (optional)
    recovery_question_one = Column(String, nullable=True)
    recovery_question_two = Column(String, nullable=True)
    recovery_answer_one = Column(String, nullable=True)  # Hashed
    recovery_answer_two = Column(String, nullable=True)  # Hashed
    
    is_used = Column(Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")
    
    def __repr__(self):
        return f"<PasswordResetToken(user_id={self.user_id}, used={self.is_used})>"



