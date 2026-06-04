"""
OGMP 2.0 (Oil & Gas Methane Partnership 2.0, UNEP/IMEO) report generator.

OGMP 2.0 is methane-specific. Reporting is done at source level and site level,
against a five-level reporting framework (Level 1 = generic single factor, up to
Level 5 = site-level measurement reconciled with the source-level inventory), and
against the ~0.2% methane-intensity near-zero ambition.

This generator re-presents the SAME deterministic Inventory; it never recomputes
emissions. Methane intensity is defined here as:

    intensity_pct = 100 * CH4 emitted (tonnes) / gas throughput (tonnes)

with throughput supplied by the caller (site total and/or per source). When a
throughput is not supplied the intensity is reported as None with an honest
"throughput_not_provided" flag - we never invent a denominator to look complete.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..engine import Inventory
from ..factors import GWP_SETS
from ._common import audit_sha256

# OGMP 2.0 near-zero methane-intensity ambition (% of gas throughput).
OGMP_TARGET_INTENSITY_PCT = 0.2

# Mapping from our NUPRC/IPCC tier to the OGMP 2.0 reporting level. Tier 2 uses
# source-specific emission factors -> Level 3; Tier 3 is source-level measurement
# -> Level 4. Level 5 requires SITE-LEVEL measurement reconciled to the source-level
# inventory (e.g. the satellite/site reconciliation in A3) and is therefore NOT
# claimed from engine data alone.
OGMP_LEVEL_FOR_TIER = {"Tier 2": 3, "Tier 3": 4}


def _intensity(ch4_tonnes: float, throughput_tonnes: float | None) -> tuple[float | None, str]:
    if throughput_tonnes is None:
        return None, "throughput_not_provided"
    if throughput_tonnes <= 0:
        return None, "throughput_not_provided"
    pct = round(100 * ch4_tonnes / throughput_tonnes, 4)
    flag = "above_target" if pct > OGMP_TARGET_INTENSITY_PCT else "at_or_below_target"
    return pct, flag


def build_ogmp2_report(
    inventory: Inventory,
    operator: str,
    asset: str,
    gas_throughput_tonnes: float | None = None,
    source_throughput_tonnes: dict[str, float] | None = None,
    prepared_by: str = "PetroBrain MRV",
    **_ignored: Any,
) -> dict[str, Any]:
    gwp = GWP_SETS[inventory.gwp_set]
    source_throughput_tonnes = source_throughput_tonnes or {}

    sources: list[dict[str, Any]] = []
    levels: list[int] = []
    ch4_measured = 0.0
    ch4_generic = 0.0
    for l in inventory.lines:
        level = OGMP_LEVEL_FOR_TIER.get(l.tier, 2)
        levels.append(level)
        measured = l.tier == "Tier 3"
        if measured:
            ch4_measured += l.ch4_tonnes
        else:
            ch4_generic += l.ch4_tonnes
        intensity_pct, flag = _intensity(
            l.ch4_tonnes, source_throughput_tonnes.get(l.source_id)
        )
        sources.append({
            "source_id": l.source_id,
            "source_type": l.source_type,
            "ch4_tonnes": round(l.ch4_tonnes, 4),
            "ch4_co2e_tonnes": round(l.ch4_tonnes * gwp["CH4"], 4),
            "ogmp_level": level,
            "quantification_basis": "measured" if measured else "generic_factor",
            "methane_intensity_pct": intensity_pct,
            "target_flag": flag,
        })

    total_ch4 = round(sum(l.ch4_tonnes for l in inventory.lines), 4)
    total_ch4_co2e = round(total_ch4 * gwp["CH4"], 4)
    site_intensity_pct, site_flag = _intensity(total_ch4, gas_throughput_tonnes)
    measured_total = ch4_measured + ch4_generic
    measured_pct = round(100 * ch4_measured / measured_total, 1) if measured_total > 0 else 0.0

    report: dict[str, Any] = {
        "report_type": "OGMP 2.0 Methane Report",
        "framework": "OGMP 2.0",
        "operator": operator,
        "asset": asset,
        "facility_id": inventory.facility_id,
        "reporting_period": inventory.period,
        "prepared_by": prepared_by,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "gwp_basis": f"IPCC {inventory.gwp_set} GWP100",
        "target_methane_intensity_pct": OGMP_TARGET_INTENSITY_PCT,
        "site_level": {
            "total_ch4_tonnes": total_ch4,
            "total_ch4_co2e_tonnes": total_ch4_co2e,
            "methane_intensity_pct": site_intensity_pct,
            "target_flag": site_flag,
        },
        "reporting_level": {
            "overall_level": min(levels) if levels else None,
            "levels_by_source": _count_levels(levels),
            "note": (
                "OGMP 2.0 Level 4 = source-level measurement; Level 5 additionally "
                "requires site-level measurement reconciled to the source-level "
                "inventory. Level 5 is not asserted from engine data alone."
            ),
        },
        "factor_basis_split": {
            "ch4_measured_tonnes": round(ch4_measured, 4),
            "ch4_generic_factor_tonnes": round(ch4_generic, 4),
            "measured_pct_of_ch4": measured_pct,
        },
        "sources": sources,
        "methodology_notes": [
            "Methane intensity = CH4 emitted (t) / gas throughput (t) x 100, vs the "
            f"OGMP 2.0 ~{OGMP_TARGET_INTENSITY_PCT}% near-zero ambition.",
            "Where a throughput denominator is not supplied, intensity is reported as "
            "null (throughput_not_provided) rather than estimated.",
            "OGMP levels are mapped from the source quantification tier; confirm against "
            "the current OGMP 2.0 technical guidance before submission.",
        ],
    }
    report["audit_sha256"] = audit_sha256({k: report[k] for k in (
        "operator", "asset", "facility_id", "reporting_period",
        "site_level", "factor_basis_split", "sources", "gwp_basis")})
    return report


def _count_levels(levels: list[int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for lvl in levels:
        key = f"Level {lvl}"
        out[key] = out.get(key, 0) + 1
    return out
