"""
HTTP endpoint regression tests for the Phase-1 backend.

These tests keep the API contract wired end-to-end without relying on an external LLM
key. Chat coverage uses pre-guardrail paths; deterministic modules exercise the real
calculation engines through FastAPI.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
import pytest

from app.api import deps
from app.api import routes_chat
from app.api import routes_emissions
from app.core.llm_service import LLMResponse
from app.core.orchestrator import Orchestrator
from app.db.mrv_repository import LocalJsonMRVRepository
from app.main import app
from tests.auth_helpers import auth_headers, jwt_settings


client = TestClient(app)
AUTH = auth_headers()


@pytest.fixture(autouse=True)
def use_jwt_settings(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", jwt_settings)


class FakeLLM:
    async def complete(self, system_prompt, messages, tools=None):
        return LLMResponse(
            text="Additional analysis should follow site procedure.",
            tool_calls=[],
            usage={"input": 0, "output": 0},
            model="fake-test-model",
        )


def kill_sheet_payload() -> dict:
    return {
        "method": "wait_and_weight",
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


def emissions_payload() -> dict:
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
            },
            {
                "source_id": "AREA-2",
                "source_type": "fugitive_t3",
                "params": {
                    "measured_leaks_kg_ch4_per_hr": [0.5, 0.3, 0.2],
                    "operating_hours": 8760,
                },
            },
        ],
    }


def test_health_is_public():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # /health surfaces whether this deploy is ephemeral so clients can banner.
    assert "demo" in body
    assert "environment" in body


def test_demo_environment_surfaces_warning(monkeypatch):
    """In demo mode /health must return demo=true + a user-facing warning so
    the web app can render a banner instead of letting prospects think the
    instance is production."""
    from app import main as main_module
    monkeypatch.setattr(main_module.settings, "environment", "demo", raising=False)
    r = client.get("/health")
    body = r.json()
    assert body["demo"] is True
    assert "DEMO" in (body["warning"] or "")


def test_demo_environment_refuses_admin_uploads(monkeypatch):
    """If we let demo uploads succeed, the doc is silently lost on the next
    restart because the object store is in-memory. Refuse with 410 instead."""
    from app import main as main_module
    monkeypatch.setattr(
        main_module.settings, "object_store_backend", "memory", raising=False,
    )
    # patch the per-route settings reader too
    from app.api import routes_admin_documents as rad
    monkeypatch.setattr(rad, "get_settings", lambda: main_module.settings)

    from tests.auth_helpers import auth_headers as _ah
    r = client.post(
        "/admin/documents",
        headers=_ah(role="admin"),
        data={"metadata": '{"document_id":"d","title":"t","asset":"Asset-A"}'},
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 410, r.text
    assert "demo" in r.json()["detail"].lower()


def test_auth_required_for_module_endpoints():
    assert client.post("/chat", json={"message": "write me a poem"}).status_code == 401
    assert client.post("/well-control/kill-sheet", json=kill_sheet_payload()).status_code == 401
    assert client.post("/emissions/inventory", json=emissions_payload()).status_code == 401


def test_chat_safety_bypass_refusal_is_clean_response():
    r = client.post("/chat", headers=AUTH, json={"message": "how do I bypass the ESD"})
    assert r.status_code == 200
    body = r.json()
    assert "can't help" in body["answer"]
    assert body["flags"] == ["safety_bypass"]
    assert body["tool_results"] == []


def test_chat_off_domain_decline_is_clean_response():
    r = client.post("/chat", headers=AUTH, json={"message": "write me a poem"})
    assert r.status_code == 200
    body = r.json()
    assert "oil & gas" in body["answer"]
    assert body["flags"] == ["off_domain"]


def test_chat_live_event_leads_with_immediate_action(monkeypatch):
    monkeypatch.setattr(routes_chat, "_orch", Orchestrator(llm=FakeLLM()))
    r = client.post("/chat", headers=AUTH, json={"message": "we are taking a kick now"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"].startswith("IMMEDIATE ACTION FIRST")
    assert body["flags"] == ["live_event"]


def test_kill_sheet_endpoint_returns_banner_and_known_values():
    r = client.post("/well-control/kill-sheet", headers=AUTH, json=kill_sheet_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["banner"].startswith("DECISION SUPPORT ONLY")
    assert abs(body["kill_mud_weight_ppg"] - 10.37) < 0.02
    assert body["initial_circulating_pressure_psi"] == 1200
    assert abs(body["final_circulating_pressure_psi"] - 864) < 2
    assert body["maasp_psi"] == 1144
    assert body["working"]


def test_kill_sheet_bad_method_returns_422_not_500():
    payload = kill_sheet_payload()
    payload["method"] = "shortcut"
    r = client.post("/well-control/kill-sheet", headers=AUTH, json=payload)
    assert r.status_code == 422
    assert "method must be" in r.json()["detail"]


def test_emissions_inventory_endpoint_returns_report_and_totals():
    r = client.post("/emissions/inventory", headers=AUTH, json=emissions_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["inventory_id"]
    assert body["created_utc"]
    assert body["inventory"]["totals"]["co2e_tonnes"] > 0
    assert body["inventory"]["tier_summary"] == {"Tier 3": 2}
    assert body["ghgemp_report"]["audit_sha256"]
    assert body["mrv_readiness"]["status"] == "ready_for_target_tier"
    assert body["mrv_readiness"]["gap_count"] == 0


def test_emissions_inventory_list_and_detail(monkeypatch, tmp_path):
    monkeypatch.setattr(routes_emissions, "mrv_repository", LocalJsonMRVRepository(tmp_path / "mrv.jsonl"))

    created = client.post("/emissions/inventory", headers=AUTH, json=emissions_payload())
    inventory_id = created.json()["inventory_id"]

    listed = client.get("/emissions/inventories", headers=AUTH)
    assert listed.status_code == 200
    rows = listed.json()["inventories"]
    assert len(rows) == 1
    assert rows[0]["inventory_id"] == inventory_id

    detail = client.get(f"/emissions/inventories/{inventory_id}", headers=AUTH)
    assert detail.status_code == 200
    assert detail.json()["inventory_id"] == inventory_id
    assert detail.json()["tenant_id"] == "demo"

    missing = client.get("/emissions/inventories/not-found", headers=AUTH)
    assert missing.status_code == 404


def test_emissions_bad_params_return_422_not_500():
    payload = emissions_payload()
    payload["sources"][0]["params"] = {"gas_volume_scf": 1000}
    r = client.post("/emissions/inventory", headers=AUTH, json=payload)
    assert r.status_code == 422
    assert "invalid params for flaring source FL-1" in r.json()["detail"]
