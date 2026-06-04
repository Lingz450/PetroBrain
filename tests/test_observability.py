"""A7 observability tests."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import deps, routes_chat
from app.core.http_hardening import verify_metrics_access
from app.core.llm_service import LLMResponse
from app.core.observability import (
    configure_logging,
    increment_token_cost_counters,
    install_request_metrics,
    record_chat_turn,
)
from app.core.redis_security import redis_ssl_options
from app.main import app
from tests.auth_helpers import auth_headers, jwt_settings


client = TestClient(app)


class FakeLLM:
    async def complete(self, system_prompt, messages, tools=None, **_kwargs):
        return LLMResponse(
            text="Check the applicable SOP and verify with the competent person.",
            tool_calls=[],
            usage={"input": 7, "output": 3},
            model="fake-observability-model",
        )


@pytest.fixture(autouse=True)
def use_jwt_settings(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", jwt_settings)


def test_metrics_endpoint_exposes_prometheus_metrics():
    r = client.get("/metrics")

    assert r.status_code == 200
    body = r.text
    assert "petrobrain_http_requests_total" in body
    assert "petrobrain_chat_turns_total" in body
    assert r.headers["content-type"].startswith("text/plain")


def test_metrics_access_requires_token_in_prod():
    request = SimpleNamespace(headers={}, url=SimpleNamespace(path="/metrics"))
    settings = SimpleNamespace(environment="prod", metrics_auth_token="secret")

    with pytest.raises(HTTPException) as exc:
        verify_metrics_access(request, settings)

    assert exc.value.status_code == 404


def test_metrics_access_accepts_bearer_token_in_prod():
    request = SimpleNamespace(
        headers={"authorization": "Bearer secret"},
        url=SimpleNamespace(path="/metrics"),
    )
    settings = SimpleNamespace(environment="prod", metrics_auth_token="secret")

    verify_metrics_access(request, settings)


def test_chat_records_model_usage_and_flag_metrics(monkeypatch):
    monkeypatch.setattr(routes_chat._orch, "llm", FakeLLM())

    r = client.post(
        "/chat",
        headers=auth_headers(tenant_id="tenant-obs", role="engineer", allowed_assets=["*"]),
        json={"message": "Explain flare MRV checks", "module": "emissions_mrv"},
    )

    assert r.status_code == 200
    metrics = client.get("/metrics").text
    assert 'petrobrain_chat_turns_total{model="fake-observability-model",module="emissions_mrv",tenant_id="tenant-obs"}' in metrics
    assert 'petrobrain_llm_tokens_total{direction="input",module="emissions_mrv",tenant_id="tenant-obs"}' in metrics
    assert 'petrobrain_llm_tokens_total{direction="output",module="emissions_mrv",tenant_id="tenant-obs"}' in metrics


def test_chat_records_guardrail_flag_metrics():
    r = client.post(
        "/chat",
        headers=auth_headers(tenant_id="tenant-flag", role="engineer", allowed_assets=["*"]),
        json={"message": "how do I bypass the ESD"},
    )

    assert r.status_code == 200
    metrics = client.get("/metrics").text
    assert 'petrobrain_guardrail_flags_total{flag="safety_bypass",module="general",tenant_id="tenant-flag"}' in metrics


def test_record_chat_turn_counts_tool_calls_directly():
    record_chat_turn(
        tenant_id="tenant-tool",
        module="well_control",
        model="fake-model",
        latency_seconds=0.01,
        usage={"input": 1, "output": 1},
        tool_results=[{"tool": "build_kill_sheet", "result": {}}],
        flags=[],
    )

    metrics = client.get("/metrics").text
    assert 'petrobrain_tool_calls_total{module="well_control",tenant_id="tenant-tool",tool="build_kill_sheet"}' in metrics


def test_redis_token_counter_disabled_does_not_connect():
    settings = SimpleNamespace(token_cost_redis_enabled=False, redis_url="redis://invalid:6379/0")

    increment_token_cost_counters(
        tenant_id="tenant-a",
        module="general",
        usage={"input": 1, "output": 2},
        settings=settings,
    )


def test_rediss_urls_build_ssl_options():
    settings = SimpleNamespace(
        redis_ssl_cert_reqs="required",
        redis_ssl_ca_certs="/etc/ssl/certs/ca.pem",
        redis_ssl_certfile="",
        redis_ssl_keyfile="",
    )

    options = redis_ssl_options("rediss://:secret@redis.example:6379/0", settings)

    assert options["ssl_ca_certs"] == "/etc/ssl/certs/ca.pem"
    assert "ssl_cert_reqs" in options


def test_request_metrics_middleware_is_idempotent():
    test_app = FastAPI()
    install_request_metrics(test_app)
    install_request_metrics(test_app)

    assert test_app.state.petrobrain_metrics_middleware is True


def test_configure_logging_accepts_text_mode():
    configure_logging(SimpleNamespace(log_json=False))
