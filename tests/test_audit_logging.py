"""Audit logging tests for Phase-1 API routes."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api import routes_chat, routes_documents, routes_emissions, routes_wellcontrol
from app.core.audit import AuditEvent, AuditLogger
from app.db.document_repository import LocalJsonDocumentRepository
from app.main import app
from tests.auth_helpers import auth_headers, jwt_settings


client = TestClient(app)
AUTH = auth_headers()


@pytest.fixture(autouse=True)
def use_jwt_settings(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", jwt_settings)


def install_temp_audit_log(monkeypatch, tmp_path):
    logger = AuditLogger(tmp_path / "audit.jsonl")
    monkeypatch.setattr(routes_chat, "audit_logger", logger)
    monkeypatch.setattr(routes_wellcontrol, "audit_logger", logger)
    monkeypatch.setattr(routes_emissions, "audit_logger", logger)
    monkeypatch.setattr(routes_documents, "audit_logger", logger)
    return logger


def read_events(logger):
    return [json.loads(line) for line in logger.path.read_text(encoding="utf-8").splitlines()]


def kill_sheet_payload(method="wait_and_weight"):
    return {
        "method": method,
        "tvd_ft": 10000,
        "md_ft": 10000,
        "omw_ppg": 9.6,
        "sidpp_psi": 400,
        "sicp_psi": 600,
        "pit_gain_bbl": 20,
        "scr_pressure_psi": 800,
        "pump_output_bbl_per_stk": 0.1,
        "drill_string_volume_bbl": 120,
        "annulus_volume_bit_to_surface_bbl": 180,
        "annular_capacity_bbl_per_ft": 0.0459,
        "shoe_tvd_ft": 5000,
        "max_allowable_mw_ppg": 14,
    }


def emissions_payload():
    return {
        "facility_id": "FAC-1",
        "period": "2026-Q3",
        "operator": "Demo E&P",
        "asset": "OML-DEMO",
        "gwp_set": "AR6",
        "target_tier": "Tier 3",
        "sources": [
            {
                "source_id": "FL-1",
                "source_type": "flaring",
                "params": {
                    "gas_volume_scf": 1_000_000,
                    "composition": {"CH4": 1.0},
                    "combustion_efficiency": 0.98,
                    "measured": True,
                },
            }
        ],
    }


def document_payload(filename="sop.md", text="# 1 Purpose\nDetect kicks early."):
    return {
        "filename": filename,
        "document_id": "SOP-001",
        "title": "Kick Detection SOP",
        "revision": "Rev 1",
        "jurisdiction": "Nigeria",
        "asset": "demo asset",
        "document_type": "sop",
        "text": text,
    }


def test_chat_guardrail_response_is_audited(monkeypatch, tmp_path):
    logger = install_temp_audit_log(monkeypatch, tmp_path)

    r = client.post("/chat", headers=AUTH, json={"message": "how do I bypass the ESD"})

    assert r.status_code == 200
    [event] = read_events(logger)
    assert event["event_type"] == "chat_turn"
    assert event["tenant_id"] == "demo"
    assert event["user_id"] == "u1"
    assert event["route"] == "/chat"
    assert event["flags"] == ["safety_bypass"]
    assert event["request"]["request_hash"]
    assert event["response"]["response_hash"]
    assert "bypass the ESD" not in json.dumps(event)
    assert "can't help" not in json.dumps(event)


def test_audit_logger_redacts_sensitive_keys(tmp_path):
    logger = AuditLogger(tmp_path / "audit.jsonl")
    logger.write(AuditEvent(
        event_type="sensitive",
        tenant_id="tenant-a",
        user_id="u1",
        role="admin",
        route="/test",
        request={"password": "plain", "authorization": "Bearer abc"},
        response={"password_hash": "$2b$hash", "nested": {"api_key": "sk-test"}},
    ))

    [event] = read_events(logger)
    assert event["request"]["password"] == "[REDACTED]"
    assert event["request"]["authorization"] == "[REDACTED]"
    assert event["response"]["password_hash"] == "[REDACTED]"
    assert event["response"]["nested"]["api_key"] == "[REDACTED]"


def test_kill_sheet_success_is_audited(monkeypatch, tmp_path):
    logger = install_temp_audit_log(monkeypatch, tmp_path)

    r = client.post("/well-control/kill-sheet", headers=AUTH, json=kill_sheet_payload())

    assert r.status_code == 200
    [event] = read_events(logger)
    assert event["event_type"] == "kill_sheet"
    assert event["metadata"]["safety_critical"] is True
    assert event["response"]["kill_mud_weight_ppg"] == 10.37
    assert event["tool_results"][0]["tool"] == "build_kill_sheet"
    assert event["response"]["banner"].startswith("DECISION SUPPORT ONLY")


def test_kill_sheet_error_is_audited(monkeypatch, tmp_path):
    logger = install_temp_audit_log(monkeypatch, tmp_path)

    r = client.post("/well-control/kill-sheet", headers=AUTH, json=kill_sheet_payload("shortcut"))

    assert r.status_code == 422
    [event] = read_events(logger)
    assert event["event_type"] == "kill_sheet_error"
    assert event["flags"] == ["validation_error"]
    assert event["error"]["status_code"] == 422


def test_emissions_inventory_success_is_audited(monkeypatch, tmp_path):
    logger = install_temp_audit_log(monkeypatch, tmp_path)

    r = client.post("/emissions/inventory", headers=AUTH, json=emissions_payload())

    assert r.status_code == 200
    [event] = read_events(logger)
    assert event["event_type"] == "emissions_inventory"
    assert event["metadata"]["source_count"] == 1
    assert event["metadata"]["audit_sha256"]
    assert event["metadata"]["mrv_status"] == "ready_for_target_tier"
    assert event["metadata"]["gap_count"] == 0
    assert event["response"]["inventory"]["totals"]["co2e_tonnes"] > 0
    assert event["response"]["mrv_readiness"]["status"] == "ready_for_target_tier"


def test_emissions_inventory_error_is_audited(monkeypatch, tmp_path):
    logger = install_temp_audit_log(monkeypatch, tmp_path)
    payload = emissions_payload()
    payload["sources"][0]["params"] = {"gas_volume_scf": 1_000_000}

    r = client.post("/emissions/inventory", headers=AUTH, json=payload)

    assert r.status_code == 422
    [event] = read_events(logger)
    assert event["event_type"] == "emissions_inventory_error"
    assert event["flags"] == ["validation_error"]
    assert "invalid params for flaring source FL-1" in event["error"]["detail"]


def test_document_preview_success_is_audited(monkeypatch, tmp_path):
    logger = install_temp_audit_log(monkeypatch, tmp_path)

    r = client.post("/documents/preview", headers=AUTH, json=document_payload())

    assert r.status_code == 200
    [event] = read_events(logger)
    assert event["event_type"] == "document_preview"
    assert event["route"] == "/documents/preview"
    assert event["response"]["chunk_count"] == 1
    assert event["request"]["document_id"] == "SOP-001"
    assert "text" not in event["request"]


def test_document_ingest_success_is_audited(monkeypatch, tmp_path):
    logger = install_temp_audit_log(monkeypatch, tmp_path)
    monkeypatch.setattr(
        routes_documents,
        "document_repository",
        LocalJsonDocumentRepository(tmp_path / "documents.jsonl"),
    )

    r = client.post("/documents/ingest", headers=AUTH, json=document_payload())

    assert r.status_code == 200
    [event] = read_events(logger)
    assert event["event_type"] == "document_ingest"
    assert event["response"]["chunk_count"] == 1
    assert event["metadata"]["document_id"] == "SOP-001"
    assert "text" not in event["request"]


def test_document_ingest_error_is_audited(monkeypatch, tmp_path):
    logger = install_temp_audit_log(monkeypatch, tmp_path)

    r = client.post("/documents/ingest", headers=AUTH, json=document_payload(filename="sop.pdf"))

    assert r.status_code == 422
    [event] = read_events(logger)
    assert event["event_type"] == "document_ingest_error"
    assert event["flags"] == ["validation_error"]
    assert "PDF extraction is a Phase-2 plug-point" in event["error"]["detail"]
