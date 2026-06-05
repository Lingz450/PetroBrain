"""
Per-tenant user-error feed for the admin Learning page.

Frontend reports errors here when a user-facing operation fails (chat
stream non-2xx, feedback POST failure, file upload failure, etc.). Admin
reads the latest N via /admin/errors and surfaces them on /admin so
issues are visible in real time without grepping audit logs.

Strict tenant isolation: in-app filter + Postgres RLS via the
`petrobrain.tenant_id` GUC. Append-only from the app side - no update
or delete API surface.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from app.config import get_settings


@dataclass
class ErrorEventRecord:
    id: str
    tenant_id: str
    user_id: str
    role: str
    route: str
    status: int | None
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_utc: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate(*, message: str) -> None:
    if not isinstance(message, str) or not message.strip():
        raise ValueError("error message is required")
    # Cap loosely - chat stream error strings, JSON.stringified detail
    # bodies, fetch error toString() are all well under 4 KB.
    if len(message) > 4000:
        raise ValueError("error message is too long (max 4000 chars)")


class LocalJsonErrorEventsRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def append(
        self, *, tenant_id: str, user_id: str, role: str, route: str,
        status: int | None, message: str,
        metadata: dict[str, Any] | None = None,
    ) -> ErrorEventRecord:
        if not tenant_id or not user_id or not role:
            raise ValueError("tenant_id, user_id, role are required")
        _validate(message=message)
        with self._lock:
            rows = self._read_all_locked()
            record = ErrorEventRecord(
                id=str(uuid4()), tenant_id=tenant_id, user_id=user_id,
                role=role, route=route or "/", status=status,
                message=message.strip(), metadata=metadata or {},
                created_utc=_now(),
            )
            rows.append(record.as_dict())
            self._write_all_locked(rows)
            return record

    def list_records(
        self, *, tenant_id: str, limit: int = 50, offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = [r for r in self._read_all() if r["tenant_id"] == tenant_id]
        rows.sort(key=lambda r: r.get("created_utc", ""), reverse=True)
        return rows[offset: offset + limit]

    def count(self, *, tenant_id: str) -> int:
        return sum(1 for r in self._read_all() if r["tenant_id"] == tenant_id)

    def _read_all(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_all_locked()

    def _read_all_locked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def _write_all_locked(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True) + "\n")


class PostgresErrorEventsRepository:
    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn

    def append(
        self, *, tenant_id: str, user_id: str, role: str, route: str,
        status: int | None, message: str,
        metadata: dict[str, Any] | None = None,
    ) -> ErrorEventRecord:
        if not tenant_id or not user_id or not role:
            raise ValueError("tenant_id, user_id, role are required")
        _validate(message=message)
        from psycopg.types.json import Json
        with _pg_tenant(tenant_id, self.dsn) as conn:
            row = conn.execute(
                f"INSERT INTO error_events "
                f"(id, tenant_id, user_id, role, route, status, message, metadata) "
                f"VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, %s, %s) "
                f"RETURNING {_COLUMNS}",
                (tenant_id, user_id, role, route or "/", status,
                 message.strip(), Json(metadata or {})),
            ).fetchone()
        return _row_to_record(row)

    def list_records(
        self, *, tenant_id: str, limit: int = 50, offset: int = 0,
    ) -> list[dict[str, Any]]:
        with _pg_tenant(tenant_id, self.dsn) as conn:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM error_events "
                f"WHERE tenant_id = %s "
                f"ORDER BY created_utc DESC LIMIT %s OFFSET %s",
                (tenant_id, limit, offset),
            ).fetchall()
        return [_serialize_row(r) for r in rows]

    def count(self, *, tenant_id: str) -> int:
        with _pg_tenant(tenant_id, self.dsn) as conn:
            row = conn.execute(
                "SELECT count(*) AS n FROM error_events WHERE tenant_id = %s",
                (tenant_id,),
            ).fetchone()
        return int(row["n"])


_COLUMNS = (
    "id, tenant_id, user_id, role, route, status, message, metadata, created_utc"
)


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if isinstance(out.get("created_utc"), datetime):
        out["created_utc"] = out["created_utc"].isoformat()
    return out


def _row_to_record(row: dict[str, Any]) -> ErrorEventRecord:
    return ErrorEventRecord(**_serialize_row(row))


def _pg_tenant(tenant_id: str, dsn: str | None):
    from app.db import pg

    return pg.tenant_connection(tenant_id, dsn=dsn, dict_rows=True)


def get_error_events_repository():
    settings = get_settings()
    if settings.persistence_backend == "postgres":
        return PostgresErrorEventsRepository(settings.database_url)
    return LocalJsonErrorEventsRepository(settings.error_events_store_path)
