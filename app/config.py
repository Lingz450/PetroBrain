"""Centralized configuration. Values come from environment / .env."""
from __future__ import annotations

import os
import sys
from functools import lru_cache

# Dev convenience: load a local .env into the process environment so vars the
# app reads via os.getenv (ANTHROPIC_API_KEY / OPENAI_API_KEY) are picked up
# without `uvicorn --env-file`. Skipped under pytest so the test suite stays
# hermetic, and never overrides values already set in the real environment.
if "pytest" not in sys.modules:
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:  # python-dotenv optional; --env-file still works without it
        pass

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # fallback so the module imports without the dep installed
    SettingsConfigDict = dict  # type: ignore

    class BaseSettings:  # type: ignore
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)


class Settings(BaseSettings):
    # extra="ignore": .env legitimately holds non-PB_ keys (ANTHROPIC_API_KEY,
    # OPENAI_API_KEY) that the LLM/embeddings SDKs read via os.getenv, not via
    # Settings. Ignore them here instead of erroring on extra inputs.
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PB_", extra="ignore")

    app_name: str = "PetroBrain"
    environment: str = "dev"

    # Cross-origin: the office/admin web apps (different port) call this API from
    # the browser. Comma-separated allowlist; lock down to the real origin(s) in
    # production.
    cors_allow_origins: str = (
        "http://localhost:3000,http://localhost:3001,"
        "http://127.0.0.1:3000,http://127.0.0.1:3001"
    )

    # LLM
    llm_provider: str = "anthropic"          # anthropic | self_hosted
    llm_model: str = "claude-sonnet-4-6"
    llm_api_base: str = ""                    # set for self-hosted (vLLM/TGI) endpoint
    llm_max_tokens: int = 2048

    # Data stores
    database_url: str = "postgresql+asyncpg://petrobrain:petrobrain@localhost:5432/petrobrain"
    redis_url: str = "redis://localhost:6379/0"
    redis_ssl_cert_reqs: str = "required"       # required | optional | none
    redis_ssl_ca_certs: str = ""
    redis_ssl_certfile: str = ""
    redis_ssl_keyfile: str = ""
    audit_log_path: str = "logs/audit.jsonl"
    persistence_backend: str = "local_json"     # local_json | postgres
    mrv_store_path: str = "data/mrv_inventories.jsonl"
    document_store_path: str = "data/document_chunks.jsonl"
    admin_document_store_path: str = "data/admin_documents.jsonl"
    audit_events_store_path: str = "data/audit_events.jsonl"
    assets_store_path: str = "data/assets.jsonl"
    asset_relationships_store_path: str = "data/asset_relationships.jsonl"
    tenants_store_path: str = "data/tenants.jsonl"
    users_store_path: str = "data/users.jsonl"
    permits_store_path: str = "data/permits.jsonl"
    conversation_shares_store_path: str = "data/conversation_shares.jsonl"

    # Async document ingestion (A5)
    object_store_backend: str = "s3"             # s3 (MinIO/AWS) | memory (tests)
    object_store_endpoint: str = "http://localhost:9000"   # MinIO local dev
    object_store_region: str = "af-south-1"
    object_store_bucket: str = "petrobrain-docs"
    object_store_access_key: str = ""
    object_store_secret_key: str = ""
    object_store_use_path_style: bool = True

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_always_eager: bool = False        # True in tests; runs in-process

    # Observability
    log_json: bool = True
    otel_endpoint: str = ""
    metrics_enabled: bool = True
    token_cost_redis_enabled: bool = False
    metrics_auth_token: str = ""

    # Basic in-process abuse controls. Production edge/WAF limits still apply,
    # but these protect auth and expensive app routes even on private/internal
    # deployments or demo hosts without WAF.
    auth_rate_limit_per_minute: int = 20
    api_rate_limit_per_minute: int = 120
    upload_rate_limit_per_minute: int = 10

    # Upload malware scanning. Production should point this at clamd TCP/3310
    # and fail closed so documents are never persisted without a clean verdict.
    malware_scan_enabled: bool = False
    malware_scan_host: str = ""
    malware_scan_port: int = 3310
    malware_scan_timeout_seconds: float = 10.0
    malware_scan_fail_closed: bool = False

    # Auth
    jwt_secret: str = "dev-secret-change-me-32-bytes-minimum"  # HS256 local/dev
    jwt_public_key: str = ""                     # RS256 production/SSO public key
    jwt_issuer: str = "petrobrain"
    jwt_audience: str = "petrobrain-api"
    jwt_ttl_hours: int = 12
    # Self-serve signup (POST /auth/signup). Disable to lock the app to
    # admin-invited accounts only.
    enable_self_signup: bool = True
    default_signup_tenant_id: str = "demo"
    default_signup_tenant_name: str = "Demo tenant"
    default_signup_role: str = "engineer"
    # Comma-separated list of emails that get auto-promoted to platform_admin
    # on first signup. Lets the founder bootstrap admin access without having
    # to edit the user store by hand. Lowercased + stripped before compare.
    bootstrap_platform_admin_emails: str = ""
    password_min_length: int = 8

    # RAG
    embedding_model: str = "text-embedding-3-large"
    # Self-hosted embeddings endpoint (Tier B). A single vLLM serves one model,
    # so embeddings may live at a different base than chat; empty falls back to
    # llm_api_base.
    embedding_api_base: str = ""
    retrieval_top_k: int = 12
    rerank_enabled: bool = True
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_cache_dir: str = "/var/cache/petrobrain"
    rerank_top_n: int = 5

    # Safety / tiering
    operational_tier: bool = False            # True => Tier B (on-prem, OT DMZ, read-only)
    sovereign_region: str = "af-south-1"

    # Web search (Tavily). Leave empty to disable; the tool stays registered and
    # returns a structured disabled-payload so the model can decline gracefully.
    tavily_api_key: str = ""

    # Satellite data providers (A3). Public, license-clean sources cross-referenced
    # against reported flaring/methane. Leave empty to keep the provider registered
    # but unavailable (it then reports "not configured" rather than fabricating data).
    # VIIRS Nightfire flaring: NOAA / Earth Observation Group (eogdata.mines.edu).
    # TROPOMI methane: Copernicus Sentinel-5P (dataspace.copernicus.eu).
    viirs_flaring_endpoint: str = ""
    tropomi_methane_endpoint: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_production_settings(settings: Settings) -> None:
    """Fail fast when production is started with known unsafe demo defaults."""
    if settings.environment.lower() not in {"prod", "production"}:
        return
    errors: list[str] = []
    if settings.jwt_secret == "dev-secret-change-me-32-bytes-minimum":
        errors.append("PB_JWT_SECRET must not use the development default")
    if settings.persistence_backend == "local_json":
        errors.append("PB_PERSISTENCE_BACKEND=local_json is not production-safe")
    if settings.enable_self_signup:
        errors.append("PB_ENABLE_SELF_SIGNUP must be false in production")
    origins = {o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()}
    if not origins:
        errors.append("PB_CORS_ALLOW_ORIGINS must not be empty in production")
    if "*" in origins or any("localhost" in o or "127.0.0.1" in o for o in origins):
        errors.append("PB_CORS_ALLOW_ORIGINS must be a production origin allowlist")
    if settings.object_store_backend == "memory":
        errors.append("PB_OBJECT_STORE_BACKEND=memory is not production-safe")
    if (
        settings.object_store_access_key == "minioadmin"
        or settings.object_store_secret_key == "minioadmin"
    ):
        errors.append("object store credentials must not use MinIO defaults")
    if settings.metrics_enabled and not settings.metrics_auth_token:
        errors.append("PB_METRICS_AUTH_TOKEN is required when metrics are enabled in production")
    if settings.metrics_auth_token == "REPLACE_ME_VIA_RUNBOOK":
        errors.append("PB_METRICS_AUTH_TOKEN must not use the placeholder value")
    if settings.llm_provider == "anthropic" and _missing_or_placeholder_secret("ANTHROPIC_API_KEY"):
        errors.append("ANTHROPIC_API_KEY must be set to a real provider key in production")
    if (
        settings.llm_provider != "self_hosted"
        and not settings.embedding_api_base
        and _missing_or_placeholder_secret("OPENAI_API_KEY")
    ):
        errors.append("OPENAI_API_KEY must be set to a real provider key in production")
    if not settings.redis_url.lower().startswith("rediss://"):
        errors.append("PB_REDIS_URL must use rediss:// in production")
    if not settings.celery_broker_url.lower().startswith("rediss://"):
        errors.append("PB_CELERY_BROKER_URL must use rediss:// in production")
    if not settings.celery_result_backend.lower().startswith("rediss://"):
        errors.append("PB_CELERY_RESULT_BACKEND must use rediss:// in production")
    if not settings.malware_scan_enabled:
        errors.append("PB_MALWARE_SCAN_ENABLED must be true in production")
    if not settings.malware_scan_fail_closed:
        errors.append("PB_MALWARE_SCAN_FAIL_CLOSED must be true in production")
    if settings.malware_scan_enabled and not settings.malware_scan_host:
        errors.append("PB_MALWARE_SCAN_HOST is required when malware scanning is enabled")
    if errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))


def _missing_or_placeholder_secret(name: str) -> bool:
    value = (os.getenv(name) or "").strip()
    if not value:
        return True
    lowered = value.lower()
    return (
        value == "REPLACE_ME_VIA_RUNBOOK"
        or "..." in value
        or "change-me" in lowered
        or "replace" in lowered
    )
