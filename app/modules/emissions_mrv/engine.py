"""
Emissions / MRV calculation engine (NUPRC Tier 2 -> Tier 3 ready).

Computes a facility GHG inventory from source-level activity data, converts to
CO2-equivalent using a configurable GWP set, and records the method/tier and the
factor sources for every line so the result is fully auditable.

Source types covered:
  - FLARING   : carbon balance on flared gas + methane slip from incomplete combustion
  - VENTING   : direct release of gas composition (CH4, CO2, ...)
  - FUGITIVE  : Tier 2 (component-count x average EF) OR Tier 3 (measured leak rates)
  - COMBUSTION: fuel volume x emission factor (engines, turbines, heaters)

Design intent: the SAME engine serves Tier 2 and Tier 3. The difference is the
*source of the numbers* (generic/averaged factors vs facility measurement), which is
recorded per line in `method`. This is exactly the transition NUPRC requires
(Tier 2 from Q3 2026 -> Tier 3 measurement-based from Jan 2027).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .factors import (
    COMPONENT_PROPERTIES,
    DEFAULT_FLARE_COMBUSTION_EFFICIENCY,
    DEFAULT_GWP_SET,
    GWP_SETS,
    MW_CH4,
    MW_CO2,
    OG_SCOPE3_CATEGORIES,
    TIER2_FUGITIVE_EF_KG_CH4_PER_COMPONENT_HR,
)

SCF_PER_LBMOL = 379.49
LB_PER_KG = 2.2046226218
KG_PER_TONNE = 1000.0


def _lb_to_tonne(lb: float) -> float:
    return lb / LB_PER_KG / KG_PER_TONNE


@dataclass
class EmissionLine:
    source_id: str
    source_type: str          # flaring | venting | fugitive | combustion | purchased_power | scope3_*
    tier: str                 # "Tier 2" | "Tier 3"
    method: str               # human-readable method + factor source (audit)
    scope: str = "scope_1"    # "scope_1" | "scope_2" | "scope_3" (GHG-Protocol scope)
    ch4_tonnes: float = 0.0
    co2_tonnes: float = 0.0
    n2o_tonnes: float = 0.0
    activity: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        for k in ("ch4_tonnes", "co2_tonnes", "n2o_tonnes"):
            d[k] = round(d[k], 4)
        return d


def _normalize_composition(comp: dict[str, float]) -> dict[str, float]:
    total = sum(comp.values())
    if total <= 0:
        raise ValueError("gas composition mole fractions must sum to > 0")
    return {k: v / total for k, v in comp.items()}


def flaring(
    source_id: str,
    gas_volume_scf: float,
    composition: dict[str, float],
    combustion_efficiency: float | None = None,
    measured: bool = False,
) -> EmissionLine:
    """
    Carbon balance:
      lbmol gas = V / 379.49
      combusted carbon -> CO2 ; un-combusted CH4 -> methane slip ; feed CO2 passes through.
    """
    ce = combustion_efficiency if combustion_efficiency is not None else DEFAULT_FLARE_COMBUSTION_EFFICIENCY
    comp = _normalize_composition(composition)
    lbmol = gas_volume_scf / SCF_PER_LBMOL

    # Carbon from hydrocarbons (exclude feed CO2, which we pass through separately)
    hc_carbon_lbmol = sum(
        comp.get(c, 0.0) * COMPONENT_PROPERTIES[c]["carbon"]
        for c in COMPONENT_PROPERTIES
        if c not in ("CO2", "N2", "H2S")
    ) * lbmol

    # CO2: combusted hydrocarbon carbon -> CO2, plus any CO2 in the feed passes through
    co2_from_combustion_lb = hc_carbon_lbmol * ce * MW_CO2
    feed_co2_lb = comp.get("CO2", 0.0) * lbmol * MW_CO2
    co2_lb = co2_from_combustion_lb + feed_co2_lb

    # CH4 slip: methane that fails to combust
    ch4_slip_lb = comp.get("CH4", 0.0) * lbmol * (1 - ce) * MW_CH4

    return EmissionLine(
        source_id=source_id,
        source_type="flaring",
        tier="Tier 3" if measured else "Tier 2",
        method=(
            f"Carbon-balance flaring, combustion efficiency {ce:.3f} "
            f"({'measured' if measured else 'default factor'})"
        ),
        ch4_tonnes=_lb_to_tonne(ch4_slip_lb),
        co2_tonnes=_lb_to_tonne(co2_lb),
        activity={"gas_volume_scf": gas_volume_scf, "combustion_efficiency": ce},
    )


def venting(source_id: str, gas_volume_scf: float, composition: dict[str, float],
            measured: bool = False) -> EmissionLine:
    """Direct release: each GHG component emitted as-is (no combustion)."""
    comp = _normalize_composition(composition)
    lbmol = gas_volume_scf / SCF_PER_LBMOL
    ch4_lb = comp.get("CH4", 0.0) * lbmol * MW_CH4
    co2_lb = comp.get("CO2", 0.0) * lbmol * MW_CO2
    return EmissionLine(
        source_id=source_id,
        source_type="venting",
        tier="Tier 3" if measured else "Tier 2",
        method=f"Direct vent of gas composition ({'measured' if measured else 'engineering estimate'})",
        ch4_tonnes=_lb_to_tonne(ch4_lb),
        co2_tonnes=_lb_to_tonne(co2_lb),
        activity={"gas_volume_scf": gas_volume_scf},
    )


def fugitive_tier2(source_id: str, component_counts: dict[str, int],
                   operating_hours: float) -> EmissionLine:
    """Tier 2 component-count method: sum(count x average EF) x hours."""
    ch4_kg = 0.0
    for ctype, count in component_counts.items():
        ef = TIER2_FUGITIVE_EF_KG_CH4_PER_COMPONENT_HR.get(
            ctype, TIER2_FUGITIVE_EF_KG_CH4_PER_COMPONENT_HR["other"]
        )
        ch4_kg += count * ef * operating_hours
    return EmissionLine(
        source_id=source_id,
        source_type="fugitive",
        tier="Tier 2",
        method="Average emission factors x component count (NUPRC/API EF set)",
        ch4_tonnes=ch4_kg / KG_PER_TONNE,
        activity={"component_counts": component_counts, "operating_hours": operating_hours},
    )


def fugitive_tier3(source_id: str, measured_leaks_kg_ch4_per_hr: list[float],
                   operating_hours: float) -> EmissionLine:
    """
    Tier 3 measurement-based: leak rates quantified by OGI/LDAR / hi-flow sampling,
    summed and scaled to the reporting period. This is the directive's end-state.
    """
    total_rate = sum(measured_leaks_kg_ch4_per_hr)
    ch4_kg = total_rate * operating_hours
    return EmissionLine(
        source_id=source_id,
        source_type="fugitive",
        tier="Tier 3",
        method="Measurement-based (OGI/LDAR quantified leak rates) scaled to period",
        ch4_tonnes=ch4_kg / KG_PER_TONNE,
        activity={
            "n_leaks": len(measured_leaks_kg_ch4_per_hr),
            "total_rate_kg_hr": round(total_rate, 4),
            "operating_hours": operating_hours,
        },
    )


def combustion(source_id: str, fuel_scf: float,
               co2_kg_per_scf: float, ch4_kg_per_scf: float = 0.0,
               n2o_kg_per_scf: float = 0.0, measured: bool = False) -> EmissionLine:
    """Stationary combustion (engines/turbines/heaters) via fuel x emission factor."""
    return EmissionLine(
        source_id=source_id,
        source_type="combustion",
        tier="Tier 3" if measured else "Tier 2",
        method=f"Fuel-based emission factors ({'CEMS/measured' if measured else 'standard EF'})",
        co2_tonnes=fuel_scf * co2_kg_per_scf / KG_PER_TONNE,
        ch4_tonnes=fuel_scf * ch4_kg_per_scf / KG_PER_TONNE,
        n2o_tonnes=fuel_scf * n2o_kg_per_scf / KG_PER_TONNE,
        activity={"fuel_scf": fuel_scf},
    )


def scope2_purchased_power(
    source_id: str,
    mwh: float,
    grid_emission_factor_kg_co2_per_mwh: float,
    measured: bool = False,
) -> EmissionLine:
    """
    Scope 2: purchased grid electricity. CO2e = MWh x grid emission factor.
    The grid factor is jurisdiction-specific (e.g. the Nigerian grid factor) and
    must be supplied per reporting period from a published source, recorded in the
    method string for the audit trail.
    """
    co2_kg = mwh * grid_emission_factor_kg_co2_per_mwh
    return EmissionLine(
        source_id=source_id,
        source_type="purchased_power",
        tier="Tier 3" if measured else "Tier 2",
        method=(
            f"Scope 2 purchased electricity: {mwh} MWh x "
            f"{grid_emission_factor_kg_co2_per_mwh} kg CO2/MWh grid factor "
            f"({'metered consumption' if measured else 'published grid factor'})"
        ),
        scope="scope_2",
        co2_tonnes=co2_kg / KG_PER_TONNE,
        activity={
            "mwh": mwh,
            "grid_emission_factor_kg_co2_per_mwh": grid_emission_factor_kg_co2_per_mwh,
        },
    )


def scope3_category(
    source_id: str,
    category: str,
    activity_value: float,
    emission_factor: float,
    unit: str,
) -> EmissionLine:
    """
    Scope 3: value-chain emissions for an O&G-relevant category (see
    factors.OG_SCOPE3_CATEGORIES). The biggest line for an operator is normally
    `use_of_sold_products` - the downstream combustion of the hydrocarbons sold.

    CO2e = activity_value x emission_factor, where emission_factor is kg CO2e per
    `unit`. Scope-3 factors are already expressed as CO2e, so the value is carried
    in the CO2 slot (GWP("CO2") = 1.0) to keep totals() and per-line CO2e exact
    without double-applying a GWP. CH4/N2O remain 0 for these activity-based lines.
    """
    if category not in OG_SCOPE3_CATEGORIES:
        raise ValueError(
            f"unknown O&G Scope-3 category {category!r}; "
            f"expected one of {sorted(OG_SCOPE3_CATEGORIES)}"
        )
    cat = OG_SCOPE3_CATEGORIES[category]
    co2e_kg = activity_value * emission_factor
    return EmissionLine(
        source_id=source_id,
        source_type=f"scope3_{category}",
        tier="Tier 2",  # Scope 3 is inherently an activity-based estimate
        method=(
            f"Scope 3 Cat {cat['ghg_protocol_category']} ({cat['label']}): "
            f"{activity_value} {unit} x {emission_factor} kg CO2e/{unit} "
            "(activity-based estimate)"
        ),
        scope="scope_3",
        co2_tonnes=co2e_kg / KG_PER_TONNE,
        activity={
            "category": category,
            "ghg_protocol_category": cat["ghg_protocol_category"],
            "activity_value": activity_value,
            "emission_factor": emission_factor,
            "unit": unit,
        },
    )


@dataclass
class Inventory:
    facility_id: str
    period: str
    gwp_set: str
    lines: list[EmissionLine]

    def totals(self) -> dict[str, float | str]:
        gwp = GWP_SETS[self.gwp_set]
        ch4 = sum(l.ch4_tonnes for l in self.lines)
        co2 = sum(l.co2_tonnes for l in self.lines)
        n2o = sum(l.n2o_tonnes for l in self.lines)
        co2e = co2 * gwp["CO2"] + ch4 * gwp["CH4"] + n2o * gwp["N2O"]
        return {
            "ch4_tonnes": round(ch4, 3),
            "co2_tonnes": round(co2, 3),
            "n2o_tonnes": round(n2o, 3),
            "co2e_tonnes": round(co2e, 3),
            "gwp_set": self.gwp_set,
        }

    def methane_intensity(self, gas_throughput_scf: float) -> float | None:
        """CH4 emitted as % of gas handled - a key NUPRC/OGMP-style metric."""
        if gas_throughput_scf <= 0:
            return None
        ch4_kg = sum(l.ch4_tonnes for l in self.lines) * KG_PER_TONNE
        # crude mass of throughput methane omitted; intensity here = CH4 tonnes / throughput
        return round(ch4_kg / gas_throughput_scf, 8)

    def tier_summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for l in self.lines:
            out[l.tier] = out.get(l.tier, 0) + 1
        return out

    def scope_summary(self) -> dict[str, float]:
        """CO2e tonnes per GHG-Protocol scope, using the inventory's GWP set.
        Always returns all three scopes (0.0 if absent) so reports have a stable shape.
        The three values sum to totals()["co2e_tonnes"]."""
        gwp = GWP_SETS[self.gwp_set]
        out: dict[str, float] = {"scope_1": 0.0, "scope_2": 0.0, "scope_3": 0.0}
        for l in self.lines:
            co2e = l.co2_tonnes * gwp["CO2"] + l.ch4_tonnes * gwp["CH4"] + l.n2o_tonnes * gwp["N2O"]
            out[l.scope] = out.get(l.scope, 0.0) + co2e
        return {k: round(v, 3) for k, v in out.items()}

    def as_dict(self) -> dict[str, Any]:
        gwp = GWP_SETS[self.gwp_set]
        lines = []
        for l in self.lines:
            d = l.as_dict()
            # Per-line CO2e contribution, using the inventory's GWP set (the
            # line itself is GWP-agnostic). Sums to totals["co2e_tonnes"].
            d["co2e_tonnes"] = round(
                l.co2_tonnes * gwp["CO2"] + l.ch4_tonnes * gwp["CH4"] + l.n2o_tonnes * gwp["N2O"], 4
            )
            lines.append(d)
        return {
            "facility_id": self.facility_id,
            "period": self.period,
            "totals": self.totals(),
            "tier_summary": self.tier_summary(),
            "lines": lines,
        }


def build_inventory(facility_id: str, period: str, lines: list[EmissionLine],
                    gwp_set: str = DEFAULT_GWP_SET) -> Inventory:
    if gwp_set not in GWP_SETS:
        raise ValueError(f"unknown GWP set {gwp_set}")
    return Inventory(facility_id=facility_id, period=period, gwp_set=gwp_set, lines=lines)


DEFAULT_MATERIAL_VARIANCE_PCT = 20.0


def reconcile_flaring(
    reported_inventory_line: Any,
    satellite_observations: Any,
    material_threshold_pct: float = DEFAULT_MATERIAL_VARIANCE_PCT,
) -> dict[str, Any]:
    """
    Cross-reference a REPORTED flaring line against independent satellite
    observation (e.g. VIIRS Nightfire flared-volume detections).

    `reported_inventory_line` is a flaring EmissionLine (or its as_dict()); the
    reported volume is read from activity["gas_volume_scf"].

    `satellite_observations` may be a ProviderResult (or its as_dict()), a plain
    list of observation dicts, or None. Observations are summed on the comparable
    quantity `flared_volume_scf`.

    HONESTY: if the satellite source is unavailable the result says so and computes
    no variance. Zero detections across a window the source DID cover is a genuine
    observation of ~0 (distinct from "unavailable"). A detection without a derivable
    volume is counted but not summed, and that is stated.
    """
    source_type = _line_attr(reported_inventory_line, "source_type")
    if source_type != "flaring":
        raise ValueError(
            f"reconcile_flaring expects a flaring line, got source_type={source_type!r}"
        )
    source_id = _line_attr(reported_inventory_line, "source_id")
    activity = _line_attr(reported_inventory_line, "activity") or {}
    reported_scf = activity.get("gas_volume_scf")
    reported_scf = float(reported_scf) if reported_scf is not None else None

    available, reason, observations, provider = _normalize_observations(satellite_observations)

    result: dict[str, Any] = {
        "source_id": source_id,
        "source_type": "flaring",
        "provider": provider,
        "reported_flared_scf": round(reported_scf, 2) if reported_scf is not None else None,
        "reconciliation_available": available,
        "unavailable_reason": reason,
        "observed_flared_scf": None,
        "variance_pct": None,
        "observed_exceeds_reported": False,
        "material_threshold_pct": material_threshold_pct,
        "n_observations": len(observations),
        "notes": [],
    }

    if not available:
        result["notes"].append(
            "Satellite flaring data unavailable for this source/period - no variance "
            "computed. " + (reason or "")
        )
        return result

    observed_scf, observed_notes = _sum_observed_flared_scf(observations)
    result["notes"].extend(observed_notes)
    result["observed_flared_scf"] = round(observed_scf, 2) if observed_scf is not None else None

    if reported_scf is None:
        result["notes"].append("Reported line carries no flared volume; cannot compute variance.")
        return result
    if observed_scf is None:
        return result

    if reported_scf > 0:
        result["variance_pct"] = round((observed_scf - reported_scf) / reported_scf * 100, 2)
        result["observed_exceeds_reported"] = observed_scf > reported_scf * (1 + material_threshold_pct / 100)
    else:
        # Reported zero with any observed flaring is, itself, a material discrepancy.
        result["observed_exceeds_reported"] = observed_scf > 0
        if observed_scf > 0:
            result["notes"].append(
                "Reported flared volume is zero but flaring was observed - material discrepancy."
            )

    if result["observed_exceeds_reported"]:
        result["notes"].append(
            "Observed flaring materially exceeds reported - investigate metering/reporting "
            "coverage for this source."
        )
    return result


def _sum_observed_flared_scf(observations: list[dict[str, Any]]) -> tuple[float | None, list[str]]:
    """Sum the comparable flared-volume quantity across observations.

    Returns (observed_scf, notes). 0.0 = covered window with no detections;
    None = detections present but none carry a derivable volume."""
    notes: list[str] = []
    n_obs = len(observations)
    if n_obs == 0:
        notes.append("No flaring detections in the observation window (observed ~0).")
        return 0.0, notes
    present = [
        float(o["flared_volume_scf"])
        for o in observations
        if isinstance(o, dict) and o.get("flared_volume_scf") is not None
    ]
    if not present:
        notes.append(
            "Flaring detected but no flared volume derivable from the data; cannot "
            "quantify a volume variance."
        )
        return None, notes
    if len(present) < n_obs:
        notes.append(
            f"{n_obs - len(present)} of {n_obs} detection(s) had no derivable flared "
            "volume; observed total is a lower bound."
        )
    return sum(present), notes


def _line_attr(line: Any, name: str) -> Any:
    if isinstance(line, dict):
        return line.get(name)
    return getattr(line, name, None)


def _normalize_observations(obs: Any) -> tuple[bool, str | None, list[dict[str, Any]], str | None]:
    """Coerce a ProviderResult / dict / list / None into
    (available, unavailable_reason, observations, provider)."""
    if obs is None:
        return False, "no satellite observations supplied", [], None
    if isinstance(obs, list):
        return True, None, obs, None
    if hasattr(obs, "as_dict"):
        obs = obs.as_dict()
    if isinstance(obs, dict):
        available = bool(obs.get("available", True))
        return (
            available,
            obs.get("unavailable_reason"),
            list(obs.get("observations") or []),
            obs.get("provider"),
        )
    return False, f"unrecognized satellite observation payload: {type(obs).__name__}", [], None
