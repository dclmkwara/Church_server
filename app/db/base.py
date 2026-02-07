"""
SQLAlchemy declarative base and model imports.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Import all models here for Alembic auto-detection
# from app.models import *  # noqa - Removed to avoid circular imports
