"""FastAPI entrypoint - the Phase-1 Tier-A spine."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_admin_audit,
    routes_admin_data_readiness,
    routes_admin_documents,
    routes_admin_permits,
    routes_admin_tenants,
    routes_admin_users,
    routes_assets,
    routes_auth,
    routes_calc,
    routes_chat,
    routes_chat_shares,
    routes_documents,
    routes_emissions,
    routes_wellcontrol,
)
from app.config import get_settings, validate_production_settings
from app.core.http_hardening import (
    add_security_headers,
    check_rate_limit,
    rate_limit_key,
    verify_metrics_access,
)
from app.core.observability import metrics_response, setup_observability

settings = get_settings()
validate_production_settings(settings)
app = FastAPI(title=settings.app_name, version="0.1.0")
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Allow the browser-based web/admin apps (served from a different port) to call
# this API. Added BEFORE observability instrumentation, which builds/wraps the
# middleware stack - middleware added after instrument_app is ignored. Auth is
# via the Authorization header (no cookies), so credentials stay off; lock the
# origin allowlist down in production via PB_CORS_ALLOW_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

setup_observability(app, settings)


@app.middleware("http")
async def hardening_middleware(request: Request, call_next):
    limit = rate_limit_key(request, settings)
    if limit is not None:
        try:
            check_rate_limit(*limit)
        except HTTPException as exc:
            return add_security_headers(
                JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
            )
    response = await call_next(request)
    return add_security_headers(response)

app.include_router(routes_auth.router)
app.include_router(routes_chat.router)
app.include_router(routes_chat_shares.router)
app.include_router(routes_wellcontrol.router)
app.include_router(routes_emissions.router)
app.include_router(routes_documents.router)
app.include_router(routes_documents.docs_router)
app.include_router(routes_admin_documents.router)
app.include_router(routes_admin_audit.router)
app.include_router(routes_assets.router)
app.include_router(routes_calc.router)
app.include_router(routes_admin_tenants.router)
app.include_router(routes_admin_users.router)
app.include_router(routes_admin_data_readiness.router)
app.include_router(routes_admin_permits.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "tier": "B" if settings.operational_tier else "A",
    }


@app.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    verify_metrics_access(request, settings)
    return metrics_response()
