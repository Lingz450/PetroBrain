"""
Tenant-scoped prompt memory (slice 2 of the learning loop).

Persistence pluggable like the rest of the data layer: LocalJson in dev,
Postgres + RLS in prod. Same shape both ways so the API and orchestrator
don't care which is wired.

What lives here:
  * One row = one short sentence injected into the system prompt for every
    chat turn in that tenant.
  * Append-then-archive: rows are never hard-deleted; ``status='archived'``
    removes the row from prompt assembly but keeps the audit trail.
  * Source of truth for the orchestrator's per-tenant context (see
    ``app.core.prompts.build_system_prompt``).

What does NOT live here:
  * Cross-tenant facts. Every read is tenant-scoped two ways: in-app filter
    + Postgres RLS.
  * Engineering constants / IPCC GWPs / safety thresholds. Those stay in the
    deterministic calc engine.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.core.memory_guard import check_memory_body


VALID_KINDS = {"terminology", "preference", "context"}
VALID_SOURCES = {"manual", "promoted_feedback"}
VALID_STATUSES = {"active", "archived"}


@dataclass
class MemoryRecord:
    id: str
    tenant_id: str
    kind: str
    body: str
    source: str
    source_feedback_id: str | None
    status: str
    created_by: str
    created_utc: str
    updated_utc: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate(*, kind: str, source: str, body: str) -> None:
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {sorted(VALID_KINDS)}")
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(VALID_SOURCES)}")
    guard = check_memory_body(body)
    if not guard.ok:
        raise ValueError(guard.reason)


class LocalJsonTenantMemoryRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def create(
        self, *, tenant_id: str, kind: str, body: str, created_by: str,
        source: str = "manual", source_feedback_id: str | None = None,
    ) -> MemoryRecord:
        if not tenant_id or not created_by:
            raise ValueError("tenant_id and created_by are required")
        _validate(kind=kind, source=source, body=body)
        now = _now()
        with self._lock:
            rows = self._read_all_locked()
            record = MemoryRecord(
                id=str(uuid4()), tenant_id=tenant_id, kind=kind, body=body.strip(),
                source=source, source_feedback_id=source_feedback_id,
                status="active", created_by=created_by,
                created_utc=now, updated_utc=now,
            )
            rows.append(record.as_dict())
            self._write_all_locked(rows)
            return record

    def update(
        self, *, tenant_id: str, memory_id: str,
        body: str | None = None, kind: str | None = None,
        status: str | None = None,
    ) -> MemoryRecord:
        with self._lock:
            rows = self._read_all_locked()
            for row in rows:
                if row["tenant_id"] == tenant_id and row["id"] == memory_id:
                    if body is not None:
                        guard = check_memory_body(body)
                        if not guard.ok:
                            raise ValueError(guard.reason)
                        row["body"] = body.strip()
                    if kind is not None:
                        if kind not in VALID_KINDS:
                            raise ValueError(f"kind must be one of {sorted(VALID_KINDS)}")
                        row["kind"] = kind
                    if status is not None:
                        if status not in VALID_STATUSES:
                            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
                        row["status"] = status
                    row["updated_utc"] = _now()
                    self._write_all_locked(rows)
                    return MemoryRecord(**row)
            raise KeyError(f"memory {memory_id!r} not found in tenant {tenant_id!r}")

    def list_records(
        self, *, tenant_id: str, status: str | None = "active",
        kind: str | None = None, limit: int = 200, offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = [r for r in self._read_all() if r["tenant_id"] == tenant_id]
        if status is not None:
            rows = [r for r in rows if r.get("status") == status]
        if kind is not None:
            rows = [r for r in rows if r.get("kind") == kind]
        rows.sort(key=lambda r: r.get("created_utc", ""))
        return rows[offset: offset + limit]

    def get(self, *, tenant_id: str, memory_id: str) -> dict[str, Any] | None:
        for row in self._read_all():
            if row["tenant_id"] == tenant_id and row["id"] == memory_id:
                return row
        return None

    def list_for_prompt(self, *, tenant_id: str) -> list[str]:
        """Bodies of active memories, oldest-first. Caller is responsible for
        applying the size cap; this method only filters and orders."""
        return [
            r["body"]
            for r in self.list_records(tenant_id=tenant_id, status="active", limit=10_000)
            if r.get("body")
        ]

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


class PostgresTenantMemoryRepository:
    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn

    def create(
        self, *, tenant_id: str, kind: str, body: str, created_by: str,
        source: str = "manual", source_feedback_id: str | None = None,
    ) -> MemoryRecord:
        if not tenant_id or not created_by:
            raise ValueError("tenant_id and created_by are required")
        _validate(kind=kind, source=source, body=body)
        with _pg_tenant(tenant_id, self.dsn) as conn:
            row = conn.execute(
                f"INSERT INTO tenant_memories "
                f"(id, tenant_id, kind, body, source, source_feedback_id, "
                f" status, created_by) "
                f"VALUES (COALESCE(%s, gen_random_uuid()::text), %s, %s, %s, %s, %s, "
                f"        'active', %s) "
                f"RETURNING {_COLUMNS}",
                (None, tenant_id, kind, body.strip(), source, source_feedback_id,
                 created_by),
            ).fetchone()
        return _row_to_record(row)

    def update(
        self, *, tenant_id: str, memory_id: str,
        body: str | None = None, kind: str | None = None,
        status: str | None = None,
    ) -> MemoryRecord:
        sets: list[str] = []
        params: list[Any] = []
        if body is not None:
            guard = check_memory_body(body)
            if not guard.ok:
                raise ValueError(guard.reason)
            sets.append("body = %s")
            params.append(body.strip())
        if kind is not None:
            if kind not in VALID_KINDS:
                raise ValueError(f"kind must be one of {sorted(VALID_KINDS)}")
            sets.append("kind = %s")
            params.append(kind)
        if status is not None:
            if status not in VALID_STATUSES:
                raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
            sets.append("status = %s")
            params.append(status)
        if not sets:
            existing = self.get(tenant_id=tenant_id, memory_id=memory_id)
            if existing is None:
                raise KeyError(f"memory {memory_id!r} not found in tenant {tenant_id!r}")
            return MemoryRecord(**existing)
        sets.append("updated_utc = now()")
        params.extend([tenant_id, memory_id])
        sql = (
            f"UPDATE tenant_memories SET {', '.join(sets)} "
            f"WHERE tenant_id = %s AND id = %s RETURNING {_COLUMNS}"
        )
        with _pg_tenant(tenant_id, self.dsn) as conn:
            row = conn.execute(sql, params).fetchone()
        if row is None:
            raise KeyError(f"memory {memory_id!r} not found in tenant {tenant_id!r}")
        return _row_to_record(row)

    def list_records(
        self, *, tenant_id: str, status: str | None = "active",
        kind: str | None = None, limit: int = 200, offset: int = 0,
    ) -> list[dict[str, Any]]:
        where = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if status is not None:
            where.append("status = %s")
            params.append(status)
        if kind is not None:
            where.append("kind = %s")
            params.append(kind)
        params.extend([limit, offset])
        sql = (
            f"SELECT {_COLUMNS} FROM tenant_memories WHERE {' AND '.join(where)} "
            f"ORDER BY created_utc ASC LIMIT %s OFFSET %s"
        )
        with _pg_tenant(tenant_id, self.dsn) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_serialize_row(r) for r in rows]

    def get(self, *, tenant_id: str, memory_id: str) -> dict[str, Any] | None:
        with _pg_tenant(tenant_id, self.dsn) as conn:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM tenant_memories "
                f"WHERE tenant_id = %s AND id = %s",
                (tenant_id, memory_id),
            ).fetchone()
        return _serialize_row(row) if row else None

    def list_for_prompt(self, *, tenant_id: str) -> list[str]:
        return [
            r["body"]
            for r in self.list_records(tenant_id=tenant_id, status="active", limit=10_000)
            if r.get("body")
        ]


_COLUMNS = (
    "id, tenant_id, kind, body, source, source_feedback_id, status, "
    "created_by, created_utc, updated_utc"
)


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for k in ("created_utc", "updated_utc"):
        if isinstance(out.get(k), datetime):
            out[k] = out[k].isoformat()
    return out


def _row_to_record(row: dict[str, Any]) -> MemoryRecord:
    return MemoryRecord(**_serialize_row(row))


def _pg_tenant(tenant_id: str, dsn: str | None):
    from app.db import pg

    return pg.tenant_connection(tenant_id, dsn=dsn, dict_rows=True)


def get_tenant_memory_repository():
    settings = get_settings()
    if settings.persistence_backend == "postgres":
        return PostgresTenantMemoryRepository(settings.database_url)
    return LocalJsonTenantMemoryRepository(settings.tenant_memory_store_path)
