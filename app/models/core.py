"""
Core model mixins and utilities for database models.
"""
from sqlalchemy import Column, DateTime, Boolean, String, Integer, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import UserDefinedType
from typing import List
import uuid
import re


from sqlalchemy import TypeDecorator, cast, String
from sqlalchemy.types import UserDefinedType

class _LTREE(UserDefinedType):
    def get_col_spec(self, **kw):
        return "LTREE"


class LtreeType(TypeDecorator):
    """
    Custom SQLAlchemy type for PostgreSQL ltree.
    Automatically casts to String on SELECT to ensure asyncpg compatibility.
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        # We want SQLAlchemy to treat this as a String at runtime (for result processing)
        # Even for Postgres, because asyncpg needs it to be a known type (String)
        # after we CAST it to varchar in column_expression.
        return dialect.type_descriptor(String)

    def column_expression(self, col):
        # Force cast to text/string when selecting from DB
        return cast(col, String)
    
    def bind_expression(self, bindvalue):
        # Cast input string to ltree for INSERT/UPDATE
        return cast(bindvalue, _LTREE())


class TimestampMixin:
    """Mixin for created_at and last_modify timestamps."""
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    last_modify = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    operation = Column(
        String,
        nullable=False,
        index=True,
        default="CREATE"
    )  # CREATE, UPDATE, DELETE


class AuditMixin:
    """Mixin for audit fields."""
    
    created_by = Column(
        UUID(as_uuid=True),
        nullable=True,  # Nullable for system-created records
        index=True
    )
    version = Column(Integer, default=1, nullable=False)  # Optimistic locking


class LTreePathMixin:
    """Mixin for hierarchical path using ltree."""
    
    path = Column(LtreeType, nullable=False, index=True)


# Utility functions for ltree path generation

def generate_ltree_path(segments: List[str]) -> str:
    """
    Generate ltree path from segments.
    
    Args:
        segments: List of path segments (e.g., ['org', '234', 'kw', 'iln', 'ile', '001'])
    
    Returns:
        str: ltree path (e.g., 'org.234.kw.iln.ile.001')
    
    Example:
        >>> generate_ltree_path(['org', '234', 'kw'])
        'org.234.kw'
    """
    # Validate segments (ltree labels must be alphanumeric + underscore, max 256 chars)
    for segment in segments:
        if not re.match(r'^[a-zA-Z0-9_]+$', segment):
            raise ValueError(f"Invalid ltree segment: {segment}")
        if len(segment) > 256:
            raise ValueError(f"ltree segment too long: {segment}")
    
    return '.'.join(segments)


def generate_display_id(path: str) -> str:
    """
    Generate human-readable display ID from ltree path.
    
    Args:
        path: ltree path (e.g., 'org.234.kw.iln.ile.001')
    
    Returns:
        str: Display ID (e.g., 'DCM-234-KW-ILN-ILE-001')
    
    Example:
        >>> generate_display_id('org.234.kw.iln.ile.001')
        'DCM-234-KW-ILN-ILE-001'
    """
    segments = path.split('.')
    
    # Replace 'org' with 'DCM' (Deeper Christian Ministry)
    if segments[0] == 'org':
        segments[0] = 'DCM'
    
    # Uppercase all segments
    segments = [seg.upper() for seg in segments]
    
    return '-'.join(segments)


def parse_display_id(display_id: str) -> str:
    """
    Parse display ID back to ltree path.
    
    Args:
        display_id: Display ID (e.g., 'DCM-234-KW-ILN-ILE-001')
    
    Returns:
        str: ltree path (e.g., 'org.234.kw.iln.ile.001')
    
    Example:
        >>> parse_display_id('DCM-234-KW-ILN-ILE-001')
        'org.234.kw.iln.ile.001'
    """
    segments = display_id.split('-')
    
    # Replace 'DCM' with 'org'
    if segments[0] == 'DCM':
        segments[0] = 'org'
    
    # Lowercase all segments
    segments = [seg.lower() for seg in segments]
    
    return '.'.join(segments)


def validate_path(path: str) -> bool:
    """
    Validate ltree path format.
    
    Args:
        path: ltree path to validate
    
    Returns:
        bool: True if valid
    """
    if not path:
        return False
    
    segments = path.split('.')
    
    for segment in segments:
        # Check if segment matches ltree label rules
        if not re.match(r'^[a-zA-Z0-9_]+$', segment):
            return False
        if len(segment) > 256:
            return False
    
    return True


def get_path_level(path: str) -> int:
    """
    Get the level/depth of a path.
    
    Args:
        path: ltree path
    
    Returns:
        int: Path level (number of segments)
    
    Example:
        >>> get_path_level('org.234.kw')
        3
    """
    return len(path.split('.'))


def get_parent_path(path: str) -> str | None:
    """
    Get parent path from a given path.
    
    Args:
        path: ltree path
    
    Returns:
        str | None: Parent path, or None if root
    
    Example:
        >>> get_parent_path('org.234.kw.iln.ile.001')
        'org.234.kw.iln.ile'
    """
    segments = path.split('.')
    if len(segments) <= 1:
        return None
    return '.'.join(segments[:-1])
