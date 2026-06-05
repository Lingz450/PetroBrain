"""
Error reporting flow:

  POST /errors          - any authenticated user reports an error they saw.
                          tenant_id / user_id / role are taken from the JWT
                          so a malicious client can't impersonate other
                          tenants. Rate-limited per principal at the
                          hardening middleware (same bucket as /chat).

  GET  /admin/errors    - admin / platform_admin reads the latest N errors
                          for their own tenant. Surfaces in the
                          /admin Learning page.

The data flowing here is user-safe strings: chat stream error messages
("token expired", "rate limit exceeded"), fetch failure descriptions,
HTTP status codes. The raw user turn text never lands here - chat-stream
catch handlers in the web app only forward the error.message, not the
prompt body.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import Principal, get_principal, require_role
from app.db.error_events_repository import get_error_events_repository


report_router = APIRouter(prefix="/errors", tags=["errors"])
admin_router = APIRouter(prefix="/admin/errors", tags=["admin", "errors"])
_admin_or_platform = require_role("admin", "platform_admin")

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


class ErrorReport(BaseModel):
    """One error the user saw. ``route`` is the frontend route or backend
    path it happened against (e.g. "/chat", "/admin/documents"). ``status``
    is the HTTP status if known. ``message`` is the user-safe error string -
    the same one the user actually saw on screen."""
    route: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    status: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@report_router.post("", status_code=201)
async def report_error(
    req: ErrorReport,
    who: Principal = Depends(get_principal),
):
    """Append a user-visible error to the tenant feed. The JWT supplies
    tenant_id / user_id / role; the client cannot set them. Returns the
    persisted row id so the frontend can correlate locally if needed."""
    repo = get_error_events_repository()
    try:
        record = repo.append(
            tenant_id=who.tenant_id,
            user_id=who.user_id,
            role=who.role,
            route=req.route,
            status=req.status,
            message=req.message,
            metadata=req.metadata or {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": record.id, "created_utc": record.created_utc}


@admin_router.get("")
async def list_errors(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    who: Principal = Depends(_admin_or_platform),
):
    """Latest errors for the admin's own tenant, newest first."""
    repo = get_error_events_repository()
    rows = repo.list_records(tenant_id=who.tenant_id, limit=limit, offset=offset)
    return {
        "errors": rows,
        "tenant_id": who.tenant_id,
        "limit": limit,
        "offset": offset,
    }
