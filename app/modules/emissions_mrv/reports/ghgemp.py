"""
GHGEMP / MRV report generator (NUPRC).

Turns an Inventory into a structured, audit-ready submission object aligned to the
NUPRC reporting requirements (GHG Emissions Management Plan + Methane/GHG Emissions
Accounting and Inventories). The exact field names/layout of the gazetted NUPRC
templates must be confirmed against the current standardized templates; this builds
the content and the audit trail. Render to PDF/XLSX/DOCX downstream.

Moved from app/modules/emissions_mrv/ghgemp_template.py (A2 refactor). Behavior and
the audit hash are unchanged; ghgemp_template.py now re-exports from here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..engine import Inventory
from ._common import audit_sha256


def build_ghgemp_report(
    inventory: Inventory,
    operator: str,
    asset: str,
    jurisdiction: str = "Nigeria (NUPRC)",
    prepared_by: str = "PetroBrain MRV",
    target_tier: str = "Tier 3",
) -> dict[str, Any]:
    totals = inventory.totals()
    tiers = inventory.tier_summary()

    # readiness: what fraction of lines already meet the target (measurement) tier?
    n = len(inventory.lines)
    at_target = sum(1 for l in inventory.lines if l.tier == target_tier)
    readiness_pct = round(100 * at_target / n, 1) if n else 0.0

    gaps = [
        {"source_id": l.source_id, "source_type": l.source_type, "current_tier": l.tier}
        for l in inventory.lines
        if l.tier != target_tier
    ]

    report: dict[str, Any] = {
        "report_type": "GHG Emissions Accounting & Inventory",
        "jurisdiction": jurisdiction,
        "operator": operator,
        "asset": asset,
        "facility_id": inventory.facility_id,
        "reporting_period": inventory.period,
        "prepared_by": prepared_by,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "gwp_basis": f"IPCC {inventory.gwp_set} GWP100",
        "summary": {
            "total_co2e_tonnes": totals["co2e_tonnes"],
            "total_ch4_tonnes": totals["ch4_tonnes"],
            "total_co2_tonnes": totals["co2_tonnes"],
            "total_n2o_tonnes": totals["n2o_tonnes"],
        },
        "tier_status": {
            "target_tier": target_tier,
            "lines_by_tier": tiers,
            "tier_readiness_pct": readiness_pct,
            "gaps_to_target": gaps,
        },
        "source_inventory": [l.as_dict() for l in inventory.lines],
        "methodology_notes": [
            "Flaring emissions computed by carbon balance with stated combustion "
            "efficiency; methane slip = uncombusted CH4 fraction.",
            "Fugitive emissions reported per source as Tier 2 (component-count x "
            "average EF) or Tier 3 (measurement-based, OGI/LDAR quantified).",
            "CO2e computed using the stated IPCC GWP100 set. Confirm the GWP set and "
            "emission factors against current NUPRC gazetted guidance before filing.",
        ],
        "compliance_flags": _compliance_flags(target_tier, readiness_pct, gaps),
    }
    # tamper-evident audit hash over the substantive content
    report["audit_sha256"] = audit_sha256({k: report[k] for k in (
        "operator", "asset", "facility_id", "reporting_period",
        "summary", "source_inventory", "gwp_basis")})
    return report


def build_mrv_readiness_summary(report: dict[str, Any]) -> dict[str, Any]:
    """
    Commercial wedge summary for operators: executive status, gap count, priority
    sources, next actions, and the audit hash. It uses the deterministic inventory
    report; it does not recompute emissions.
    """
    tier_status = report["tier_status"]
    summary = report["summary"]
    gaps = tier_status["gaps_to_target"]
    readiness_pct = tier_status["tier_readiness_pct"]
    status = "ready_for_target_tier" if readiness_pct == 100 else "action_required"
    priority_gaps = sorted(gaps, key=lambda g: (g["source_type"], g["source_id"]))[:5]
    gap_action_plan = [_gap_action(gap) for gap in gaps]
    next_actions = []
    if gaps:
        next_actions.append("Assign measurement coverage for each non-target-tier source.")
        next_actions.append("Capture source-level evidence: meters, OGI/LDAR records, or calculation basis.")
        next_actions.append("Re-run the inventory and preserve the audit hash after each data update.")
    else:
        next_actions.append("Preserve the audit package and verify factors/GWP against current NUPRC guidance.")
        next_actions.append("Prepare management approval and filing package from the generated GHGEMP report.")
    return {
        "status": status,
        "facility_id": report["facility_id"],
        "reporting_period": report["reporting_period"],
        "target_tier": tier_status["target_tier"],
        "tier_readiness_pct": readiness_pct,
        "gap_count": len(gaps),
        "priority_gaps": priority_gaps,
        "gap_action_plan": gap_action_plan,
        "total_co2e_tonnes": summary["total_co2e_tonnes"],
        "total_ch4_tonnes": summary["total_ch4_tonnes"],
        "compliance_flags": report["compliance_flags"],
        "next_actions": next_actions,
        "audit_sha256": report["audit_sha256"],
    }


def _gap_action(gap: dict[str, Any]) -> dict[str, Any]:
    source_type = gap["source_type"]
    if source_type == "fugitive":
        action = "Move to quantified OGI/LDAR or hi-flow measurement and record leak rates."
        evidence = "LDAR campaign record, quantified leak list, repair status, operating hours."
    elif source_type == "flaring":
        action = "Use metered flare gas volume/composition and measured combustion efficiency where required."
        evidence = "Flare meter records, gas composition, combustion efficiency basis, calibration record."
    elif source_type == "venting":
        action = "Use measured or metered vent volume and current gas composition for each event/source."
        evidence = "Vent log, meter record, gas analysis, event duration and approval trail."
    elif source_type == "combustion":
        action = "Use measured fuel consumption and approved emission factors or CEMS where applicable."
        evidence = "Fuel meter records, equipment run hours, factor source, calibration or CEMS record."
    else:
        action = "Define a source-specific measurement method and preserve the calculation basis."
        evidence = "Measurement record, source register entry, factor source, reviewer sign-off."
    return {
        "source_id": gap["source_id"],
        "source_type": source_type,
        "current_tier": gap["current_tier"],
        "required_action": action,
        "evidence_required": evidence,
    }


def _compliance_flags(target_tier: str, readiness_pct: float,
                      gaps: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    if target_tier == "Tier 3" and readiness_pct < 100:
        flags.append(
            f"{len(gaps)} source(s) not yet on measurement-based Tier 3. NUPRC requires "
            "full Tier 3 measurement-based MRV from January 2027 - plan measurement "
            "coverage (OGI/LDAR, metering) for the listed gaps."
        )
    if readiness_pct == 0:
        flags.append("All sources are estimate-based. Begin Tier 2 reporting now and "
                     "schedule the transition to measurement-based quantification.")
    return flags
