"""
Validation tests. Run from the repo root: python -m pytest -q  (or run this file).
The numbers here are hand-checked against standard well-control / emissions math.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.calc.drilling import hydrostatic_pressure, equivalent_circulating_density, kill_mud_weight, maasp
from app.calc.production import (
    arps_exponential_cumulative,
    arps_exponential_rate,
    arps_harmonic_rate,
    arps_hyperbolic_rate,
    vogel_ipr,
)
from app.modules.well_control.kill_sheet import WellInputs, build_kill_sheet
from app.modules.well_control.agent import detect_live_event
from app.modules.emissions_mrv.engine import (
    flaring, venting, fugitive_tier2, fugitive_tier3, build_inventory,
    scope2_purchased_power, scope3_category, reconcile_flaring,
)
from app.data_providers import (
    SatelliteFlaringProvider, ObservationRequest, ProviderResult, DateRange,
    bounding_box_for_point, asset_bounding_box, asset_coordinates,
)
from app.modules.emissions_mrv.engine import combustion
from app.modules.emissions_mrv.abatement import (
    model_abatement, abatement_catalog, capital_recovery_factor,
)
from app.modules.emissions_mrv.ghgemp_template import build_ghgemp_report, build_mrv_readiness_summary
from app.modules.emissions_mrv.reports import (
    build_report, build_ogmp2_report, build_csrd_report, build_iso14064_report,
)


def approx(a, b, tol=1e-2):
    return abs(a - b) <= tol * max(1, abs(b))


def test_hydrostatic():
    # 0.052 * 9.6 * 10000 = 4992 psi
    assert approx(hydrostatic_pressure(9.6, 10000).result, 4992)


def test_ecd():
    # 9.6 + 200/(0.052*10000) = 9.6 + 0.3846 = 9.9846
    assert approx(equivalent_circulating_density(9.6, 200, 10000).result, 9.9846)


def test_kill_mud_weight():
    # 9.6 + 400/(0.052*10000) = 9.6 + 0.7692 = 10.369
    r = kill_mud_weight(9.6, 400, 10000)
    assert approx(r.result, 10.369)
    assert r.safety_critical is True


def test_maasp():
    # 0.052*(14-9.6)*5000 = 0.052*4.4*5000 = 1144
    assert approx(maasp(14.0, 9.6, 5000).result, 1144)


def test_vogel():
    # test point 500 STB/d at Pwf/Pr=0.5 -> denom = 1-0.1-0.2 = 0.7 -> qomax=714.3
    r = vogel_ipr(500, 1500, 3000)
    assert approx(r.result, 714.29)


def test_arps_exponential_rate():
    # q = 1000 * exp(-0.2 * 2) = 670.32 STB/d
    r = arps_exponential_rate(1000, 0.2, 2)
    assert approx(r.result, 670.32, tol=1e-3)
    assert r.unit == "STB/d"


def test_arps_exponential_cumulative():
    # Np = (1000 / 0.2) * (1 - exp(-0.2 * 2)) * 365.25 = 601,922 STB
    r = arps_exponential_cumulative(1000, 0.2, 2)
    assert approx(r.result, 601922, tol=1e-3)
    assert r.unit == "STB"


def test_arps_harmonic_rate():
    # q = 1000 / (1 + 0.2 * 2) = 714.29 STB/d
    r = arps_harmonic_rate(1000, 0.2, 2)
    assert approx(r.result, 714.29, tol=1e-3)


def test_arps_hyperbolic_rate():
    # q = 1000 / (1 + 0.5 * 0.2 * 2)^(1/0.5) = 694.44 STB/d
    r = arps_hyperbolic_rate(1000, 0.2, 0.5, 2)
    assert approx(r.result, 694.44, tol=1e-3)
    assert r.unit == "STB/d"


def test_kill_sheet_full():
    w = WellInputs(
        tvd_ft=10000, md_ft=10000, omw_ppg=9.6, sidpp_psi=400, sicp_psi=600,
        pit_gain_bbl=20, scr_pressure_psi=800, pump_output_bbl_per_stk=0.1,
        drill_string_volume_bbl=120, annulus_volume_bit_to_surface_bbl=180,
        annular_capacity_bbl_per_ft=0.0459, shoe_tvd_ft=5000, max_allowable_mw_ppg=14.0,
    )
    ks = build_kill_sheet(w, method="wait_and_weight")
    assert approx(ks.kill_mud_weight_ppg, 10.37, tol=2e-3)
    assert approx(ks.initial_circulating_pressure_psi, 1200)   # 400+800
    # FCP = 800 * 10.369/9.6 = 864
    assert approx(ks.final_circulating_pressure_psi, 864, tol=2e-3)
    assert approx(ks.strokes_surface_to_bit, 1200)             # 120/0.1
    assert approx(ks.strokes_bit_to_surface, 1800)             # 180/0.1
    assert ks.maasp_psi == 1144
    # pressure schedule starts at ICP, ends at FCP
    assert ks.pressure_schedule[0]["drill_pipe_pressure_psi"] == 1200
    assert abs(ks.pressure_schedule[-1]["drill_pipe_pressure_psi"] - 864) <= 1
    # influx gradient: 0.052*9.6 - (600-400)/H ; H = 20/0.0459 = 435.7 ft
    # = 0.4992 - 200/435.7 = 0.4992 - 0.459 = 0.040 -> gas
    assert ks.influx["inferred_fluid"].startswith("gas")
    assert "DECISION SUPPORT ONLY" in ks.banner


def test_live_event_detection():
    assert detect_live_event("We are taking a kick right now!") is True
    assert detect_live_event("What is the formula for ECD?") is False


def test_flaring_carbon_balance():
    # 1,000,000 scf of pure methane, CE = 0.98
    # lbmol = 1e6/379.49 = 2635.1
    # carbon lbmol = 2635.1 * 1 = 2635.1 ; CO2 = 2635.1*0.98*44.01 lb = 113,656 lb = 51.55 t
    # CH4 slip = 2635.1*0.02*16.043 lb = 845.6 lb = 0.3835 t
    line = flaring("FL-1", 1_000_000, {"CH4": 1.0}, combustion_efficiency=0.98)
    assert approx(line.co2_tonnes, 51.55, tol=1e-2)
    assert approx(line.ch4_tonnes, 0.3835, tol=2e-2)


def test_venting():
    # vent 100,000 scf pure methane -> all CH4
    # lbmol=263.51 -> CH4 lb = 263.51*16.043=4227.9 lb = 1.917 t
    line = venting("V-1", 100_000, {"CH4": 1.0})
    assert approx(line.ch4_tonnes, 1.917, tol=1e-2)
    assert line.co2_tonnes == 0.0


def test_fugitive_tiers_and_inventory():
    f2 = fugitive_tier2("AREA-1", {"valve": 100, "flange": 200}, operating_hours=8760)
    # valves: 100*0.0045*8760 = 3942 kg ; flanges: 200*0.00039*8760=683.3 kg => 4.6253 t
    assert approx(f2.ch4_tonnes, 4.6253, tol=1e-2)
    f3 = fugitive_tier3("AREA-2", [0.5, 0.3, 0.2], operating_hours=8760)  # 1.0 kg/hr total
    # 1.0*8760 = 8760 kg = 8.76 t
    assert approx(f3.ch4_tonnes, 8.76)
    inv = build_inventory("FAC-1", "2026-Q3", [f2, f3], gwp_set="AR6")
    t = inv.totals()
    # CO2e from CH4 only: (4.6253+8.76)*29.8 = 398.8 t
    assert approx(t["co2e_tonnes"], (4.6253 + 8.76) * 29.8, tol=1e-2)
    assert inv.tier_summary() == {"Tier 2": 1, "Tier 3": 1}


def test_ghgemp_report():
    f2 = fugitive_tier2("AREA-1", {"valve": 50}, 8760)
    f3 = fugitive_tier3("AREA-2", [0.2], 8760)
    inv = build_inventory("FAC-1", "2026-Q3", [f2, f3])
    rep = build_ghgemp_report(inv, operator="Acme E&P", asset="OML-XX", target_tier="Tier 3")
    assert rep["tier_status"]["tier_readiness_pct"] == 50.0  # 1 of 2 at Tier 3
    assert len(rep["tier_status"]["gaps_to_target"]) == 1
    assert rep["audit_sha256"]
    assert any("Tier 3" in f for f in rep["compliance_flags"])


def test_mrv_readiness_summary():
    f2 = fugitive_tier2("AREA-1", {"valve": 50}, 8760)
    f3 = fugitive_tier3("AREA-2", [0.2], 8760)
    inv = build_inventory("FAC-1", "2026-Q3", [f2, f3])
    rep = build_ghgemp_report(inv, operator="Acme E&P", asset="OML-XX", target_tier="Tier 3")
    summary = build_mrv_readiness_summary(rep)
    assert summary["status"] == "action_required"
    assert summary["tier_readiness_pct"] == 50.0
    assert summary["gap_count"] == 1
    assert summary["priority_gaps"][0]["source_id"] == "AREA-1"
    assert summary["gap_action_plan"][0]["source_id"] == "AREA-1"
    assert "OGI/LDAR" in summary["gap_action_plan"][0]["required_action"]
    assert summary["audit_sha256"] == rep["audit_sha256"]


def test_scope_default_tagging():
    # Existing Scope-1 sources default their scope without any caller change.
    fl = flaring("FL-1", 1_000_000, {"CH4": 1.0}, combustion_efficiency=0.98)
    f2 = fugitive_tier2("AREA-1", {"valve": 100}, 8760)
    assert fl.scope == "scope_1"
    assert f2.scope == "scope_1"
    # And it serializes onto the line dict.
    assert fl.as_dict()["scope"] == "scope_1"


def test_scope2_purchased_power():
    # 1000 MWh x 400 kg CO2/MWh = 400,000 kg = 400 t CO2, all in Scope 2.
    line = scope2_purchased_power("GRID-1", 1000, 400.0)
    assert line.scope == "scope_2"
    assert line.source_type == "purchased_power"
    assert approx(line.co2_tonnes, 400.0)
    assert line.ch4_tonnes == 0.0
    assert line.tier == "Tier 2"  # published grid factor (not metered)
    assert scope2_purchased_power("GRID-2", 1000, 400.0, measured=True).tier == "Tier 3"


def test_scope3_use_of_sold_products():
    # 1,000,000 bbl sold x 0.43 t... factor in kg CO2e/bbl = 430 -> 430,000,000 kg = 430,000 t
    line = scope3_category("SOLD-1", "use_of_sold_products",
                           activity_value=1_000_000, emission_factor=430.0, unit="bbl")
    assert line.scope == "scope_3"
    assert line.source_type == "scope3_use_of_sold_products"
    assert approx(line.co2_tonnes, 430_000.0)
    assert line.activity["ghg_protocol_category"] == 11
    # Unknown categories are rejected (not silently accepted).
    try:
        scope3_category("X", "not_a_category", 1, 1, "unit")
        raise AssertionError("expected ValueError for unknown category")
    except ValueError:
        pass


def test_scope_summary():
    s1 = fugitive_tier2("AREA-1", {"valve": 100}, 8760)   # 3.942 t CH4
    s2 = scope2_purchased_power("GRID-1", 1000, 400.0)    # 400 t CO2
    s3 = scope3_category("SOLD-1", "use_of_sold_products",
                         activity_value=1_000, emission_factor=430.0, unit="bbl")  # 430 t
    inv = build_inventory("FAC-1", "2026-Q3", [s1, s2, s3], gwp_set="AR6")
    ss = inv.scope_summary()
    assert set(ss) == {"scope_1", "scope_2", "scope_3"}
    assert approx(ss["scope_1"], 3.942 * 29.8, tol=1e-2)
    assert approx(ss["scope_2"], 400.0)
    assert approx(ss["scope_3"], 430.0)
    # Scopes partition the inventory: they sum to the CO2e total.
    assert approx(sum(ss.values()), inv.totals()["co2e_tonnes"], tol=1e-2)


def _sample_multiscope_inventory():
    s1 = fugitive_tier2("AREA-1", {"valve": 100}, 8760)               # scope 1, Tier 2
    s1b = fugitive_tier3("AREA-2", [0.2], 8760)                       # scope 1, Tier 3
    s2 = scope2_purchased_power("GRID-1", 1000, 400.0)                # scope 2
    s3 = scope3_category("SOLD-1", "use_of_sold_products",
                         activity_value=1_000, emission_factor=430.0, unit="bbl")  # scope 3
    return build_inventory("FAC-1", "2026-Q3", [s1, s1b, s2, s3], gwp_set="AR6")


def test_build_report_registry_dispatches_all_frameworks():
    inv = _sample_multiscope_inventory()
    meta = dict(operator="Acme E&P", asset="OML-XX")
    for framework in ("ghgemp", "ogmp2", "csrd", "iso14064"):
        rep = build_report(framework, inv, **meta)
        assert isinstance(rep, dict)
        assert rep["audit_sha256"]
    # alias + unknown handling
    assert build_report("NUPRC", inv, **meta)["report_type"].startswith("GHG")
    try:
        build_report("not_a_framework", inv, **meta)
        raise AssertionError("expected ValueError for unknown framework")
    except ValueError:
        pass


def test_ogmp2_methane_intensity_target_flagging():
    # HI: 1.0 t CH4 over 100 t throughput = 1.0% (> 0.2% target -> above)
    # LO: 0.1 t CH4 over 1000 t throughput = 0.01% (< 0.2% target -> at/below)
    hi = fugitive_tier3("HI", [1.0], 1000)   # 1.0*1000/1000 = 1.0 t
    lo = fugitive_tier3("LO", [0.1], 1000)   # 0.1 t
    inv = build_inventory("FAC-1", "2026-Q3", [hi, lo], gwp_set="AR6")
    rep = build_ogmp2_report(
        inv, operator="Acme E&P", asset="OML-XX",
        gas_throughput_tonnes=1100,
        source_throughput_tonnes={"HI": 100, "LO": 1000},
    )
    by_id = {s["source_id"]: s for s in rep["sources"]}
    assert approx(by_id["HI"]["methane_intensity_pct"], 1.0)
    assert by_id["HI"]["target_flag"] == "above_target"
    assert approx(by_id["LO"]["methane_intensity_pct"], 0.01)
    assert by_id["LO"]["target_flag"] == "at_or_below_target"
    # both sources are measured (Tier 3) -> OGMP Level 4, measured factor split 100%
    assert by_id["HI"]["ogmp_level"] == 4
    assert rep["factor_basis_split"]["measured_pct_of_ch4"] == 100.0
    assert rep["target_methane_intensity_pct"] == 0.2


def test_ogmp2_missing_throughput_is_honest():
    line = fugitive_tier3("X", [0.5], 8760)
    inv = build_inventory("FAC-1", "2026-Q3", [line], gwp_set="AR6")
    rep = build_ogmp2_report(inv, operator="A", asset="B")  # no throughput supplied
    assert rep["sources"][0]["methane_intensity_pct"] is None
    assert rep["sources"][0]["target_flag"] == "throughput_not_provided"
    assert rep["site_level"]["methane_intensity_pct"] is None


def test_csrd_scopes_reconcile_to_totals():
    inv = _sample_multiscope_inventory()
    rep = build_csrd_report(inv, operator="Acme E&P", asset="OML-XX",
                            net_revenue=1_000_000, production_boe=500_000)
    e16 = rep["gross_ghg_emissions_e1_6"]
    ss = inv.scope_summary()
    assert e16["scope_1_co2e_tonnes"] == ss["scope_1"]
    assert e16["scope_2_location_based_co2e_tonnes"] == ss["scope_2"]
    assert e16["scope_3_co2e_tonnes"] == ss["scope_3"]
    assert approx(e16["total_co2e_tonnes"], inv.totals()["co2e_tonnes"], tol=1e-2)
    assert "use_of_sold_products" in e16["scope_3_by_category"]
    assert rep["ghg_intensity_e1_6"]["co2e_tonnes_per_boe"] is not None


def test_iso14064_categories_partition_inventory():
    inv = _sample_multiscope_inventory()
    rep = build_iso14064_report(inv, operator="Acme E&P", asset="OML-XX")
    cats = {c["iso_category"]: c for c in rep["categories"]}
    assert 1 in cats and 2 in cats and 5 in cats  # scope1, scope2, use-of-sold-products
    # Categories sum to the inventory CO2e total.
    cat_sum = sum(c["co2e_tonnes"] for c in rep["categories"])
    assert approx(cat_sum, inv.totals()["co2e_tonnes"], tol=1e-2)
    # use_of_sold_products lands in ISO Category 5
    assert any(s["source_type"] == "scope3_use_of_sold_products" for s in cats[5]["sources"])


def test_bounding_box_and_asset_coords():
    bbox = bounding_box_for_point(5.0, 6.0, radius_km=10.0)
    assert bbox.min_lat < 5.0 < bbox.max_lat
    assert bbox.min_lon < 6.0 < bbox.max_lon
    # Asset coords pulled from A9 attributes; missing -> None (caller asks for them).
    assert asset_coordinates({"latitude": 5.0, "longitude": 6.0}) == (5.0, 6.0)
    assert asset_coordinates({"name": "no coords here"}) is None
    assert asset_bounding_box({"name": "no coords here"}) is None
    assert asset_bounding_box({"lat": 5.0, "lon": 6.0}) is not None


def test_reconcile_flaring_observed_exceeds_reported_flags():
    # Reported 1,000,000 scf; satellite observed 2,000,000 scf -> +100% -> flagged.
    line = flaring("FL-1", 1_000_000, {"CH4": 1.0}, combustion_efficiency=0.98)
    observations = [
        {"detection_date": "2026-01-05", "flared_volume_scf": 1_200_000},
        {"detection_date": "2026-01-18", "flared_volume_scf": 800_000},
    ]
    res = reconcile_flaring(line, observations)
    assert res["reconciliation_available"] is True
    assert approx(res["reported_flared_scf"], 1_000_000)
    assert approx(res["observed_flared_scf"], 2_000_000)
    assert approx(res["variance_pct"], 100.0)
    assert res["observed_exceeds_reported"] is True


def test_reconcile_flaring_unavailable_is_honest():
    line = flaring("FL-1", 1_000_000, {"CH4": 1.0}, combustion_efficiency=0.98)
    unavailable = ProviderResult(
        provider="viirs_noaa_flaring", available=False, observations=[],
        unavailable_reason="VIIRS flaring source not configured.",
    )
    res = reconcile_flaring(line, unavailable)
    assert res["reconciliation_available"] is False
    assert res["observed_flared_scf"] is None
    assert res["variance_pct"] is None
    assert res["observed_exceeds_reported"] is False
    assert any("unavailable" in n.lower() for n in res["notes"])


def test_reconcile_flaring_zero_detections_is_observed_zero():
    line = flaring("FL-1", 1_000_000, {"CH4": 1.0}, combustion_efficiency=0.98)
    res = reconcile_flaring(line, [])  # covered window, nothing detected
    assert res["reconciliation_available"] is True
    assert res["observed_flared_scf"] == 0.0
    assert approx(res["variance_pct"], -100.0)
    assert res["observed_exceeds_reported"] is False


def test_satellite_flaring_provider_parses_mocked_http_response():
    import httpx

    def handler(request):
        return httpx.Response(200, json={"detections": [
            {"date": "2026-01-05", "latitude": 5.1, "longitude": 6.2,
             "rh_mw": 12.5, "flared_volume_scf": 1_200_000},
            {"date": "2026-01-18", "latitude": 5.0, "longitude": 6.1,
             "flared_volume_m3": 20_000},  # m3 -> scf conversion exercised
        ]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = SatelliteFlaringProvider(http_client=client)
    assert provider.available() is True
    req = ObservationRequest(
        bbox=bounding_box_for_point(5.0, 6.0, 10.0),
        date_range=DateRange("2026-01-01", "2026-01-31"),
    )
    result = provider.fetch(req)
    assert result.available is True
    assert result.provider == "viirs_noaa_flaring"
    assert len(result.observations) == 2
    first = result.observations[0]
    assert {"detection_date", "lat", "lon", "radiant_heat_mw",
            "flared_volume_scf", "source"}.issubset(first)
    assert approx(first["flared_volume_scf"], 1_200_000)
    # second detection converted from 20,000 m3 -> ~706,294 scf
    assert approx(result.observations[1]["flared_volume_scf"], 20_000 * 35.3147, tol=1e-4)


def test_satellite_flaring_provider_unconfigured_reports_unavailable():
    provider = SatelliteFlaringProvider(endpoint="")  # not configured, no client
    assert provider.available() is False
    req = ObservationRequest(
        bbox=bounding_box_for_point(5.0, 6.0, 10.0),
        date_range=DateRange("2026-01-01", "2026-01-31"),
    )
    result = provider.fetch(req)
    assert result.available is False
    assert result.observations == []
    assert "not configured" in (result.unavailable_reason or "")


def test_capital_recovery_factor():
    # CRF(10%, 10y) = 0.1*1.1^10/(1.1^10-1) ~ 0.16275
    assert approx(capital_recovery_factor(0.10, 10), 0.16275, tol=1e-3)
    assert approx(capital_recovery_factor(0.0, 5), 0.2)  # zero-rate -> straight-line


def test_abatement_reduces_modeled_emissions():
    v = venting("V-1", 10_000_000, {"CH4": 1.0})   # large CH4 source
    c = combustion("GT-1", 1_000_000, co2_kg_per_scf=0.05)  # 50 t CO2
    inv = build_inventory("FAC-1", "2026", [v, c], gwp_set="AR6")
    baseline = inv.totals()["co2e_tonnes"]
    res = model_abatement(inv, [
        {"measure_id": "vapor_recovery_unit", "target_source_ids": ["V-1"],
         "reduction_pct": 0.95},
    ])
    assert approx(res["baseline_co2e_tonnes"], baseline)
    # projected = baseline - avoided
    assert approx(res["projected_co2e_tonnes"], baseline - res["total_co2e_avoided_tonnes"], tol=1e-2)
    # the venting line's methane is reduced 95% in the projected inventory
    proj_v = next(l for l in res["projected_inventory"]["lines"] if l["source_id"] == "V-1")
    assert approx(proj_v["ch4_tonnes"], v.ch4_tonnes * 0.05, tol=1e-2)
    assert "ESTIMATE" in res["cost_estimate_disclaimer"]


def test_abatement_mac_ordering_and_net_negative_flag():
    v = venting("V-1", 10_000_000, {"CH4": 1.0})   # ~191.8 t CH4 -> big CO2e
    c = combustion("GT-1", 1_000_000, co2_kg_per_scf=0.05)
    inv = build_inventory("FAC-1", "2026", [v, c], gwp_set="AR6")
    res = model_abatement(inv, [
        # VRU: cheap + recovers a lot of valuable gas -> net-negative MAC
        {"measure_id": "vapor_recovery_unit", "target_source_ids": ["V-1"],
         "reduction_pct": 0.95, "capex_usd": 10_000, "opex_usd_per_yr": 1_000,
         "gas_price_usd_per_mcf": 5.0, "discount_rate": 0.10, "lifetime_years": 10},
        # Electrification: large capex, no gas recovery -> clearly positive MAC
        {"measure_id": "electrification", "target_source_ids": ["GT-1"],
         "reduction_pct": 0.90, "capex_usd": 500_000, "opex_usd_per_yr": 20_000},
    ])
    by_id = {m["measure_id"]: m for m in res["measures"]}
    assert by_id["vapor_recovery_unit"]["net_negative_cost"] is True
    assert by_id["vapor_recovery_unit"]["marginal_abatement_cost_usd_per_tco2e"] < 0
    assert by_id["electrification"]["net_negative_cost"] is False
    assert by_id["electrification"]["marginal_abatement_cost_usd_per_tco2e"] > 0
    # MAC curve sorted ascending: net-negative VRU first
    curve = res["mac_curve"]
    assert curve[0]["measure_id"] == "vapor_recovery_unit"
    assert curve[0]["marginal_abatement_cost_usd_per_tco2e"] <= curve[1]["marginal_abatement_cost_usd_per_tco2e"]
    # cumulative avoided is monotonic and reaches the total
    assert approx(curve[-1]["cumulative_co2e_avoided_tonnes"], res["total_co2e_avoided_tonnes"], tol=1e-2)


def test_abatement_catalog_and_unknown_measure():
    cat = abatement_catalog()
    ids = {m["measure_id"] for m in cat}
    assert {"vapor_recovery_unit", "flare_gas_recovery", "ldar_program", "electrification"}.issubset(ids)
    inv = build_inventory("FAC-1", "2026", [venting("V-1", 1000, {"CH4": 1.0})], gwp_set="AR6")
    try:
        model_abatement(inv, [{"measure_id": "teleport_the_methane_away"}])
        raise AssertionError("expected ValueError for unknown measure")
    except ValueError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
