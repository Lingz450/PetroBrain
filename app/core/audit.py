"""Append-only audit logging for Phase-1 API activity."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import get_settings


@dataclass
class AuditEvent:
    event_type: str
    tenant_id: str
    user_id: str
    role: str
    route: str
    request: dict[str, Any]
    response: dict[str, Any] | None = None
    flags: list[str] | None = None
    tool_results: list[dict[str, Any]] | None = None
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    event_id: str = ""
    timestamp_utc: str = ""

    def as_record(self) -> dict[str, Any]:
        record = asdict(self)
        if not record["event_id"]:
            record["event_id"] = str(uuid4())
        if not record["timestamp_utc"]:
            record["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        return {k: v for k, v in record.items() if v is not None}


class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, event: AuditEvent) -> dict[str, Any]:
        record = _redact(event.as_record())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=_json_default, sort_keys=True) + "\n")
        return record


def get_audit_logger() -> AuditLogger:
    return AuditLogger(get_settings().audit_log_path)


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if hasattr(value, "as_dict"):
        return value.as_dict()
    return str(value)


_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "authorization",
    "api_key",
    "secret",
    "object_store_secret_key",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if (
                lowered in _SENSITIVE_KEYS
                or lowered.endswith("_token")
                or lowered.endswith("_secret")
            ):
                out[key] = "[REDACTED]"
            else:
                out[key] = _redact(item)
        return out
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
