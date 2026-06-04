"""
Celery application for PetroBrain async ingestion.

Tier-A spine runs Celery against Redis. Tier-B (on-prem) reuses the same
broker URL pointed at an in-DMZ Redis. The application object is exposed as
``celery_app`` so it can be run with ``celery -A app.workers.celery_app worker``.
"""
from __future__ import annotations

from celery import Celery

from app.config import get_settings
from app.core.redis_security import redis_ssl_options


def build_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "petrobrain",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.workers.ingest_worker"],
    )
    app.conf.task_always_eager = settings.celery_task_always_eager
    app.conf.task_eager_propagates = settings.celery_task_always_eager
    app.conf.task_acks_late = True
    app.conf.task_default_queue = "petrobrain.ingest"
    app.conf.worker_max_tasks_per_child = 100
    app.conf.broker_connection_retry_on_startup = True
    broker_ssl = redis_ssl_options(settings.celery_broker_url, settings)
    if broker_ssl:
        app.conf.broker_use_ssl = broker_ssl
    backend_ssl = redis_ssl_options(settings.celery_result_backend, settings)
    if backend_ssl:
        app.conf.redis_backend_use_ssl = backend_ssl
    return app


celery_app = build_celery_app()
