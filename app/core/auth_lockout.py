"""Per-account brute-force lockout for /auth/signin (H4).

Counts consecutive failed sign-in attempts for an email and rejects further
attempts once the threshold is crossed, for a cool-down window. Reset on
success. Backed by the same memory/Redis split as the rate limiter so the
lockout is shared across replicas in prod.

This is layered on top of the per-IP rate limit (which is checked first in the
hardening middleware). The IP limit slows scanners; the per-account limit stops
credential-stuffing against a single high-value account from many IPs.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock
from typing import Protocol

logger = logging.getLogger(__name__)


class _Backend(Protocol):
    def record_failure(self, key: str, window_seconds: int) -> int: ...
    def record_success(self, key: str) -> None: ...
    def is_locked(self, key: str, max_failures: int) -> bool: ...
    def lock(self, key: str, ttl_seconds: int) -> None: ...


class _MemoryBackend:
    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = {}
        self._locks: dict[str, float] = {}
        self._mu = Lock()

    def record_failure(self, key: str, window_seconds: int) -> int:
        now = time.time()
        with self._mu:
            bucket = self._failures.setdefault(key, deque())
            while bucket and now - bucket[0] >= window_seconds:
                bucket.popleft()
            bucket.append(now)
            return len(bucket)

    def record_success(self, key: str) -> None:
        with self._mu:
            self._failures.pop(key, None)
            self._locks.pop(key, None)

    def is_locked(self, key: str, max_failures: int) -> bool:  # noqa: ARG002
        with self._mu:
            until = self._locks.get(key, 0.0)
            if until > time.time():
                return True
            if until:
                self._locks.pop(key, None)
            return False

    def lock(self, key: str, ttl_seconds: int) -> None:
        with self._mu:
            self._locks[key] = time.time() + ttl_seconds


class _RedisBackend:
    def __init__(self, client) -> None:  # type: ignore[no-untyped-def]
        self._client = client

    def record_failure(self, key: str, window_seconds: int) -> int:
        bucket = f"pb:lockf:{key}"
        try:
            pipe = self._client.pipeline()
            pipe.incr(bucket, 1)
            pipe.expire(bucket, window_seconds)
            count, _ = pipe.execute()
            return int(count)
        except Exception as exc:  # noqa: BLE001
            logger.warning("lockout_backend_unreachable", extra={"error": str(exc)})
            return 0

    def record_success(self, key: str) -> None:
        try:
            self._client.delete(f"pb:lockf:{key}", f"pb:lock:{key}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("lockout_clear_unreachable", extra={"error": str(exc)})

    def is_locked(self, key: str, max_failures: int) -> bool:  # noqa: ARG002
        try:
            return bool(self._client.exists(f"pb:lock:{key}"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("lockout_check_unreachable", extra={"error": str(exc)})
            return False

    def lock(self, key: str, ttl_seconds: int) -> None:
        try:
            self._client.set(f"pb:lock:{key}", "1", ex=ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            logger.warning("lockout_set_unreachable", extra={"error": str(exc)})


_backend: _Backend | None = None


def _get_backend() -> _Backend:
    global _backend
    if _backend is not None:
        return _backend
    from app.config import get_settings

    settings = get_settings()
    # Reuse the rate-limit choice: same Redis, same lifecycle.
    choice = (settings.rate_limit_backend or "").strip().lower()
    if not choice:
        choice = "redis" if settings.environment.lower() in {"prod", "production"} else "memory"
    if choice == "redis":
        _backend = _build_redis_backend(settings)
    else:
        _backend = _MemoryBackend()
    return _backend


def _build_redis_backend(settings) -> _Backend:
    try:
        import redis  # type: ignore

        from app.core.redis_security import redis_ssl_options

        client = redis.Redis.from_url(
            settings.redis_url, decode_responses=True,
            **redis_ssl_options(settings.redis_url, settings),
        )
        client.ping()
        return _RedisBackend(client)
    except Exception as exc:  # noqa: BLE001
        logger.error("lockout_redis_fallback_memory", extra={"error": str(exc)})
        return _MemoryBackend()


def _key(tenant_id: str, email: str) -> str:
    return f"{tenant_id}|{email.strip().lower()}"


def is_locked(tenant_id: str, email: str) -> bool:
    from app.config import get_settings

    settings = get_settings()
    return _get_backend().is_locked(_key(tenant_id, email), settings.auth_lockout_max_failures)


def record_failure(tenant_id: str, email: str) -> bool:
    """Record a failed signin. Returns True iff this failure tripped the lock."""
    from app.config import get_settings

    settings = get_settings()
    backend = _get_backend()
    failures = backend.record_failure(
        _key(tenant_id, email), settings.auth_lockout_window_minutes * 60,
    )
    if failures >= settings.auth_lockout_max_failures:
        backend.lock(_key(tenant_id, email), settings.auth_lockout_minutes * 60)
        return True
    return False


def record_success(tenant_id: str, email: str) -> None:
    _get_backend().record_success(_key(tenant_id, email))


def reset_for_tests() -> None:
    global _backend
    _backend = None
