"""
Back-compat shim.

The GHGEMP generator moved into the multi-framework reports package
(app/modules/emissions_mrv/reports/ghgemp.py) in the A2 refactor. This module
re-exports the public names so existing imports keep working unchanged. Prefer
importing from `app.modules.emissions_mrv.reports` in new code.
"""
from __future__ import annotations

from .reports.ghgemp import build_ghgemp_report, build_mrv_readiness_summary

__all__ = ["build_ghgemp_report", "build_mrv_readiness_summary"]
