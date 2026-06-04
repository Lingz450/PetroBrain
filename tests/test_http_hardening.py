"""HTTP hardening tests: rate limiter keying + trusted-proxy XFF parsing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from starlette.requests import Request

from app.config import Settings
from app.core import http_hardening as hh


def _request(headers: dict[str, str], client: tuple[str, int] | None = ("203.0.113.10", 1234)):
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/chat",
        "headers": raw_headers,
        "client": client,
        "query_string": b"",
        "scheme": "http",
    }
    return Request(scope)


def _settings(**overrides) -> Settings:
    base = {"rate_limit_backend": "memory", "trusted_proxy_cidrs": ""}
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(autouse=True)
def _reset_backend():
    hh.clear_rate_limits()
    yield
    hh.clear_rate_limits()


def test_untrusted_xff_is_ignored():
    """A direct connect from a non-proxy peer MUST NOT honour XFF, otherwise
    an attacker rotates XFF and gets unlimited rate-limit buckets."""
    req = _request({"x-forwarded-for": "1.1.1.1"})
    settings = _settings(trusted_proxy_cidrs="")
    assert hh._trusted_client_ip(req, settings) == "203.0.113.10"


def test_trusted_xff_is_honoured():
    req = _request({"x-forwarded-for": "1.1.1.1, 10.0.0.5"}, client=("10.0.0.5", 0))
    settings = _settings(trusted_proxy_cidrs="10.0.0.0/8")
    # Inner hop is trusted, so the next-left untrusted IP wins.
    assert hh._trusted_client_ip(req, settings) == "1.1.1.1"


def test_principal_key_uses_jwt_sub_unverified():
    token = jwt.encode(
        {
            "user_id": "u-42", "sub": "u-42", "tenant_id": "demo",
            "role": "admin", "allowed_assets": [],
            "iss": "petrobrain", "aud": "petrobrain-api",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "anything-this-is-not-verified-here",
        algorithm="HS256",
    )
    req = _request({"authorization": f"Bearer {token}"})
    assert hh._principal_or_ip(req, _settings()) == "user:u-42"


def test_rate_limit_blocks_after_limit():
    key, limit = "auth:1.2.3.4:/auth/signin", 3
    for _ in range(limit):
        hh.check_rate_limit(key, limit)
    with pytest.raises(Exception) as exc:  # HTTPException
        hh.check_rate_limit(key, limit)
    assert getattr(exc.value, "status_code", None) == 429


def test_unauthenticated_falls_back_to_ip():
    req = _request({})
    assert hh._principal_or_ip(req, _settings()) == "ip:203.0.113.10"
