"""
Multi-framework MRV report generators.

The engine is framework-agnostic: the SAME Inventory exports to every framework
below. Each generator returns a structured dict plus an audit SHA-256 over its
substantive content. None of them recompute emissions.
"""
from .csrd import build_csrd_report
from .ghgemp import build_ghgemp_report, build_mrv_readiness_summary
from .iso14064 import build_iso14064_report
from .ogmp2 import build_ogmp2_report
from .registry import SUPPORTED_FRAMEWORKS, build_report

__all__ = [
    "build_report",
    "SUPPORTED_FRAMEWORKS",
    "build_ghgemp_report",
    "build_mrv_readiness_summary",
    "build_ogmp2_report",
    "build_csrd_report",
    "build_iso14064_report",
]
