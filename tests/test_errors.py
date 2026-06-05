"""Error reporting feed (Commit B): POST /errors + GET /admin/errors."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps, routes_errors
from app.db.error_events_repository import LocalJsonErrorEventsRepository
from app.main import app
from tests.auth_helpers import auth_headers, jwt_settings


client = TestClient(app)


@pytest.fixture
def errors_repo(tmp_path):
    return LocalJsonErrorEventsRepository(tmp_path / "error_events.jsonl")


@pytest.fixture(autouse=True)
def wire(monkeypatch, errors_repo):
    monkeypatch.setattr(deps, "get_settings", jwt_settings)
    monkeypatch.setattr(
        routes_errors, "get_error_events_repository", lambda: errors_repo,
    )


# ---- POST /errors ------------------------------------------------------

def test_post_error_persists_under_jwt_tenant(errors_repo):
    r = client.post(
        "/errors",
        headers=auth_headers(tenant_id="t1", user_id="u1"),
        json={
            "route": "/chat",
            "message": "chat stream failed (502): bad gateway",
            "status": 502,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"]
    # tenant_id comes from JWT, not the request body.
    rows = errors_repo.list_records(tenant_id="t1")
    assert len(rows) == 1
    assert rows[0]["tenant_id"] == "t1"
    assert rows[0]["user_id"] == "u1"
    assert rows[0]["route"] == "/chat"
    assert rows[0]["status"] == 502
    assert rows[0]["message"].startswith("chat stream failed")


def test_post_error_requires_auth():
    r = client.post(
        "/errors",
        json={"route": "/chat", "message": "x"},
    )
    assert r.status_code == 401


def test_post_error_rejects_blank_message():
    r = client.post(
        "/errors",
        headers=auth_headers(tenant_id="t1"),
        json={"route": "/chat", "message": ""},
    )
    assert r.status_code == 422


def test_post_error_rejects_overlong_message(errors_repo):
    r = client.post(
        "/errors",
        headers=auth_headers(tenant_id="t1"),
        json={"route": "/chat", "message": "x" * 4001},
    )
    assert r.status_code == 422


def test_post_error_is_tenant_scoped(errors_repo):
    """A user from tenant t1 cannot write under tenant 'other' even if they
    try - the route reads tenant_id from the JWT, not the body."""
    client.post(
        "/errors",
        headers=auth_headers(tenant_id="t1", user_id="u-1"),
        json={"route": "/chat", "message": "from t1"},
    )
    client.post(
        "/errors",
        headers=auth_headers(tenant_id="other", user_id="u-other"),
        json={"route": "/chat", "message": "from other"},
    )
    assert {r["tenant_id"] for r in errors_repo.list_records(tenant_id="t1")} == {"t1"}
    assert {r["tenant_id"] for r in errors_repo.list_records(tenant_id="other")} == {"other"}


# ---- GET /admin/errors -------------------------------------------------

def test_admin_errors_requires_admin_role(errors_repo):
    # Seed one error.
    client.post(
        "/errors",
        headers=auth_headers(tenant_id="t1", role="admin"),
        json={"route": "/chat", "message": "x"},
    )
    r = client.get("/admin/errors", headers=auth_headers(tenant_id="t1", role="engineer"))
    assert r.status_code == 403
    r = client.get("/admin/errors", headers=auth_headers(tenant_id="t1", role="admin"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["errors"]) == 1


def test_admin_errors_returns_newest_first(errors_repo):
    import time
    for i in range(3):
        client.post(
            "/errors",
            headers=auth_headers(tenant_id="t1", user_id=f"u{i}"),
            json={"route": f"/chat/{i}", "message": f"err {i}"},
        )
        time.sleep(0.002)
    r = client.get("/admin/errors", headers=auth_headers(tenant_id="t1", role="admin"))
    bodies = [e["message"] for e in r.json()["errors"]]
    assert bodies == ["err 2", "err 1", "err 0"]


def test_admin_errors_only_returns_own_tenant(errors_repo):
    """Two tenants reporting errors - tenant admin only sees their own
    tenant's rows, not the other's. Backend filter + RLS deliver this."""
    client.post(
        "/errors",
        headers=auth_headers(tenant_id="acme", user_id="u-acme"),
        json={"route": "/chat", "message": "acme err"},
    )
    client.post(
        "/errors",
        headers=auth_headers(tenant_id="ghost", user_id="u-ghost"),
        json={"route": "/chat", "message": "ghost err"},
    )
    r = client.get("/admin/errors", headers=auth_headers(tenant_id="acme", role="admin"))
    bodies = [e["message"] for e in r.json()["errors"]]
    assert bodies == ["acme err"]
