"""
CSRD / ESRS E1 (Climate change) disclosure generator.

Builds the GHG-emissions backbone of an ESRS E1 disclosure from the SAME
deterministic Inventory: gross Scope 1 / 2 / 3 (datapoint E1-6), GHG intensity
(E1-6 intensity), and a pass-through of reduction targets (E1-4). Framed for an
O&G operator, where Scope 3 - dominated by the use of sold products (combustion of
sold hydrocarbons) - typically dwarfs Scope 1 + 2.

Does not recompute emissions; scope totals come from Inventory.scope_summary().
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..engine import Inventory
from ..factors import GWP_SETS, OG_SCOPE3_CATEGORIES
from ._common import audit_sha256


def build_csrd_report(
    inventory: Inventory,
    operator: str,
    asset: str,
    net_revenue: float | None = None,
    revenue_currency: str = "USD",
    production_boe: float | None = None,
    scope2_market_based_co2e_tonnes: float | None = None,
    targets: list[dict[str, Any]] | None = None,
    prepared_by: str = "PetroBrain MRV",
    **_ignored: Any,
) -> dict[str, Any]:
    gwp = GWP_SETS[inventory.gwp_set]
    scopes = inventory.scope_summary()
    total_co2e = round(scopes["scope_1"] + scopes["scope_2"] + scopes["scope_3"], 3)

    # Scope-3 breakdown by O&G category (E1-6 requires significant Scope-3 categories).
    scope3_by_category: dict[str, dict[str, Any]] = {}
    for l in inventory.lines:
        if l.scope != "scope_3":
            continue
        cat = l.activity.get("category", l.source_type.replace("scope3_", ""))
        co2e = l.co2_tonnes * gwp["CO2"] + l.ch4_tonnes * gwp["CH4"] + l.n2o_tonnes * gwp["N2O"]
        meta = OG_SCOPE3_CATEGORIES.get(cat, {})
        entry = scope3_by_category.setdefault(cat, {
            "ghg_protocol_category": meta.get("ghg_protocol_category"),
            "label": meta.get("label", cat),
            "co2e_tonnes": 0.0,
        })
        entry["co2e_tonnes"] = round(entry["co2e_tonnes"] + co2e, 3)

    intensity = _intensity(total_co2e, net_revenue, revenue_currency, production_boe)

    report: dict[str, Any] = {
        "report_type": "CSRD / ESRS E1 Climate Disclosure",
        "framework": "ESRS E1",
        "standard": "ESRS E1 Climate change",
        "operator": operator,
        "asset": asset,
        "facility_id": inventory.facility_id,
        "reporting_period": inventory.period,
        "prepared_by": prepared_by,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "gwp_basis": f"IPCC {inventory.gwp_set} GWP100",
        "gross_ghg_emissions_e1_6": {
            "scope_1_co2e_tonnes": scopes["scope_1"],
            "scope_2_location_based_co2e_tonnes": scopes["scope_2"],
            "scope_2_market_based_co2e_tonnes": scope2_market_based_co2e_tonnes,
            "scope_3_co2e_tonnes": scopes["scope_3"],
            "scope_3_by_category": scope3_by_category,
            "total_co2e_tonnes": total_co2e,
        },
        "ghg_intensity_e1_6": intensity,
        "targets_e1_4": targets or [],
        "operator_framing_notes": _framing_notes(scopes),
        "methodology_notes": [
            "Scope totals are the engine's deterministic per-scope CO2e; ESRS E1 is a "
            "re-presentation, not a recomputation.",
            "Scope 2 location-based is reported by default; supply a market-based total "
            "where the operator has contractual instruments.",
            "Confirm consolidation boundary, materiality of Scope-3 categories, and GWP "
            "set against the operator's ESRS reporting basis before disclosure.",
        ],
    }
    report["audit_sha256"] = audit_sha256({k: report[k] for k in (
        "operator", "asset", "facility_id", "reporting_period",
        "gross_ghg_emissions_e1_6", "ghg_intensity_e1_6", "gwp_basis")})
    return report


def _intensity(total_co2e: float, net_revenue: float | None, currency: str,
               production_boe: float | None) -> dict[str, Any]:
    per_revenue = None
    if net_revenue and net_revenue > 0:
        per_revenue = round(total_co2e / net_revenue, 6)
    per_boe = None
    if production_boe and production_boe > 0:
        per_boe = round(total_co2e / production_boe, 6)
    return {
        "total_co2e_tonnes": total_co2e,
        "co2e_tonnes_per_revenue_unit": per_revenue,
        "revenue_currency": currency if per_revenue is not None else None,
        "co2e_tonnes_per_boe": per_boe,
        "note": (
            None if (per_revenue is not None or per_boe is not None)
            else "No revenue or production denominator supplied; intensity not computed."
        ),
    }


def _framing_notes(scopes: dict[str, float]) -> list[str]:
    notes: list[str] = []
    s1_s2 = scopes["scope_1"] + scopes["scope_2"]
    if scopes["scope_3"] > 0:
        notes.append(
            "Scope 3 is reported. For an O&G operator the use of sold products "
            "(combustion of sold hydrocarbons) is typically the dominant category."
        )
        if scopes["scope_3"] > s1_s2:
            notes.append(
                "Scope 3 exceeds Scope 1 + 2 combined - prioritise its data quality "
                "and stated estimation basis in the disclosure."
            )
    else:
        notes.append(
            "No Scope 3 reported. For an O&G operator this is usually material "
            "(use of sold products); confirm whether it is excluded by boundary."
        )
    return notes
