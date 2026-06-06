"""Non-streaming POST /chat must return retrieved citations in the JSON body
(previously they only landed in SSE citation events)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.api import deps, routes_chat
from app.core.audit import AuditLogger
from app.core.llm_service import LLMResponse
from app.core.orchestrator import Orchestrator
from app.db.audit_events_repository import LocalJsonAuditEventsRepository
from app.main import app
from tests.auth_helpers import auth_headers, jwt_settings

client = TestClient(app)

_HITS = [
    {"text": "Handover requires a verbal brief.", "title": "Ops SOP", "revision": "B", "clause": "7.4"},
    {"text": "Record the shift log.", "title": "NUPRC Guideline", "revision": "2024", "clause": "3.1"},
]


class _FakeRetriever:
    async def retrieve(self, text, *, tenant_id, asset=None, assets=None):
        return _HITS


class _FakeLLM:
    async def complete(self, system_prompt, messages, tools=None):
        return LLMResponse(text="Per the SOP, brief the incoming crew.", tool_calls=[],
                           usage={"input": 3, "output": 6}, model="fake")


@pytest.fixture(autouse=True)
def wire(monkeypatch, tmp_path):
    monkeypatch.setattr(deps, "get_settings", jwt_settings)
    monkeypatch.setattr(routes_chat, "audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(routes_chat, "_events_repository",
                        lambda: LocalJsonAuditEventsRepository(tmp_path / "audit_events.jsonl"))
    monkeypatch.setattr(routes_chat, "_orch",
                        Orchestrator(retriever=_FakeRetriever(), llm=_FakeLLM()))


def test_non_streaming_chat_returns_citations():
    r = client.post("/chat", headers=auth_headers(),
                    json={"message": "explain the shift handover procedure", "module": "general"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [
        (row["title"], row["revision"], row["clause"])
        for row in body["citations"]
    ] == [
        ("Ops SOP", "B", "7.4"),
        ("NUPRC Guideline", "2024", "3.1"),
    ]
    assert all(row["reliability"] == "primary" for row in body["citations"])
    assert all(row["quality_score"] == 100 for row in body["citations"])


def test_citations_empty_without_retriever():
    monkeypatchless = Orchestrator(llm=_FakeLLM())  # no retriever
    routes_chat._orch = monkeypatchless
    r = client.post("/chat", headers=auth_headers(),
                    json={"message": "explain the shift handover procedure", "module": "general"})
    assert r.status_code == 200, r.text
    assert r.json()["citations"] == []
