"""
Emission factors, Global Warming Potentials, and gas-component properties.

IMPORTANT COMPLIANCE NOTE:
The GWP values and default emission factors below are industry/IPCC reference
values for engineering use. For a NUPRC submission they MUST be set to the values
in the *current gazetted* NUPRC guidance (Guidelines for Management of Fugitive
Methane and GHGs in Upstream Oil & Gas) and the IPCC tier the operator is on at the
time. This file is configuration, not doctrine - it is meant to be overridden per
tenant and per reporting period, with the source recorded for the audit trail.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Global Warming Potentials (100-year), by IPCC assessment report.
# Fossil methane in AR6 has a higher GWP than biogenic; oil & gas methane is fossil.
# ---------------------------------------------------------------------------
GWP_SETS = {
    "AR5": {"CO2": 1.0, "CH4": 28.0, "N2O": 265.0},
    "AR6": {"CO2": 1.0, "CH4": 29.8, "N2O": 273.0},   # CH4 = fossil methane GWP100
}
DEFAULT_GWP_SET = "AR6"

# ---------------------------------------------------------------------------
# Gas component properties: molecular weight (lb/lbmol) and carbon number.
# Used to convert flared/vented gas volumes to component masses and to do the
# carbon balance for flaring.
# ---------------------------------------------------------------------------
COMPONENT_PROPERTIES = {
    #            MW (lb/lbmol), carbon atoms
    "CH4":  {"mw": 16.043, "carbon": 1},
    "C2H6": {"mw": 30.070, "carbon": 2},
    "C3H8": {"mw": 44.097, "carbon": 3},
    "C4H10": {"mw": 58.123, "carbon": 4},
    "C5H12": {"mw": 72.150, "carbon": 5},
    "CO2":  {"mw": 44.010, "carbon": 1},   # passes through as CO2 (already oxidized)
    "N2":   {"mw": 28.013, "carbon": 0},   # inert
    "H2S":  {"mw": 34.081, "carbon": 0},
}

MW_CO2 = 44.010   # lb/lbmol
MW_CH4 = 16.043

# ---------------------------------------------------------------------------
# Tier 2 average fugitive emission factors (component-count method).
# Units: kg CH4 per component per HOUR (illustrative reference values, oil/gas
# service). Replace with the EF set mandated by NUPRC / API for the period.
# ---------------------------------------------------------------------------
TIER2_FUGITIVE_EF_KG_CH4_PER_COMPONENT_HR = {
    "valve": 0.0045,
    "connector": 0.0002,
    "flange": 0.00039,
    "open_ended_line": 0.0020,
    "pump_seal": 0.0029,
    "compressor_seal": 0.0089,
    "pressure_relief_valve": 0.0088,
    "other": 0.0020,
}

# Default flare combustion (destruction) efficiency if not measured.
DEFAULT_FLARE_COMBUSTION_EFFICIENCY = 0.98

# ---------------------------------------------------------------------------
# GHG-Protocol Scope-3 categories RELEVANT to an oil & gas operator.
# This is deliberately NOT the full generic 15-category list - it is the subset
# that matters for an upstream/midstream operator. The dominant line for O&G is
# category 11 (use of sold products = combustion of the hydrocarbons sold), which
# typically dwarfs Scope 1 + 2 combined.
#
# `ghg_protocol_category` is the official GHG-Protocol number so reports can map
# back to the standard. Scope-3 emission factors are supplied per reporting and
# are expressed as kg CO2e per activity unit (already CO2e - see engine).
# ---------------------------------------------------------------------------
OG_SCOPE3_CATEGORIES = {
    "purchased_goods_services": {
        "ghg_protocol_category": 1,
        "label": "Purchased goods & services",
    },
    "capital_goods": {
        "ghg_protocol_category": 2,
        "label": "Capital goods",
    },
    "fuel_and_energy_related": {
        "ghg_protocol_category": 3,
        "label": "Fuel- and energy-related activities (not in Scope 1/2)",
    },
    "upstream_transport": {
        "ghg_protocol_category": 4,
        "label": "Upstream transportation & distribution",
    },
    "waste": {
        "ghg_protocol_category": 5,
        "label": "Waste generated in operations",
    },
    "business_travel": {
        "ghg_protocol_category": 6,
        "label": "Business travel",
    },
    "downstream_transport": {
        "ghg_protocol_category": 9,
        "label": "Downstream transportation & distribution",
    },
    "processing_of_sold_products": {
        "ghg_protocol_category": 10,
        "label": "Processing of sold products",
    },
    "use_of_sold_products": {
        "ghg_protocol_category": 11,
        "label": "Use of sold products (combustion of sold hydrocarbons)",
    },
}
