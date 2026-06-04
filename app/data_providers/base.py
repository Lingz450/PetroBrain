"""
DataProvider interface - the external-data abstraction from the intelligence
strategy. Every external source PetroBrain reasons over (satellite flaring,
satellite methane, and future market/benchmark feeds) implements this same
contract, so the rest of the system can consume independent observations
uniformly and - critically - can tell when a source has nothing to say.

HONESTY CONTRACT: a provider must never invent an observation. When a source is
not configured, not reachable, or has no data for the requested area/period, it
returns a ProviderResult with ``available=False`` (or an empty observation list
for a genuine "covered the area, saw nothing") and an explicit reason. Downstream
code surfaces that rather than filling the gap.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

# Earth geometry constants for the small-box approximation used to turn a point
# (a facility's lat/lon) into a bounding box for a satellite query.
_KM_PER_DEG_LAT = 110.574
_KM_PER_DEG_LON_EQUATOR = 111.320


@dataclass
class GeoBoundingBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class DateRange:
    start: str  # ISO date, e.g. "2026-01-01"
    end: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class ObservationRequest:
    bbox: GeoBoundingBox
    date_range: DateRange
    params: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "bbox": self.bbox.as_dict(),
            "date_range": self.date_range.as_dict(),
            "params": self.params,
        }


@dataclass
class ProviderResult:
    provider: str
    available: bool
    observations: list[dict[str, Any]] = field(default_factory=list)
    source_url: str | None = None
    unavailable_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DataProvider(ABC):
    """Common contract for every external observation source."""

    name: str = "data_provider"
    source_url: str | None = None

    @abstractmethod
    def available(self) -> bool:
        """True if the source is configured and can be queried."""

    @abstractmethod
    def fetch(self, request: ObservationRequest) -> ProviderResult:
        """Return observations for the requested bounding box + date range."""


def bounding_box_for_point(lat: float, lon: float, radius_km: float = 10.0) -> GeoBoundingBox:
    """Square-ish bounding box of +/- radius_km around a point.

    Uses a local flat-earth approximation - fine for the small (single-facility)
    boxes we query satellite data with. Latitude is clamped to valid range; the
    longitude delta widens with latitude (cos term).
    """
    dlat = radius_km / _KM_PER_DEG_LAT
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    dlon = radius_km / (_KM_PER_DEG_LON_EQUATOR * cos_lat)
    return GeoBoundingBox(
        min_lat=max(lat - dlat, -90.0),
        min_lon=lon - dlon,
        max_lat=min(lat + dlat, 90.0),
        max_lon=lon + dlon,
    )


def asset_coordinates(attributes: dict[str, Any] | None) -> tuple[float, float] | None:
    """Extract (lat, lon) from an A9 asset's ``attributes`` dict, if present.

    Accepts common key spellings. Returns None when coordinates are absent so the
    caller can ask the operator for them rather than guessing a location.
    """
    if not isinstance(attributes, dict):
        return None
    lat = _first_number(attributes, ("lat", "latitude"))
    lon = _first_number(attributes, ("lon", "lng", "long", "longitude"))
    if lat is None or lon is None:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


def asset_bounding_box(attributes: dict[str, Any] | None,
                       radius_km: float = 10.0) -> GeoBoundingBox | None:
    """Bounding box around an asset's coordinates, or None if coords are unknown."""
    coords = asset_coordinates(attributes)
    if coords is None:
        return None
    return bounding_box_for_point(coords[0], coords[1], radius_km)


def _first_number(d: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                return None
    return None
