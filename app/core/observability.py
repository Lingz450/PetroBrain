"""Structured logging, tracing, metrics, and token counters."""
from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.config import Settings, get_settings
from app.core.redis_security import redis_ssl_options


HTTP_REQUESTS = Counter(
    "petrobrain_http_requests_total",
    "HTTP requests handled by PetroBrain.",
    ("method", "path", "status_code"),
)
HTTP_REQUEST_DURATION = Histogram(
    "petrobrain_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "path"),
)
CHAT_TURNS = Counter(
    "petrobrain_chat_turns_total",
    "Chat turns by tenant, module, and model.",
    ("tenant_id", "module", "model"),
)
TOOL_CALLS = Counter(
    "petrobrain_tool_calls_total",
    "Deterministic tool calls by tenant, module, and tool.",
    ("tenant_id", "module", "tool"),
)
GUARDRAIL_FLAGS = Counter(
    "petrobrain_guardrail_flags_total",
    "Guardrail flags by tenant, module, and flag.",
    ("tenant_id", "module", "flag"),
)
LLM_TOKENS = Counter(
    "petrobrain_llm_tokens_total",
    "LLM token usage by tenant, module, and direction.",
    ("tenant_id", "module", "direction"),
)
CHAT_LATENCY = Histogram(
    "petrobrain_chat_latency_seconds",
    "Chat route latency in seconds.",
    ("tenant_id", "module"),
)

_otel_configured = False
_instrumented_fastapi_ids: set[int] = set()
_httpx_instrumented = False
_asyncpg_instrumented = False


def configure_logging(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if s.log_json else structlog.dev.ConsoleRenderer()
    )
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def configure_tracing(app: FastAPI, settings: Settings | None = None) -> None:
    global _otel_configured, _httpx_instrumented, _asyncpg_instrumented
    s = settings or get_settings()

    if not _otel_configured:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

        provider = TracerProvider(resource=Resource.create({
            "service.name": s.app_name,
            "deployment.environment": s.environment,
        }))
        if s.otel_endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporter: SpanExporter = OTLPSpanExporter(endpoint=s.otel_endpoint, insecure=True)
        else:
            class LocalLogSpanExporter(SpanExporter):
                def export(self, spans):
                    span_logger = structlog.get_logger("petrobrain.traces")
                    for span in spans:
                        span_logger.info(
                            "span",
                            name=span.name,
                            trace_id=f"{span.context.trace_id:032x}",
                            span_id=f"{span.context.span_id:016x}",
                        )
                    return SpanExportResult.SUCCESS

                def shutdown(self) -> None:
                    return None

            exporter = LocalLogSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        try:
            trace.set_tracer_provider(provider)
        except Exception:  # pragma: no cover - provider can already be set by tests/runtime
            pass
        _otel_configured = True

    if id(app) not in _instrumented_fastapi_ids:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        _instrumented_fastapi_ids.add(id(app))
    if not _httpx_instrumented:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        _httpx_instrumented = True
    if not _asyncpg_instrumented:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
        _asyncpg_instrumented = True


def install_request_metrics(app: FastAPI) -> None:
    if getattr(app.state, "petrobrain_metrics_middleware", False):
        return

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        path = request.url.path
        method = request.method
        started = perf_counter()
        status_code = "500"
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        finally:
            elapsed = perf_counter() - started
            HTTP_REQUESTS.labels(method, path, status_code).inc()
            HTTP_REQUEST_DURATION.labels(method, path).observe(elapsed)

    app.state.petrobrain_metrics_middleware = True


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_chat_turn(
    *,
    tenant_id: str,
    module: str,
    model: str,
    latency_seconds: float,
    usage: dict[str, Any],
    tool_results: list[dict[str, Any]],
    flags: list[str],
) -> None:
    CHAT_TURNS.labels(tenant_id, module, model or "unknown").inc()
    CHAT_LATENCY.labels(tenant_id, module).observe(latency_seconds)
    for direction in ("input", "output"):
        value = usage.get(direction, 0) if isinstance(usage, dict) else 0
        if isinstance(value, (int, float)) and value:
            LLM_TOKENS.labels(tenant_id, module, direction).inc(float(value))
    for tr in tool_results or []:
        TOOL_CALLS.labels(tenant_id, module, str(tr.get("tool") or "unknown")).inc()
    for flag in flags or []:
        GUARDRAIL_FLAGS.labels(tenant_id, module, str(flag)).inc()


def increment_token_cost_counters(
    *,
    tenant_id: str,
    module: str,
    usage: dict[str, Any],
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()
    if not s.token_cost_redis_enabled or not isinstance(usage, dict):
        return
    total = 0
    for value in usage.values():
        if isinstance(value, (int, float)):
            total += int(value)
    if total <= 0:
        return
    try:
        import redis

        client = redis.Redis.from_url(
            s.redis_url,
            socket_connect_timeout=0.05,
            socket_timeout=0.05,
            decode_responses=True,
            **redis_ssl_options(s.redis_url, s),
        )
        pipe = client.pipeline()
        pipe.hincrby(f"petrobrain:tokens:{tenant_id}", module, total)
        pipe.hincrby("petrobrain:tokens:all", tenant_id, total)
        pipe.execute()
    except Exception:
        structlog.get_logger(__name__).warning(
            "token_counter_unavailable",
            tenant_id=tenant_id,
            module=module,
        )


def setup_observability(app: FastAPI, settings: Settings | None = None) -> None:
    s = settings or get_settings()
    configure_logging(s)
    configure_tracing(app, s)
    if s.metrics_enabled:
        install_request_metrics(app)
