"""HTTP hardening middleware: security headers, metrics auth and rate limits."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from starlette.responses import Response

from app.config import Settings


_WINDOW_SECONDS = 60.0
_hits: dict[str, deque[float]] = defaultdict(deque)


def add_security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' http://localhost:* http://127.0.0.1:*; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    return response


def rate_limit_key(request: Request, settings: Settings) -> tuple[str, int] | None:
    path = request.url.path
    method = request.method.upper()
    if path in {"/auth/signup", "/auth/signin"} and method == "POST":
        return (
            f"auth:{_client_ip(request)}:{path}",
            _setting(settings, "auth_rate_limit_per_minute", 20),
        )
    if path == "/admin/documents" and method == "POST":
        return (
            f"upload:{_principal_or_ip(request)}",
            _setting(settings, "upload_rate_limit_per_minute", 10),
        )
    if path == "/chat" and method == "POST":
        return (
            f"chat:{_principal_or_ip(request)}",
            _setting(settings, "api_rate_limit_per_minute", 120),
        )
    return None


def check_rate_limit(key: str, limit: int) -> None:
    if limit <= 0:
        return
    now = time.monotonic()
    bucket = _hits[key]
    while bucket and now - bucket[0] >= _WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    bucket.append(now)


def verify_metrics_access(request: Request, settings: Settings) -> None:
    if settings.environment.lower() not in {"prod", "production"}:
        return
    expected = settings.metrics_auth_token.strip()
    if not expected:
        raise HTTPException(status_code=404, detail="not found")
    supplied = request.headers.get("x-metrics-token", "")
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        supplied = auth.partition(" ")[2]
    if supplied != expected:
        raise HTTPException(status_code=404, detail="not found")


def clear_rate_limits() -> None:
    _hits.clear()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _principal_or_ip(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth:
        return auth[-32:]
    return _client_ip(request)


def _setting(settings: Settings, name: str, default: int) -> int:
    return int(getattr(settings, name, default))
