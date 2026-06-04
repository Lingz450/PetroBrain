"""
Admin read API for per-tenant chunk weights (slice 3 of the learning loop).

GET /admin/chunk-weights?tenant_id=&limit=&offset=

Read-only for now. Admins watch this to see which chunks the tenant's users
are pushing up or down; if a critical SOP shows up at the bottom, that's a
signal to investigate (training problem? wrong document? prompt
misalignment?). Writes happen only through the feedback loop -
no manual override endpoint here - so the audit trail stays clean: every
weight change is traceable to a feedback row + a turn.

Role-gated to admin / platform_admin. Tenant-scoped via RLS + in-app
filter; platform_admin may pass ?tenant_id=X.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import Principal, is_platform_admin, require_role
from app.db.chunk_weights_repository import get_chunk_weights_repository


router = APIRouter(prefix="/admin/chunk-weights", tags=["admin", "learning"])
_admin_or_platform = require_role("admin", "platform_admin")

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


@router.get("")
async def list_chunk_weights(
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    who: Principal = Depends(_admin_or_platform),
):
    effective_tenant = _resolve_target_tenant(who, tenant_id)
    rows = get_chunk_weights_repository().list_records(
        tenant_id=effective_tenant, limit=limit, offset=offset,
    )
    return {
        "weights": rows,
        "tenant_id": effective_tenant,
        "limit": limit,
        "offset": offset,
    }


def _resolve_target_tenant(who: Principal, tenant_id: str | None) -> str:
    if tenant_id is None:
        return who.tenant_id
    if not is_platform_admin(who) and tenant_id != who.tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant access denied")
    return tenant_id
