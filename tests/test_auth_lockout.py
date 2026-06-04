"""H4: per-account brute force lockout for /auth/signin."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api import routes_auth
from app.config import Settings
from app.core import auth_lockout
from app.db.tenants_repository import LocalJsonTenantsRepository
from app.db.users_repository import LocalJsonUsersRepository
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def wire(monkeypatch, tmp_path):
    tenants = LocalJsonTenantsRepository(tmp_path / "tenants.jsonl")
    users = LocalJsonUsersRepository(tmp_path / "users.jsonl")
    settings = Settings(
        environment="dev",
        jwt_secret="x" * 48,
        jwt_issuer="petrobrain",
        jwt_audience="petrobrain-api",
        jwt_ttl_hours=1,
        enable_self_signup=True,
        default_signup_tenant_id="demo",
        default_signup_tenant_name="Demo",
        default_signup_role="engineer",
        bootstrap_platform_admin_emails="",
        password_min_length=8,
        auth_lockout_max_failures=3,
        auth_lockout_window_minutes=15,
        auth_lockout_minutes=15,
        rate_limit_backend="memory",
    )
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    monkeypatch.setattr(routes_auth, "get_settings", lambda: settings)
    monkeypatch.setattr(routes_auth, "get_users_repository", lambda: users)
    monkeypatch.setattr(routes_auth, "get_tenants_repository", lambda: tenants)
    # auth_lockout reads settings via app.config.get_settings directly
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    auth_lockout.reset_for_tests()


def test_account_locks_after_max_failures():
    # Real user.
    r = client.post("/auth/signup", json={"email": "u@x.y", "password": "correcthorse1"})
    assert r.status_code == 201

    # Three failures (max=3) trip the lock.
    for _ in range(3):
        r = client.post("/auth/signin", json={"email": "u@x.y", "password": "wrong-one1"})
        assert r.status_code == 401

    # Now even the correct password is refused with the same 401.
    r = client.post("/auth/signin", json={"email": "u@x.y", "password": "correcthorse1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid email or password"


def test_successful_signin_clears_failure_count():
    client.post("/auth/signup", json={"email": "u2@x.y", "password": "correcthorse1"})
    # Two failures (below the lockout threshold).
    for _ in range(2):
        client.post("/auth/signin", json={"email": "u2@x.y", "password": "wrong-one1"})
    # Right password resets the counter.
    r = client.post("/auth/signin", json={"email": "u2@x.y", "password": "correcthorse1"})
    assert r.status_code == 200
    # And the next two failures don't trip the lock (counter was reset).
    for _ in range(2):
        client.post("/auth/signin", json={"email": "u2@x.y", "password": "wrong-one1"})
    r = client.post("/auth/signin", json={"email": "u2@x.y", "password": "correcthorse1"})
    assert r.status_code == 200


def test_unknown_email_still_counts_to_lockout():
    """Otherwise an attacker can probe email existence by watching the lockout
    show up for valid users but not invalid ones."""
    for _ in range(3):
        r = client.post("/auth/signin", json={"email": "ghost@x.y", "password": "anything1"})
        assert r.status_code == 401
    # Lockout now active for ghost@x.y - same 401 either way.
    r = client.post("/auth/signin", json={"email": "ghost@x.y", "password": "different1"})
    assert r.status_code == 401
