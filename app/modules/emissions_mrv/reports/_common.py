"""
Shared helpers for the framework report generators.

The SAME deterministic Inventory feeds every framework generator in this package
(NUPRC GHGEMP, OGMP 2.0, CSRD/ESRS E1, ISO 14064-1). None of them recompute
emissions - they only re-present the engine's numbers in each framework's shape.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def audit_sha256(payload: dict[str, Any]) -> str:
    """Tamper-evident SHA-256 over the substantive content of a report.

    Byte-identical to the original GHGEMP hash (sorted-key JSON, default utf-8),
    so moving the GHGEMP generator into this package does not change any existing
    audit hash.
    """
    blob = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()
