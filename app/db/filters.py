"""
Shared database filter helpers used across service and route layers.

Having _scope_filter in one place eliminates 5 identical copies that
previously lived in statistics_service.py, dashboard_service.py,
notification_service.py, dashboard.py (route), and reports.py.
"""
from sqlalchemy import cast
from app.models.core import _LTREE


def scope_filter(column, scope_path: str):
    """
    Build an ltree ancestor-or-self filter.

    Returns an SQLAlchemy clause that is True when *column* is equal to
    *scope_path* OR is a descendant of it (i.e. ``column <@ scope_path``).

    Usage::

        .where(scope_filter(Count.path, effective_scope))
    """
    ltree_col = cast(column, _LTREE())
    ltree_scope = cast(scope_path, _LTREE())
    return ltree_col.op("<@")(ltree_scope) | (ltree_col == ltree_scope)
