"""
External data providers (the intelligence-strategy abstraction).

Every external observation source implements the DataProvider contract in
``base``. Today: independent satellite observation of flaring and methane,
cross-referenced against the operator's reported numbers.
"""
from .base import (
    DataProvider,
    DateRange,
    GeoBoundingBox,
    ObservationRequest,
    ProviderResult,
    asset_bounding_box,
    asset_coordinates,
    bounding_box_for_point,
)
from .satellite import Sentinel5PMethaneProvider, SatelliteFlaringProvider

__all__ = [
    "DataProvider",
    "ProviderResult",
    "ObservationRequest",
    "GeoBoundingBox",
    "DateRange",
    "bounding_box_for_point",
    "asset_coordinates",
    "asset_bounding_box",
    "SatelliteFlaringProvider",
    "Sentinel5PMethaneProvider",
]
