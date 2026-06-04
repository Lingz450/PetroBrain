import pytest

from app.config import Settings, validate_production_settings


def _prod_settings(**overrides):
    values = {
        "environment": "prod",
        "jwt_secret": "x" * 48,
        "persistence_backend": "postgres",
        "enable_self_signup": False,
        "cors_allow_origins": "https://app.example.com,https://admin.example.com",
        "object_store_backend": "s3",
        "object_store_access_key": "",
        "object_store_secret_key": "",
        "metrics_enabled": True,
        "metrics_auth_token": "m" * 40,
        "llm_provider": "anthropic",
        "embedding_api_base": "",
        "redis_url": "rediss://:secret@redis.example.com:6379/0",
        "celery_broker_url": "rediss://:secret@redis.example.com:6379/1",
        "celery_result_backend": "rediss://:secret@redis.example.com:6379/2",
        "malware_scan_enabled": True,
        "malware_scan_fail_closed": True,
        "malware_scan_host": "127.0.0.1",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_accept_real_deployed_values(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-value")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-value")

    validate_production_settings(_prod_settings())


def test_production_settings_reject_empty_cors(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-value")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-value")

    with pytest.raises(RuntimeError, match="PB_CORS_ALLOW_ORIGINS"):
        validate_production_settings(_prod_settings(cors_allow_origins=""))


def test_production_settings_reject_placeholder_provider_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-...")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-...")

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        validate_production_settings(_prod_settings())


def test_production_settings_reject_enabled_self_signup(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-value")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-value")

    with pytest.raises(RuntimeError, match="PB_ENABLE_SELF_SIGNUP"):
        validate_production_settings(_prod_settings(enable_self_signup=True))


def test_tier_a_prod_rejects_plaintext_redis(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-value")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-value")

    with pytest.raises(RuntimeError, match="PB_REDIS_URL"):
        validate_production_settings(
            _prod_settings(redis_url="redis://:secret@redis.example.com:6379/0")
        )


@pytest.mark.parametrize(
    "bad_origin,fragment",
    [
        ("http://app.example.com", "https://"),
        ("https://localhost", "loopback"),
        ("https://127.0.0.1", "loopback"),
        ("https://*.example.com", "wildcard"),
        ("https://user:pass@app.example.com", "userinfo"),
        ("https://app.example.com/admin", "path"),
        ("https://app.example.com?x=1", "query"),
    ],
)
def test_production_settings_reject_unsafe_cors_entries(monkeypatch, bad_origin, fragment):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-value")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-value")
    with pytest.raises(RuntimeError, match=fragment):
        validate_production_settings(
            _prod_settings(cors_allow_origins=f"https://app.example.com,{bad_origin}")
        )


def test_tier_b_prod_allows_plaintext_redis_on_dmz_bridge(monkeypatch):
    """Tier B runs inside the OT DMZ on a Docker bridge with no egress; the
    rediss:// requirement is relaxed because the conduit never leaves the
    boundary. The Tier-A check above still enforces TLS for cloud deployments."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-value")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-value")

    validate_production_settings(
        _prod_settings(
            operational_tier=True,
            llm_provider="self_hosted",
            embedding_api_base="http://vllm-embed:8000",
            redis_url="redis://:secret@redis:6379/0",
            celery_broker_url="redis://:secret@redis:6379/1",
            celery_result_backend="redis://:secret@redis:6379/2",
        )
    )
