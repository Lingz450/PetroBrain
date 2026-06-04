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
