"""
Shared database filter helpers used across service and route layers.

Having _scope_filter in one place eliminates 5 identical copies that
previously lived in statistics_service.py, dashboard_service.py,
notification_service.py, dashboard.py (route), and reports.py.
"""
from sqlalchemy import cast, func, literal_column
from app.models.core import _LTREE


def _raw_column(column):
    """Return the underlying table column, bypassing TypeDecorator select casts."""
    prop = getattr(column, "property", None)
    columns = getattr(prop, "columns", None)
    if columns:
        return columns[0]
    return column


def ltree_column(column):
    """Return a qualified ltree cast for a model path column."""
    return cast(_raw_column(column), _LTREE())


def ltree_subpath(column, segment_count: int):
    """Return a stable ltree subpath expression for hierarchy grouping."""
    return func.subpath(ltree_column(column), literal_column("0"), literal_column(str(segment_count)))


def scope_filter(column, scope_path: str):
    """
    Build an ltree ancestor-or-self filter.

    Returns an SQLAlchemy clause that is True when *column* is equal to
    *scope_path* OR is a descendant of it (i.e. ``column <@ scope_path``).

    Usage::

        .where(scope_filter(Count.path, effective_scope))
    """
    ltree_col = ltree_column(column)
    ltree_scope = cast(scope_path, _LTREE())
    return ltree_col.op("<@")(ltree_scope) | (ltree_col == ltree_scope)
