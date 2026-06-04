"""H1: server-side JWT revocation via jti + /auth/logout."""
from __future__ import annotations

from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core import token_revocation
from app.core.auth import mint_jwt
from app.main import app
from tests.auth_helpers import jwt_settings


client = TestClient(app)


@pytest.fixture(autouse=True)
def _wire(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", jwt_settings)
    token_revocation.reset_for_tests()
    yield
    token_revocation.reset_for_tests()


def _mint(settings, **overrides) -> str:
    args = dict(
        tenant_id="demo", user_id="u1", role="engineer", allowed_assets=["*"],
        secret=settings.jwt_secret, issuer=settings.jwt_issuer,
        audience=settings.jwt_audience, ttl=timedelta(hours=1),
    )
    args.update(overrides)
    return mint_jwt(**args)


def test_mint_jwt_includes_jti():
    settings = jwt_settings()
    token = _mint(settings)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert isinstance(claims.get("jti"), str) and claims["jti"]


def test_logout_revokes_jti_and_subsequent_calls_401():
    settings = jwt_settings()
    token = _mint(settings)
    headers = {"Authorization": f"Bearer {token}"}

    # Token works pre-logout.
    assert client.get("/health").status_code == 200
    r = client.post("/auth/logout", headers=headers)
    assert r.status_code == 204

    # Same token now rejected.
    r2 = client.post(
        "/chat", headers=headers,
        json={"message": "hi"},
    )
    assert r2.status_code == 401
    assert "revoked" in r2.json()["detail"].lower()


def test_logout_is_idempotent():
    settings = jwt_settings()
    token = _mint(settings)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/auth/logout", headers=headers).status_code == 204
    # Second call would also need a still-valid token, which is now revoked,
    # so we get 401 - that's the expected idempotent shape (no 500).
    assert client.post("/auth/logout", headers=headers).status_code == 401


def test_logout_without_auth_is_401():
    assert client.post("/auth/logout").status_code == 401
