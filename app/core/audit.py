"""Append-only audit logging for Phase-1 API activity."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.core.audit_hash import sha256_canonical


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
    """Append-only logger with a per-row hash chain (H7).

    Each row gets ``prev_hash`` (the previous row's ``row_hash``, "" on the
    first row) and ``row_hash = sha256_canonical({prev_hash, redacted_event})``.
    Any insertion, deletion, or in-place edit of a row breaks the chain at the
    affected row and every row after it. ``verify_chain()`` walks the file and
    reports the first break, which is enough for an audit-trail integrity check
    without needing an external store.

    NOTE: this is tamper-EVIDENT, not tamper-PROOF. A privileged attacker with
    write access to the file can recompute the chain end-to-end. The Phase-2
    follow-up ships rows off-host (CloudWatch / Kinesis / signed-anchor) for
    actual tamper resistance.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._chain_lock = Lock()
        self._tail_hash: str | None = None

    def write(self, event: AuditEvent) -> dict[str, Any]:
        record = _redact(event.as_record())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._chain_lock:
            prev = self._load_tail_hash()
            # Hash over the event PAYLOAD (no chain fields), with prev_hash
            # mixed in as a sibling so the chain order participates in the
            # digest. verify_chain reconstructs this exact shape.
            row_hash = sha256_canonical({"prev_hash": prev, "event": record})
            record["prev_hash"] = prev
            record["row_hash"] = row_hash
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=_json_default, sort_keys=True) + "\n")
            self._tail_hash = row_hash
        return record

    def _load_tail_hash(self) -> str:
        if self._tail_hash is not None:
            return self._tail_hash
        if not self.path.exists():
            self._tail_hash = ""
            return ""
        last = ""
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line).get("row_hash") or ""
                except Exception:  # noqa: BLE001
                    pass
        self._tail_hash = last
        return last


def verify_chain(path: str | Path) -> tuple[bool, int | None]:
    """Walk the audit log and return (ok, broken_at_line_or_None). A line is
    broken if its ``prev_hash`` doesn't match the previous row's ``row_hash``
    or if its ``row_hash`` doesn't match the recomputed value."""
    p = Path(path)
    if not p.exists():
        return True, None
    prev_hash = ""
    with p.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return False, idx
            if record.get("prev_hash") != prev_hash:
                return False, idx
            expected = {"prev_hash": prev_hash,
                        "event": {k: v for k, v in record.items()
                                  if k not in {"prev_hash", "row_hash"}}}
            if sha256_canonical(expected) != record.get("row_hash"):
                return False, idx
            prev_hash = record["row_hash"]
    return True, None


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
