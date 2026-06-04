"""Server-side JWT revocation by ``jti``.

Access tokens are short-lived (jwt_ttl_hours), but until they expire we still
need a way to invalidate a stolen or logged-out session immediately. This
module is the store ``get_principal`` checks and ``/auth/logout`` writes to.

Backends:
* memory: per-process set keyed by jti -> expiry epoch. Lost on restart, not
  shared across replicas. Right for tests and single-process dev.
* redis: ``SET key "" EX <remaining>`` per revoked jti. Shared across all
  replicas; entries auto-expire when the underlying token would have expired.

Falls open (treats unknown as not-revoked) if the backend is unreachable so a
Redis outage doesn't lock everyone out. The /auth/logout call still succeeds
locally; the access token is at most ``jwt_ttl_hours`` away from expiring on
its own.
"""
from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Protocol

logger = logging.getLogger(__name__)

_KEY_PREFIX = "pb:revoked:"


class _Backend(Protocol):
    def revoke(self, jti: str, ttl_seconds: int) -> None: ...
    def is_revoked(self, jti: str) -> bool: ...


class _MemoryBackend:
    def __init__(self) -> None:
        self._entries: dict[str, float] = {}
        self._lock = Lock()

    def revoke(self, jti: str, ttl_seconds: int) -> None:
        with self._lock:
            self._entries[jti] = time.time() + max(0, ttl_seconds)
            self._sweep_locked()

    def is_revoked(self, jti: str) -> bool:
        with self._lock:
            self._sweep_locked()
            return jti in self._entries

    def _sweep_locked(self) -> None:
        now = time.time()
        for k in [k for k, exp in self._entries.items() if exp <= now]:
            del self._entries[k]


class _RedisBackend:
    def __init__(self, client) -> None:  # type: ignore[no-untyped-def]
        self._client = client

    def revoke(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        try:
            self._client.set(_KEY_PREFIX + jti, "1", ex=ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            logger.warning("token_revoke_redis_unreachable", extra={"error": str(exc)})

    def is_revoked(self, jti: str) -> bool:
        try:
            return bool(self._client.exists(_KEY_PREFIX + jti))
        except Exception as exc:  # noqa: BLE001
            logger.warning("token_revoke_check_redis_unreachable", extra={"error": str(exc)})
            return False


_backend: _Backend | None = None


def _get_backend() -> _Backend:
    global _backend
    if _backend is not None:
        return _backend
    from app.config import get_settings

    settings = get_settings()
    choice = (settings.jwt_revocation_backend or "").strip().lower()
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
        logger.error(
            "token_revoke_redis_unavailable_falling_back_to_memory",
            extra={"error": str(exc)},
        )
        return _MemoryBackend()


def revoke(jti: str, exp_epoch: float) -> None:
    if not jti:
        return
    ttl = int(exp_epoch - time.time())
    _get_backend().revoke(jti, ttl)


def is_revoked(jti: str) -> bool:
    if not jti:
        return False
    return _get_backend().is_revoked(jti)


def reset_for_tests() -> None:
    global _backend
    _backend = None
