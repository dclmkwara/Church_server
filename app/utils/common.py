"""
Common utility functions.
"""
from datetime import datetime, timedelta
from typing import Optional
from app.core.config import settings


def is_within_edit_window(created_at: datetime) -> tuple[bool, Optional[str]]:
    """
    Check if a record is within the edit window.
    
    Args:
        created_at: Record creation timestamp
    
    Returns:
        tuple: (is_editable, warning_message)
            - is_editable: True if within 7-day window
            - warning_message: Warning if older than 48 hours, None otherwise
    
    Example:
        >>> is_within_edit_window(datetime.utcnow() - timedelta(days=1))
        (True, None)
        >>> is_within_edit_window(datetime.utcnow() - timedelta(days=3))
        (True, 'Record is older than 48 hours')
        >>> is_within_edit_window(datetime.utcnow() - timedelta(days=8))
        (False, None)
    """
    now = datetime.utcnow()
    age = now - created_at
    
    max_window = timedelta(days=settings.MAX_EDIT_WINDOW_DAYS)
    warning_threshold = timedelta(hours=settings.EDIT_WARNING_THRESHOLD_HOURS)
    
    is_editable = age <= max_window
    warning = None
    
    if is_editable and age > warning_threshold:
        warning = f"Record is older than {settings.EDIT_WARNING_THRESHOLD_HOURS} hours"
    
    return is_editable, warning


def calculate_total_count(
    adult_male: int,
    adult_female: int,
    youth_male: int,
    youth_female: int,
    boys: int,
    girls: int
) -> int:
    """
    Calculate total count from individual categories.
    
    Args:
        adult_male: Adult male count
        adult_female: Adult female count
        youth_male: Youth male count
        youth_female: Youth female count
        boys: Boys count
        girls: Girls count
    
    Returns:
        int: Total count
    """
    return adult_male + adult_female + youth_male + youth_female + boys + girls
