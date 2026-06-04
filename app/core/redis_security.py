"""Redis URL TLS helpers shared by API and Celery clients."""
from __future__ import annotations

import ssl
from typing import Any

from app.config import Settings


_CERT_REQS = {
    "required": ssl.CERT_REQUIRED,
    "none": ssl.CERT_NONE,
    "optional": ssl.CERT_OPTIONAL,
}


def redis_ssl_options(url: str, settings: Settings) -> dict[str, Any]:
    """Return redis-py/Celery SSL kwargs for rediss:// URLs."""
    if not url.lower().startswith("rediss://"):
        return {}
    cert_reqs = _CERT_REQS.get(settings.redis_ssl_cert_reqs.lower())
    if cert_reqs is None:
        raise ValueError("PB_REDIS_SSL_CERT_REQS must be one of required, optional, none")
    options: dict[str, Any] = {"ssl_cert_reqs": cert_reqs}
    if settings.redis_ssl_ca_certs:
        options["ssl_ca_certs"] = settings.redis_ssl_ca_certs
    if settings.redis_ssl_certfile:
        options["ssl_certfile"] = settings.redis_ssl_certfile
    if settings.redis_ssl_keyfile:
        options["ssl_keyfile"] = settings.redis_ssl_keyfile
    return options
