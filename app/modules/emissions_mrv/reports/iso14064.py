"""
ISO 14064-1:2018 GHG inventory generator.

Re-presents the SAME deterministic Inventory in the ISO 14064-1:2018 category
structure:

  Category 1 - Direct GHG emissions and removals            (= Scope 1)
  Category 2 - Indirect from imported energy                (= Scope 2)
  Category 3 - Indirect from transportation
  Category 4 - Indirect from products used by the org
  Category 5 - Indirect associated with use of products
  Category 6 - Indirect from other sources

Does not recompute emissions; CO2e per line uses the inventory's GWP set.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..engine import Inventory
from ..factors import GWP_SETS
from ._common import audit_sha256

ISO_CATEGORY_TITLES = {
    1: "Direct GHG emissions and removals",
    2: "Indirect GHG emissions from imported energy",
    3: "Indirect GHG emissions from transportation",
    4: "Indirect GHG emissions from products used by the organization",
    5: "Indirect GHG emissions associated with the use of products from the organization",
    6: "Indirect GHG emissions from other sources",
}

# ISO 14064-1 category for each O&G Scope-3 category.
ISO_CATEGORY_FOR_SCOPE3 = {
    "upstream_transport": 3,
    "downstream_transport": 3,
    "business_travel": 3,
    "purchased_goods_services": 4,
    "capital_goods": 4,
    "fuel_and_energy_related": 4,
    "waste": 4,
    "use_of_sold_products": 5,
    "processing_of_sold_products": 5,
}


def _iso_category(scope: str, scope3_category: str | None) -> int:
    if scope == "scope_1":
        return 1
    if scope == "scope_2":
        return 2
    return ISO_CATEGORY_FOR_SCOPE3.get(scope3_category or "", 6)


def build_iso14064_report(
    inventory: Inventory,
    operator: str,
    asset: str,
    prepared_by: str = "PetroBrain MRV",
    **_ignored: Any,
) -> dict[str, Any]:
    gwp = GWP_SETS[inventory.gwp_set]
    categories: dict[int, dict[str, Any]] = {}

    for l in inventory.lines:
        cat3 = l.activity.get("category") if l.scope == "scope_3" else None
        cat_num = _iso_category(l.scope, cat3)
        co2e = l.co2_tonnes * gwp["CO2"] + l.ch4_tonnes * gwp["CH4"] + l.n2o_tonnes * gwp["N2O"]
        bucket = categories.setdefault(cat_num, {
            "iso_category": cat_num,
            "title": ISO_CATEGORY_TITLES[cat_num],
            "co2e_tonnes": 0.0,
            "ch4_tonnes": 0.0,
            "co2_tonnes": 0.0,
            "n2o_tonnes": 0.0,
            "sources": [],
        })
        bucket["co2e_tonnes"] = round(bucket["co2e_tonnes"] + co2e, 4)
        bucket["ch4_tonnes"] = round(bucket["ch4_tonnes"] + l.ch4_tonnes, 4)
        bucket["co2_tonnes"] = round(bucket["co2_tonnes"] + l.co2_tonnes, 4)
        bucket["n2o_tonnes"] = round(bucket["n2o_tonnes"] + l.n2o_tonnes, 4)
        bucket["sources"].append({
            "source_id": l.source_id,
            "source_type": l.source_type,
            "scope": l.scope,
            "co2e_tonnes": round(co2e, 4),
        })

    totals = inventory.totals()
    categories_list = [categories[k] for k in sorted(categories)]

    report: dict[str, Any] = {
        "report_type": "ISO 14064-1 GHG Inventory",
        "framework": "ISO 14064-1:2018",
        "operator": operator,
        "asset": asset,
        "facility_id": inventory.facility_id,
        "reporting_period": inventory.period,
        "prepared_by": prepared_by,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "gwp_basis": f"IPCC {inventory.gwp_set} GWP100",
        "categories": categories_list,
        "totals": {
            "total_co2e_tonnes": totals["co2e_tonnes"],
            "total_ch4_tonnes": totals["ch4_tonnes"],
            "total_co2_tonnes": totals["co2_tonnes"],
            "total_n2o_tonnes": totals["n2o_tonnes"],
        },
        "methodology_notes": [
            "Sources are classified into ISO 14064-1:2018 categories 1-6; CO2e uses the "
            "stated IPCC GWP100 set. This is a re-presentation, not a recomputation.",
            "Confirm the organizational/operational consolidation boundary and the "
            "significance assessment of indirect categories before reporting.",
        ],
    }
    report["audit_sha256"] = audit_sha256({k: report[k] for k in (
        "operator", "asset", "facility_id", "reporting_period",
        "categories", "totals", "gwp_basis")})
    return report
