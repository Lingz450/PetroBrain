"""Emissions MRV specialist tool wrappers for the orchestrator."""
from __future__ import annotations

from typing import Any

from app.data_providers import (
    DateRange,
    ObservationRequest,
    SatelliteFlaringProvider,
    asset_coordinates,
    bounding_box_for_point,
)

from .abatement import COST_ESTIMATE_DISCLAIMER, abatement_catalog, model_abatement
from .engine import (
    EmissionLine,
    build_inventory,
    combustion,
    flaring,
    fugitive_tier2,
    fugitive_tier3,
    reconcile_flaring,
    venting,
)
from .reports import SUPPORTED_FRAMEWORKS, build_ghgemp_report, build_mrv_readiness_summary, build_report

MODULE_TOOL_NOTE = (
    "Emission quantities are deterministic tool outputs from app/modules/emissions_mrv; "
    "the LLM must not recompute them in prose."
)

FLARING_TOOL = {
    "name": "flaring_emissions",
    "description": (
        "Calculate flaring emissions by carbon balance from gas volume, composition, "
        "and combustion efficiency. Returns a source-level MRV line item."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source_id": {"type": "string"},
            "gas_volume_scf": {"type": "number"},
            "composition": {"type": "object", "additionalProperties": {"type": "number"}},
            "combustion_efficiency": {"type": "number"},
            "measured": {"type": "boolean"},
        },
        "required": ["source_id", "gas_volume_scf", "composition"],
    },
}

VENTING_TOOL = {
    "name": "venting_emissions",
    "description": (
        "Calculate direct venting emissions from gas volume and composition. Returns "
        "a source-level MRV line item."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source_id": {"type": "string"},
            "gas_volume_scf": {"type": "number"},
            "composition": {"type": "object", "additionalProperties": {"type": "number"}},
            "measured": {"type": "boolean"},
        },
        "required": ["source_id", "gas_volume_scf", "composition"],
    },
}

FUGITIVE_TIER2_TOOL = {
    "name": "fugitive_tier2",
    "description": (
        "Calculate fugitive methane emissions using Tier 2 component counts and "
        "operating hours. Returns a source-level MRV line item."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source_id": {"type": "string"},
            "component_counts": {"type": "object", "additionalProperties": {"type": "integer"}},
            "operating_hours": {"type": "number"},
        },
        "required": ["source_id", "component_counts", "operating_hours"],
    },
}

FUGITIVE_TIER3_TOOL = {
    "name": "fugitive_tier3",
    "description": (
        "Calculate measurement-based fugitive methane emissions from quantified leak "
        "rates and operating hours. Returns a source-level MRV line item."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source_id": {"type": "string"},
            "measured_leaks_kg_ch4_per_hr": {
                "type": "array",
                "items": {"type": "number"},
            },
            "operating_hours": {"type": "number"},
        },
        "required": ["source_id", "measured_leaks_kg_ch4_per_hr", "operating_hours"],
    },
}

COMBUSTION_TOOL = {
    "name": "combustion_emissions",
    "description": (
        "Calculate stationary combustion emissions from fuel volume and emission "
        "factors. Returns a source-level MRV line item."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source_id": {"type": "string"},
            "fuel_scf": {"type": "number"},
            "co2_kg_per_scf": {"type": "number"},
            "ch4_kg_per_scf": {"type": "number"},
            "n2o_kg_per_scf": {"type": "number"},
            "measured": {"type": "boolean"},
        },
        "required": ["source_id", "fuel_scf", "co2_kg_per_scf"],
    },
}

BUILD_GHGEMP_REPORT_TOOL = {
    "name": "build_ghgemp_report",
    "description": (
        "Build an audit-ready GHGEMP/MRV report from deterministic source-level "
        "emission line items. Does not compute source emissions itself."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "facility_id": {"type": "string"},
            "period": {"type": "string"},
            "operator": {"type": "string"},
            "asset": {"type": "string"},
            "gwp_set": {"type": "string", "default": "AR6"},
            "target_tier": {"type": "string", "default": "Tier 3"},
            "jurisdiction": {"type": "string", "default": "Nigeria (NUPRC)"},
            "prepared_by": {"type": "string", "default": "PetroBrain MRV"},
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string"},
                        "source_type": {"type": "string"},
                        "tier": {"type": "string"},
                        "method": {"type": "string"},
                        "ch4_tonnes": {"type": "number"},
                        "co2_tonnes": {"type": "number"},
                        "n2o_tonnes": {"type": "number"},
                        "activity": {"type": "object"},
                    },
                    "required": ["source_id", "source_type", "tier", "method"],
                },
            },
        },
        "required": ["facility_id", "period", "operator", "asset", "lines"],
    },
}


# Shared schema for a precomputed source-level emission line item (engine output).
_LINE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "source_id": {"type": "string"},
        "source_type": {"type": "string"},
        "tier": {"type": "string"},
        "method": {"type": "string"},
        "scope": {"type": "string", "description": "scope_1 | scope_2 | scope_3 (default scope_1)"},
        "ch4_tonnes": {"type": "number"},
        "co2_tonnes": {"type": "number"},
        "n2o_tonnes": {"type": "number"},
        "activity": {"type": "object"},
    },
    "required": ["source_id", "source_type", "tier", "method"],
}

BUILD_REPORT_TOOL = {
    "name": "build_report",
    "description": (
        "Generate an MRV report in a chosen framework from precomputed source-level "
        "emission line items. Supported frameworks: 'ghgemp' (NUPRC GHGEMP), 'ogmp2' "
        "(OGMP 2.0 methane), 'csrd' (CSRD/ESRS E1), 'iso14064' (ISO 14064-1). The same "
        "inventory exports to every framework; this does not compute source emissions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "framework": {"type": "string", "enum": list(SUPPORTED_FRAMEWORKS)},
            "facility_id": {"type": "string"},
            "period": {"type": "string"},
            "operator": {"type": "string"},
            "asset": {"type": "string"},
            "gwp_set": {"type": "string", "default": "AR6"},
            "lines": {"type": "array", "items": _LINE_ITEM_SCHEMA},
            "meta": {
                "type": "object",
                "description": (
                    "Framework-specific options. GHGEMP: target_tier, jurisdiction, "
                    "prepared_by. OGMP2: gas_throughput_tonnes, source_throughput_tonnes. "
                    "CSRD: net_revenue, revenue_currency, production_boe, "
                    "scope2_market_based_co2e_tonnes, targets."
                ),
                "additionalProperties": True,
            },
        },
        "required": ["framework", "facility_id", "period", "operator", "asset", "lines"],
    },
}

RECONCILE_FLARING_TOOL = {
    "name": "reconcile_flaring",
    "description": (
        "Cross-reference a REPORTED flaring source against independent satellite "
        "observation (VIIRS/NOAA). Returns reported vs observed flared volume, a "
        "variance %, and a flag if observed materially exceeds reported. Supply "
        "satellite_observations directly, or a facility location (lat/lon) or "
        "asset_attributes plus a date_range to fetch them. If satellite data is "
        "unavailable, the result says so - never infer a number. If no coordinates "
        "are available it asks for them."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reported_line": {
                "type": "object",
                "description": "A flaring emission line item (source_type='flaring', "
                               "with activity.gas_volume_scf).",
                "properties": {
                    "source_id": {"type": "string"},
                    "source_type": {"type": "string"},
                    "activity": {"type": "object"},
                },
                "required": ["source_id"],
            },
            "satellite_observations": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional pre-fetched VIIRS detections, each with "
                               "flared_volume_scf.",
            },
            "location": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "radius_km": {"type": "number", "default": 10.0},
                },
            },
            "asset_attributes": {
                "type": "object",
                "description": "A9 asset attributes; lat/lon read from here if location absent.",
            },
            "date_range": {
                "type": "object",
                "properties": {"start": {"type": "string"}, "end": {"type": "string"}},
            },
            "material_threshold_pct": {"type": "number", "default": 20.0},
        },
        "required": ["reported_line"],
    },
}

MODEL_ABATEMENT_TOOL = {
    "name": "model_abatement",
    "description": (
        "Model abatement/decarbonization measures against the operator's own source "
        "inventory. Returns the projected post-abatement inventory, CO2e avoided, and a "
        "marginal-abatement-cost ($/tCO2e) per measure sorted into a MAC curve, flagging "
        "net-negative-cost measures. ALL cost figures are reference ESTIMATES the "
        "operator must validate. Measure ids: " + ", ".join(m["measure_id"] for m in abatement_catalog()) + "."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "facility_id": {"type": "string"},
            "period": {"type": "string"},
            "gwp_set": {"type": "string", "default": "AR6"},
            "lines": {"type": "array", "items": _LINE_ITEM_SCHEMA},
            "selected_measures": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "measure_id": {"type": "string"},
                        "target_source_ids": {"type": "array", "items": {"type": "string"}},
                        "reduction_pct": {"type": "number", "description": "fraction 0-1"},
                        "capex_usd": {"type": "number"},
                        "opex_usd_per_yr": {"type": "number"},
                        "gas_price_usd_per_mcf": {"type": "number"},
                        "discount_rate": {"type": "number"},
                        "lifetime_years": {"type": "integer"},
                    },
                    "required": ["measure_id"],
                },
            },
            "default_gas_price_usd_per_mcf": {"type": "number"},
        },
        "required": ["facility_id", "period", "lines", "selected_measures"],
    },
}


def run_flaring_tool(args: dict[str, Any]) -> dict[str, Any]:
    return flaring(
        source_id=args["source_id"],
        gas_volume_scf=args["gas_volume_scf"],
        composition=args["composition"],
        combustion_efficiency=args.get("combustion_efficiency"),
        measured=args.get("measured", False),
    ).as_dict()


def run_venting_tool(args: dict[str, Any]) -> dict[str, Any]:
    return venting(
        source_id=args["source_id"],
        gas_volume_scf=args["gas_volume_scf"],
        composition=args["composition"],
        measured=args.get("measured", False),
    ).as_dict()


def run_fugitive_tier2_tool(args: dict[str, Any]) -> dict[str, Any]:
    return fugitive_tier2(
        source_id=args["source_id"],
        component_counts=args["component_counts"],
        operating_hours=args["operating_hours"],
    ).as_dict()


def run_fugitive_tier3_tool(args: dict[str, Any]) -> dict[str, Any]:
    return fugitive_tier3(
        source_id=args["source_id"],
        measured_leaks_kg_ch4_per_hr=args["measured_leaks_kg_ch4_per_hr"],
        operating_hours=args["operating_hours"],
    ).as_dict()


def run_combustion_tool(args: dict[str, Any]) -> dict[str, Any]:
    return combustion(
        source_id=args["source_id"],
        fuel_scf=args["fuel_scf"],
        co2_kg_per_scf=args["co2_kg_per_scf"],
        ch4_kg_per_scf=args.get("ch4_kg_per_scf", 0.0),
        n2o_kg_per_scf=args.get("n2o_kg_per_scf", 0.0),
        measured=args.get("measured", False),
    ).as_dict()


def run_build_ghgemp_report_tool(args: dict[str, Any]) -> dict[str, Any]:
    lines = [_line_from_dict(row) for row in args["lines"]]
    inventory = build_inventory(
        args["facility_id"],
        args["period"],
        lines,
        gwp_set=args.get("gwp_set", "AR6"),
    )
    report = build_ghgemp_report(
        inventory,
        operator=args["operator"],
        asset=args["asset"],
        jurisdiction=args.get("jurisdiction", "Nigeria (NUPRC)"),
        prepared_by=args.get("prepared_by", "PetroBrain MRV"),
        target_tier=args.get("target_tier", "Tier 3"),
    )
    return {
        "inventory": inventory.as_dict(),
        "ghgemp_report": report,
        "mrv_readiness": build_mrv_readiness_summary(report),
        "notes": [MODULE_TOOL_NOTE],
    }


def run_build_report_tool(args: dict[str, Any]) -> dict[str, Any]:
    lines = [_line_from_dict(row) for row in args["lines"]]
    inventory = build_inventory(
        args["facility_id"], args["period"], lines, gwp_set=args.get("gwp_set", "AR6"),
    )
    meta = dict(args.get("meta") or {})
    report = build_report(
        args["framework"], inventory,
        operator=args["operator"], asset=args["asset"], **meta,
    )
    return {
        "framework": args["framework"],
        "inventory": inventory.as_dict(),
        "report": report,
        "notes": [MODULE_TOOL_NOTE],
    }


def _resolve_satellite_observations(args: dict[str, Any]) -> Any:
    """Return observations to reconcile against, or a dict signalling what input is
    still required (coordinates / date range). Fetches via the provider when only a
    location + date range are given."""
    observations = args.get("satellite_observations")
    if observations is not None:
        return observations

    loc = args.get("location") or {}
    lat, lon = loc.get("lat"), loc.get("lon")
    if (lat is None or lon is None) and args.get("asset_attributes"):
        coords = asset_coordinates(args["asset_attributes"])
        if coords:
            lat, lon = coords
    if lat is None or lon is None:
        return {
            "coordinates_required": True,
            "message": (
                "No facility coordinates available. Provide location.lat/lon (or "
                "asset_attributes with coordinates) and a date_range to fetch "
                "satellite flaring observations."
            ),
            "notes": [MODULE_TOOL_NOTE],
        }
    date_range = args.get("date_range") or {}
    start, end = date_range.get("start"), date_range.get("end")
    if not start or not end:
        return {
            "date_range_required": True,
            "message": "Provide date_range.start and date_range.end for the satellite query.",
            "notes": [MODULE_TOOL_NOTE],
        }
    provider = SatelliteFlaringProvider()
    return provider.fetch(ObservationRequest(
        bbox=bounding_box_for_point(lat, lon, loc.get("radius_km", 10.0)),
        date_range=DateRange(start, end),
    )).as_dict()


def run_reconcile_flaring_tool(args: dict[str, Any]) -> dict[str, Any]:
    threshold = args.get("material_threshold_pct", 20.0)
    observations = _resolve_satellite_observations(args)
    # Missing-input signals are returned to the caller as-is (it asks the operator).
    if isinstance(observations, dict) and (
        observations.get("coordinates_required") or observations.get("date_range_required")
    ):
        return observations

    reconciliation = reconcile_flaring(
        args["reported_line"], observations, material_threshold_pct=threshold
    )
    return {
        "reconciliation": reconciliation,
        "notes": [
            MODULE_TOOL_NOTE,
            "Satellite observation is independent of the operator's report; where it is "
            "unavailable the result states so rather than inferring a value.",
        ],
    }


def run_model_abatement_tool(args: dict[str, Any]) -> dict[str, Any]:
    lines = [_line_from_dict(row) for row in args["lines"]]
    inventory = build_inventory(
        args["facility_id"], args["period"], lines, gwp_set=args.get("gwp_set", "AR6"),
    )
    kwargs: dict[str, Any] = {}
    if args.get("default_gas_price_usd_per_mcf") is not None:
        kwargs["default_gas_price_usd_per_mcf"] = args["default_gas_price_usd_per_mcf"]
    result = model_abatement(inventory, args["selected_measures"], **kwargs)
    return {
        "abatement": result,
        "notes": [
            MODULE_TOOL_NOTE,
            COST_ESTIMATE_DISCLAIMER,
        ],
    }


def _line_from_dict(row: dict[str, Any]) -> EmissionLine:
    return EmissionLine(
        source_id=row["source_id"],
        source_type=row["source_type"],
        tier=row["tier"],
        method=row["method"],
        scope=row.get("scope", "scope_1"),
        ch4_tonnes=float(row.get("ch4_tonnes", 0.0)),
        co2_tonnes=float(row.get("co2_tonnes", 0.0)),
        n2o_tonnes=float(row.get("n2o_tonnes", 0.0)),
        activity=dict(row.get("activity") or {}),
    )
