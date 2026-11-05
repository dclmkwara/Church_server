"""
Shared database filter helpers used across service and route layers.

Having _scope_filter in one place eliminates 5 identical copies that
previously lived in statistics_service.py, dashboard_service.py,
notification_service.py, dashboard.py (route), and reports.py.
"""
from sqlalchemy import String, and_, cast, func, literal, literal_column, or_
from contextvars import ContextVar, Token
from app.models.core import _LTREE

_scope_context: ContextVar[tuple[int, tuple[str, ...]]] = ContextVar(
    "church_scope_context", default=(0, ())
)


def set_scope_context(role_score: int, nation_paths: tuple[str, ...] = ()) -> Token:
    """Set request-local role metadata used by shared SQL scope filters."""
    return _scope_context.set((role_score, tuple(nation_paths)))


def reset_scope_context(token: Token | None = None) -> Token:
    """Reset request-local scope metadata to its prior/default value."""
    if token is None:
        return _scope_context.set((0, ()))
    _scope_context.reset(token)
    return token


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
    path_scope = ltree_col.op("<@")(ltree_scope)

    role_score, nation_paths = _scope_context.get()
    if role_score not in (8, 9):
        return path_scope
    if role_score == 9:
        return path_scope
    # For score 9 the global path is intentionally unrestricted; score 8 is
    # further filtered to the user's resolved continent below.
    if not nation_paths:
        # Missing continental context must fail closed.
        return and_(path_scope, literal(False))
    nation_prefix = cast(func.subpath(ltree_col, literal(0), literal(2)), String)
    return and_(path_scope, nation_prefix.in_(nation_paths))


def scope_or_ancestor_filter(column, scope_path: str):
    """Include in-scope descendants and their ancestor records safely."""
    role_score, nation_paths = _scope_context.get()
    if role_score == 8:
        # A continent user has `org` as a query envelope. Ancestor matching
        # against that envelope would expose every campaign globally.
        return scope_filter(column, scope_path)
    path = ltree_column(column)
    scope = cast(scope_path, _LTREE())
    return or_(path.op("<@")(scope), scope.op("<@")(path))
