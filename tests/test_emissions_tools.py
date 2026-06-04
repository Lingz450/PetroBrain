"""Emissions MRV deterministic tool wrapper tests."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.llm_service import LLMResponse
from app.core.orchestrator import MODULE_TOOLS, Orchestrator, TOOL_REGISTRY
from app.modules.emissions_mrv.agent import (
    BUILD_GHGEMP_REPORT_TOOL,
    BUILD_REPORT_TOOL,
    COMBUSTION_TOOL,
    FLARING_TOOL,
    FUGITIVE_TIER2_TOOL,
    FUGITIVE_TIER3_TOOL,
    MODEL_ABATEMENT_TOOL,
    RECONCILE_FLARING_TOOL,
    VENTING_TOOL,
    run_build_ghgemp_report_tool,
    run_build_report_tool,
    run_combustion_tool,
    run_flaring_tool,
    run_fugitive_tier2_tool,
    run_fugitive_tier3_tool,
    run_model_abatement_tool,
    run_reconcile_flaring_tool,
    run_venting_tool,
)


class SequenceLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, system_prompt, messages, tools=None, **kwargs):
        self.calls.append({"system": system_prompt, "messages": messages, "tools": tools})
        if not self.responses:
            raise AssertionError("unexpected extra LLM call")
        return self.responses.pop(0)


def test_emissions_line_tool_entrypoints_return_auditable_lines():
    flaring = run_flaring_tool({
        "source_id": "FL-1",
        "gas_volume_scf": 1_000_000,
        "composition": {"CH4": 1.0},
        "combustion_efficiency": 0.98,
        "measured": True,
    })
    venting = run_venting_tool({
        "source_id": "V-1",
        "gas_volume_scf": 100_000,
        "composition": {"CH4": 0.92, "CO2": 0.04, "N2": 0.04},
        "measured": True,
    })
    fugitive_t2 = run_fugitive_tier2_tool({
        "source_id": "AREA-1",
        "component_counts": {"valve": 100, "flange": 200},
        "operating_hours": 8760,
    })
    fugitive_t3 = run_fugitive_tier3_tool({
        "source_id": "AREA-2",
        "measured_leaks_kg_ch4_per_hr": [0.5, 0.3, 0.2],
        "operating_hours": 8760,
    })
    combustion = run_combustion_tool({
        "source_id": "GT-1",
        "fuel_scf": 500_000,
        "co2_kg_per_scf": 0.0545,
        "ch4_kg_per_scf": 0.000001,
        "n2o_kg_per_scf": 0.0000001,
    })

    assert flaring["source_id"] == "FL-1"
    assert flaring["tier"] == "Tier 3"
    assert flaring["co2_tonnes"] > 0
    assert venting["source_type"] == "venting"
    assert venting["ch4_tonnes"] > 0
    assert fugitive_t2["tier"] == "Tier 2"
    assert fugitive_t3["tier"] == "Tier 3"
    assert combustion["source_type"] == "combustion"
    for line in (flaring, venting, fugitive_t2, fugitive_t3, combustion):
        assert line["method"]
        assert "activity" in line


def test_build_ghgemp_report_tool_uses_precomputed_line_items():
    line = run_flaring_tool({
        "source_id": "FL-1",
        "gas_volume_scf": 1_000_000,
        "composition": {"CH4": 1.0},
        "combustion_efficiency": 0.98,
        "measured": True,
    })

    result = run_build_ghgemp_report_tool({
        "facility_id": "FAC-1",
        "period": "2026-Q3",
        "operator": "Demo E&P",
        "asset": "OML-DEMO",
        "gwp_set": "AR6",
        "target_tier": "Tier 3",
        "lines": [line],
    })

    assert result["inventory"]["facility_id"] == "FAC-1"
    assert result["inventory"]["totals"]["co2e_tonnes"] > 0
    assert result["ghgemp_report"]["audit_sha256"]
    assert result["mrv_readiness"]["status"] == "ready_for_target_tier"
    assert "LLM must not recompute" in result["notes"][0]


def test_emissions_tools_registered_for_module():
    expected = {
        "flaring_emissions",
        "venting_emissions",
        "fugitive_tier2",
        "fugitive_tier3",
        "combustion_emissions",
        "build_ghgemp_report",
        "build_report",
        "reconcile_flaring",
        "model_abatement",
        "web_search",
    }

    assert set(MODULE_TOOLS["emissions_mrv"]) == expected
    assert TOOL_REGISTRY["flaring_emissions"][0] is FLARING_TOOL
    assert TOOL_REGISTRY["venting_emissions"][0] is VENTING_TOOL
    assert TOOL_REGISTRY["fugitive_tier2"][0] is FUGITIVE_TIER2_TOOL
    assert TOOL_REGISTRY["fugitive_tier3"][0] is FUGITIVE_TIER3_TOOL
    assert TOOL_REGISTRY["combustion_emissions"][0] is COMBUSTION_TOOL
    assert TOOL_REGISTRY["build_ghgemp_report"][0] is BUILD_GHGEMP_REPORT_TOOL
    assert TOOL_REGISTRY["build_report"][0] is BUILD_REPORT_TOOL
    assert TOOL_REGISTRY["reconcile_flaring"][0] is RECONCILE_FLARING_TOOL
    assert TOOL_REGISTRY["model_abatement"][0] is MODEL_ABATEMENT_TOOL


def _sample_flaring_line():
    return run_flaring_tool({
        "source_id": "FL-1",
        "gas_volume_scf": 1_000_000,
        "composition": {"CH4": 1.0},
        "combustion_efficiency": 0.98,
        "measured": True,
    })


def test_build_report_tool_dispatches_frameworks():
    line = _sample_flaring_line()
    base = {
        "facility_id": "FAC-1", "period": "2026-Q3",
        "operator": "Demo E&P", "asset": "OML-DEMO", "lines": [line],
    }
    ghgemp = run_build_report_tool({**base, "framework": "ghgemp"})
    assert ghgemp["framework"] == "ghgemp"
    assert ghgemp["report"]["audit_sha256"]
    assert "LLM must not recompute" in ghgemp["notes"][0]

    ogmp = run_build_report_tool({
        **base, "framework": "ogmp2",
        "meta": {"gas_throughput_tonnes": 1000, "source_throughput_tonnes": {"FL-1": 1000}},
    })
    assert ogmp["report"]["framework"] == "OGMP 2.0"
    assert ogmp["report"]["target_methane_intensity_pct"] == 0.2

    iso = run_build_report_tool({**base, "framework": "iso14064"})
    assert iso["report"]["framework"] == "ISO 14064-1:2018"


def test_reconcile_flaring_tool_with_observations_flags_excess():
    line = _sample_flaring_line()
    result = run_reconcile_flaring_tool({
        "reported_line": line,
        "satellite_observations": [
            {"detection_date": "2026-08-05", "flared_volume_scf": 1_500_000},
            {"detection_date": "2026-08-20", "flared_volume_scf": 1_000_000},
        ],
    })
    rec = result["reconciliation"]
    assert rec["reconciliation_available"] is True
    assert rec["observed_exceeds_reported"] is True
    assert rec["observed_flared_scf"] == 2_500_000


def test_reconcile_flaring_tool_asks_for_coordinates():
    line = _sample_flaring_line()
    # No observations and no resolvable coordinates -> honest request for coords.
    result = run_reconcile_flaring_tool({"reported_line": line})
    assert result["coordinates_required"] is True

    # Coords present but no date range -> asks for the date range.
    result2 = run_reconcile_flaring_tool({
        "reported_line": line,
        "asset_attributes": {"lat": 5.0, "lon": 6.0},
    })
    assert result2["date_range_required"] is True


def test_reconcile_flaring_tool_unconfigured_provider_is_honest():
    line = _sample_flaring_line()
    # Coords + date range, but no satellite endpoint configured -> unavailable, honest.
    result = run_reconcile_flaring_tool({
        "reported_line": line,
        "location": {"lat": 5.0, "lon": 6.0},
        "date_range": {"start": "2026-08-01", "end": "2026-08-31"},
    })
    rec = result["reconciliation"]
    assert rec["reconciliation_available"] is False
    assert rec["variance_pct"] is None


def test_model_abatement_tool_returns_mac_curve_and_disclaimer():
    venting_line = run_venting_tool({
        "source_id": "V-1", "gas_volume_scf": 10_000_000, "composition": {"CH4": 1.0},
    })
    result = run_model_abatement_tool({
        "facility_id": "FAC-1", "period": "2026", "gwp_set": "AR6",
        "lines": [venting_line],
        "selected_measures": [{
            "measure_id": "vapor_recovery_unit", "target_source_ids": ["V-1"],
            "reduction_pct": 0.95, "capex_usd": 10_000, "opex_usd_per_yr": 1_000,
            "gas_price_usd_per_mcf": 5.0,
        }],
    })
    ab = result["abatement"]
    assert ab["total_co2e_avoided_tonnes"] > 0
    assert ab["measures"][0]["net_negative_cost"] is True
    assert ab["mac_curve"][0]["measure_id"] == "vapor_recovery_unit"
    assert any("ESTIMATE" in n for n in result["notes"])


def test_orchestrator_dispatches_emissions_tool_without_llm_arithmetic():
    first = LLMResponse(
        text="",
        tool_calls=[{
            "name": "flaring_emissions",
            "id": "tool-1",
            "input": {
                "source_id": "FL-1",
                "gas_volume_scf": 1_000_000,
                "composition": {"CH4": 1.0},
                "combustion_efficiency": 0.98,
                "measured": True,
            },
        }],
        usage={"input": 10, "output": 5},
        model="fake-model",
    )
    final = LLMResponse(
        text="Use the tool result and verify factors/GWP against current NUPRC guidance.",
        tool_calls=[],
        usage={"input": 12, "output": 6},
        model="fake-model",
    )
    llm = SequenceLLM([first, final])
    orch = Orchestrator(llm=llm)

    turn = asyncio.run(orch.handle("Estimate flare emissions", module="emissions_mrv", tenant_id="tenant-a"))

    assert llm.calls[0]["tools"]
    assert {tool["name"] for tool in llm.calls[0]["tools"]} == set(MODULE_TOOLS["emissions_mrv"])
    assert turn.tool_results[0]["tool"] == "flaring_emissions"
    assert turn.tool_results[0]["result"]["co2_tonnes"] > 0
    assert turn.flags == []
