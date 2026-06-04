"""H7: audit log is a hash chain. Any tamper breaks verify_chain."""
from __future__ import annotations

import json

from app.core.audit import AuditEvent, AuditLogger, verify_chain


def _event(i: int) -> AuditEvent:
    return AuditEvent(
        event_type="chat_turn",
        tenant_id="demo",
        user_id=f"u{i}",
        role="engineer",
        route="/chat",
        request={"request_hash": f"hash-{i}"},
        response={"response_hash": f"resp-{i}"},
    )


def test_chain_grows_correctly(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    for i in range(5):
        logger.write(_event(i))
    ok, broken = verify_chain(path)
    assert ok and broken is None


def test_inserted_row_breaks_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    for i in range(3):
        logger.write(_event(i))
    # Splice a forged row in the middle.
    rows = path.read_text(encoding="utf-8").splitlines()
    forged = json.dumps({
        "event_type": "chat_turn", "tenant_id": "demo", "user_id": "INTRUDER",
        "role": "engineer", "route": "/chat",
        "request": {"x": 1}, "prev_hash": "wrong", "row_hash": "alsowrong",
    })
    rows.insert(1, forged)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    ok, broken = verify_chain(path)
    assert not ok
    assert broken == 2  # the forged row (1-indexed; line 1 still valid)


def test_edited_row_breaks_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    for i in range(3):
        logger.write(_event(i))
    rows = path.read_text(encoding="utf-8").splitlines()
    # Edit row 2's user_id without recomputing the hash.
    row = json.loads(rows[1])
    row["user_id"] = "wasnt-me"
    rows[1] = json.dumps(row, sort_keys=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    ok, broken = verify_chain(path)
    assert not ok
    assert broken == 2


def test_existing_file_continues_chain_after_restart(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    logger.write(_event(0))
    logger.write(_event(1))

    # Simulate a process restart by building a new logger that reads tail.
    logger2 = AuditLogger(path)
    logger2.write(_event(2))

    ok, broken = verify_chain(path)
    assert ok and broken is None
