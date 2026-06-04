"""Auth + tenant resolution dependencies (RBAC down to asset/function level)."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.config import get_settings
from app.core import neon_auth


VALID_ROLES = {"platform_admin", "admin", "engineer", "field", "hse"}


@dataclass
class Principal:
    tenant_id: str
    user_id: str
    role: str
    allowed_assets: list[str]


async def get_principal(authorization: str = Header(default="")) -> Principal:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing credentials")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="invalid credentials")

    # Pick the verification path by the token's algorithm. Neon Auth (Better Auth) tokens are
    # EdDSA and verified against Neon's JWKS; our own tokens are HS256/RS256.
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="invalid credentials") from exc
    if alg == "EdDSA":
        return await _neon_principal(token)

    settings = get_settings()
    key, algorithm = _jwt_key_and_algorithm(settings)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="invalid credentials") from exc

    # Server-side revocation check: signature + exp are valid, but the user may
    # have hit /auth/logout or an admin may have revoked the jti out-of-band.
    from app.core.token_revocation import is_revoked
    jti = claims.get("jti")
    if isinstance(jti, str) and jti and is_revoked(jti):
        raise HTTPException(status_code=401, detail="token revoked")

    try:
        principal = Principal(
            tenant_id=_claim_str(claims, "tenant_id"),
            user_id=_claim_str(claims, "user_id", fallback_key="sub"),
            role=_claim_str(claims, "role"),
            allowed_assets=_claim_list(claims, "allowed_assets"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if principal.role not in VALID_ROLES:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return principal


async def _neon_principal(token: str) -> Principal:
    """
    Verify a Neon Auth (Better Auth) EdDSA token and map it to a Principal via
    the local users table.

    Disabled by default. When ``PB_NEON_AUTH_ENABLED=true``, the token must:
      * pass JWKS signature + ``exp`` verification, AND
      * carry an ``email`` claim that matches an *active* row in the ``users``
        table - which is what supplies tenant_id, role, and allowed_assets.

    No email match = 401. Previously this path collapsed every Neon user into
    ``default_signup_tenant_id`` with ``allowed_assets=["*"]``, which silently
    defeated multi-tenant isolation. There is no per-tenant trust-on-first-use:
    a tenant admin must invite the user before Neon SSO works for them.
    """
    settings = get_settings()
    invalid = HTTPException(status_code=401, detail="invalid credentials")
    if not settings.neon_auth_enabled or not neon_auth.is_configured():
        raise invalid
    try:
        claims = await run_in_threadpool(neon_auth.verify_neon_token, token)
    except Exception as exc:  # JWKS fetch / signature / expiry failure
        raise invalid from exc

    email = claims.get("email")
    if not isinstance(email, str) or not email.strip():
        raise invalid

    from app.db.users_repository import get_users_repository
    repo = get_users_repository()
    record = await run_in_threadpool(repo.find_by_email_any_tenant, email.strip())
    if record is None or record.get("status") != "active":
        raise invalid
    role = record.get("role")
    if role not in VALID_ROLES:
        raise invalid
    return Principal(
        tenant_id=record["tenant_id"],
        user_id=record["id"],
        role=role,
        allowed_assets=list(record.get("allowed_assets") or []),
    )


def require_role(*roles: str) -> Callable[[Principal], Principal]:
    allowed = set(roles)
    unknown = allowed - VALID_ROLES
    if unknown:
        raise ValueError(f"unknown roles: {sorted(unknown)}")

    def checker(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(status_code=403, detail="role not allowed for principal")
        return principal

    return checker


def require_asset_access(principal: Principal, asset: str | None) -> None:
    if not asset or "*" in principal.allowed_assets:
        return
    if asset not in principal.allowed_assets:
        raise HTTPException(status_code=403, detail="asset not allowed for principal")


def require_tenant_access(principal: Principal, tenant_id: str) -> None:
    """
    Cross-tenant authorisation gate (B8).

    Platform admins can act on any tenant; everyone else is locked to
    their own. Routes that take a tenant_id path/query parameter call
    this before reading or writing.
    """
    if principal.role == "platform_admin":
        return
    if principal.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="cross-tenant access denied",
        )


def is_platform_admin(principal: Principal) -> bool:
    return principal.role == "platform_admin"


def _jwt_key_and_algorithm(settings) -> tuple[str, str]:
    if settings.jwt_public_key:
        return settings.jwt_public_key, "RS256"
    if settings.jwt_secret:
        return settings.jwt_secret, "HS256"
    raise HTTPException(status_code=500, detail="JWT verification key is not configured")


def _claim_str(claims: dict, key: str, *, fallback_key: str | None = None) -> str:
    value = claims.get(key)
    if value is None and fallback_key:
        value = claims.get(fallback_key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or invalid JWT claim: {key}")
    return value


def _claim_list(claims: dict, key: str) -> list[str]:
    value = claims.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"missing or invalid JWT claim: {key}")
    return value
