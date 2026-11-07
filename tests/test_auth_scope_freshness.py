import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import deps
from app.core.auth_cache import clear_user_cache, invalidate_user_cache


def test_request_scope_is_recomputed_from_current_database_roles(monkeypatch):
    clear_user_cache()
    injected_scopes = []
    context_scopes = []
    user = SimpleNamespace(
        user_id="user-1",
        path="org.234.KW.ILR.ILE.003",
        roles=[SimpleNamespace(score_value=3)],
        is_deleted=False,
        is_active=True,
        approval_status="approved",
    )

    monkeypatch.setattr(
        deps.security,
        "verify_token",
        lambda token: {"sub": "user-1", "scope_path": "org"},
    )

    async def fake_get(db, *, id):
        assert id == "user-1"
        return user

    async def fake_inject_auth_user(db, user_id):
        assert user_id == "user-1"

    async def fake_inject_scope(db, scope_path, *, role_score, continent=None, user_id=None, nation_paths=()):
        injected_scopes.append((scope_path, role_score, continent, user_id, nation_paths))

    monkeypatch.setattr(deps.crud_user, "get", fake_get)
    monkeypatch.setattr(deps, "inject_auth_user", fake_inject_auth_user)
    monkeypatch.setattr(deps, "inject_scope", fake_inject_scope)
    monkeypatch.setattr(deps, "set_scope_context", lambda score, paths=(): context_scopes.append((score, paths)))

    returned = asyncio.run(deps.get_current_user(db=object(), token="signed-token"))

    assert returned is user
    assert injected_scopes == [("org.234.KW.ILR.ILE", 3, None, "user-1", ())]
    assert context_scopes == [(3, ())]


def test_token_permission_snapshot_is_reused_until_user_cache_invalidation(monkeypatch):
    clear_user_cache()
    user = SimpleNamespace(
        user_id="user-cache-1", path="org.234.KW.ILR.ILE.003",
        roles=[SimpleNamespace(score_value=3, permissions=[])],
        is_deleted=False, is_active=True, approval_status="approved",
    )
    lookups = []
    scopes = []

    class MergeSession:
        async def merge(self, cached, *, load):
            return cached
    monkeypatch.setattr(deps.security, "verify_token", lambda token: {"sub": "user-cache-1"})

    async def fake_get(db, *, id):
        lookups.append(id)
        return user

    async def fake_inject_auth_user(db, user_id):
        return None

    async def fake_inject_scope(db, scope_path, *, role_score, continent=None, user_id=None, nation_paths=()):
        scopes.append(scope_path)

    monkeypatch.setattr(deps.crud_user, "get", fake_get)
    monkeypatch.setattr(deps, "inject_auth_user", fake_inject_auth_user)
    monkeypatch.setattr(deps, "inject_scope", fake_inject_scope)
    monkeypatch.setattr(deps, "set_scope_context", lambda score, paths=(): None)

    first = asyncio.run(deps.get_current_user(db=MergeSession(), token="cache-token-1"))
    second = asyncio.run(deps.get_current_user(db=MergeSession(), token="cache-token-1"))
    assert first is user and second is user
    assert lookups == ["user-cache-1"]
    assert len(scopes) == 2

    invalidate_user_cache("user-cache-1")
    asyncio.run(deps.get_current_user(db=MergeSession(), token="cache-token-1"))
    assert lookups == ["user-cache-1", "user-cache-1"]


def test_request_rejects_unapproved_account(monkeypatch):
    clear_user_cache()
    user = SimpleNamespace(
        user_id="user-1",
        path="org.234.KW.ILR.ILE.003",
        roles=[],
        is_deleted=False,
        is_active=True,
        approval_status="pending",
    )
    monkeypatch.setattr(deps.security, "verify_token", lambda token: {"sub": "user-1"})

    async def fake_get(db, *, id):
        return user

    async def fake_inject_auth_user(db, user_id):
        return None

    monkeypatch.setattr(deps, "inject_auth_user", fake_inject_auth_user)
    monkeypatch.setattr(deps.crud_user, "get", fake_get)

    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(deps.get_current_user(db=object(), token="signed-token"))

    assert exc_info.value.status_code == 401


def test_request_rejects_refresh_token_as_access_token(monkeypatch):
    clear_user_cache()
    monkeypatch.setattr(
        deps.security,
        "verify_token",
        lambda token: {"sub": "user-1", "type": "refresh"},
    )

    async def unexpected_user_lookup(db, *, id):
        raise AssertionError("refresh token reached protected user lookup")

    monkeypatch.setattr(deps.crud_user, "get", unexpected_user_lookup)

    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(deps.get_current_user(db=object(), token="refresh-token"))

    assert exc_info.value.status_code == 401


def test_level_eight_scope_loads_all_nations_in_home_continent(monkeypatch):
    from app.models.location import Nation

    injected_scopes = []
    context_scopes = []
    user = SimpleNamespace(
        user_id="user-continental",
        path="org.AFR1.KW.ILR.ILE.003",
        roles=[SimpleNamespace(score_value=8)],
        is_deleted=False,
        is_active=True,
        approval_status="approved",
    )
    home_nation = SimpleNamespace(continent="Africa")

    monkeypatch.setattr(deps.security, "verify_token", lambda token: {"sub": user.user_id})

    async def fake_get(db, *, id):
        return user

    class FakeResult:
        def scalar_one_or_none(self):
            return home_nation

        def all(self):
            return [("org.AFR1",), ("org.AFR2",)]

    class FakeDB:
        async def execute(self, statement):
            return FakeResult()

    async def fake_inject_auth_user(db, user_id):
        return None

    async def fake_inject_continent(db, continent):
        return None

    async def fake_inject_scope(db, scope_path, *, role_score, continent=None, user_id=None, nation_paths=()):
        injected_scopes.append((scope_path, role_score, continent, user_id, nation_paths))

    monkeypatch.setattr(deps.crud_user, "get", fake_get)
    monkeypatch.setattr(deps, "inject_auth_user", fake_inject_auth_user)
    monkeypatch.setattr(deps, "inject_continent", fake_inject_continent)
    monkeypatch.setattr(deps, "inject_scope", fake_inject_scope)
    monkeypatch.setattr(deps, "set_scope_context", lambda score, paths=(): context_scopes.append((score, paths)))

    returned = asyncio.run(deps.get_current_user(db=FakeDB(), token="signed-token"))

    assert returned._authorized_continent == "Africa"
    assert returned._authorized_nation_paths == ("org.AFR1", "org.AFR2")
    assert injected_scopes == [("org", 8, "Africa", user.user_id, ("org.AFR1", "org.AFR2"))]
    assert context_scopes == [(8, ("org.AFR1", "org.AFR2"))]
