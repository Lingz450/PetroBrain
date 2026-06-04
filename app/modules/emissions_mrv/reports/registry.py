"""
Framework registry: one deterministic Inventory -> any supported framework report.

build_report(framework, inventory, **meta) dispatches by framework name. The
emission numbers are identical across frameworks (they come from the same
Inventory); only the presentation/structure differs.
"""
from __future__ import annotations

from typing import Any, Callable

from ..engine import Inventory
from .csrd import build_csrd_report
from .ghgemp import build_ghgemp_report
from .iso14064 import build_iso14064_report
from .ogmp2 import build_ogmp2_report

# Normalized framework name -> generator. Aliases included for ergonomics.
_GENERATORS: dict[str, Callable[..., dict[str, Any]]] = {
    "ghgemp": build_ghgemp_report,
    "nuprc": build_ghgemp_report,
    "ogmp2": build_ogmp2_report,
    "ogmp": build_ogmp2_report,
    "ogmp2.0": build_ogmp2_report,
    "csrd": build_csrd_report,
    "esrs": build_csrd_report,
    "esrse1": build_csrd_report,
    "iso14064": build_iso14064_report,
    "iso": build_iso14064_report,
    "iso14064-1": build_iso14064_report,
}

SUPPORTED_FRAMEWORKS = ("ghgemp", "ogmp2", "csrd", "iso14064")


def _normalize(framework: str) -> str:
    return framework.strip().lower().replace(" ", "").replace("_", "")


def build_report(framework: str, inventory: Inventory, **meta: Any) -> dict[str, Any]:
    """Build the named framework report from a single Inventory.

    `meta` carries framework-specific arguments (operator, asset are required by all;
    OGMP also takes throughput, CSRD takes revenue/production/targets, etc.).
    """
    generator = _GENERATORS.get(_normalize(framework))
    if generator is None:
        raise ValueError(
            f"unknown framework {framework!r}; supported: {', '.join(SUPPORTED_FRAMEWORKS)}"
        )
    return generator(inventory, **meta)
