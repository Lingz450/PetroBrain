"""
Satellite providers: independent, public, license-clean observation of flaring
and methane that we cross-reference against the operator's REPORTED numbers.

  SatelliteFlaringProvider   - VIIRS Nightfire flaring detections (NOAA / Earth
                               Observation Group, Colorado School of Mines). Public.
  Sentinel5PMethaneProvider  - Sentinel-5P / TROPOMI methane (CH4) column data,
                               public via the Copernicus programme.

The actual HTTP retrieval is wired behind the DataProvider interface. The real
product endpoints are recorded as constants with TODOs to confirm the exact API
path/parameters and any (free) registration step; until an endpoint is configured
(PB_VIIRS_FLARING_ENDPOINT / PB_TROPOMI_METHANE_ENDPOINT) the provider reports
itself unavailable rather than fabricating detections. No secrets are hardcoded.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings

from .base import DataProvider, ObservationRequest, ProviderResult

# 1 cubic metre of gas = 35.3147 standard cubic feet (volume comparison unit).
SCF_PER_M3 = 35.3147
SCF_PER_BCM = 1e9 * SCF_PER_M3
DEFAULT_TIMEOUT_S = 15.0


class _HttpProvider(DataProvider):
    """Shared HTTP plumbing. Inject ``http_client`` (e.g. an httpx.Client with a
    MockTransport) in tests; in production a per-call client is used."""

    def __init__(self, *, endpoint: str | None = None,
                 http_client: httpx.Client | None = None,
                 timeout: float = DEFAULT_TIMEOUT_S) -> None:
        self._endpoint = (endpoint or "").strip()
        self._client = http_client
        self._timeout = timeout

    def available(self) -> bool:
        # Configured by endpoint, or explicitly wired with a client (tests).
        return bool(self._endpoint) or self._client is not None

    def _get(self, params: dict[str, Any]) -> Any:
        url = self._endpoint or (self.source_url or "")
        if self._client is not None:
            resp = self._client.get(url, params=params)
        else:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


class SatelliteFlaringProvider(_HttpProvider):
    """VIIRS Nightfire flaring detections (NOAA / EOG, Colorado School of Mines)."""

    name = "viirs_noaa_flaring"
    # TODO: confirm the exact public product endpoint + query parameters. The VIIRS
    # Nightfire / global gas flaring data is published by the Earth Observation Group:
    #   https://eogdata.mines.edu/products/vnf/
    # (annual flared-volume estimates and nightly detections). Free registration may
    # be required; the access token MUST come from configuration, never hardcoded.
    source_url = "https://eogdata.mines.edu/products/vnf/"

    def __init__(self, *, endpoint: str | None = None,
                 http_client: httpx.Client | None = None,
                 timeout: float = DEFAULT_TIMEOUT_S) -> None:
        if endpoint is None and http_client is None:
            endpoint = get_settings().viirs_flaring_endpoint
        super().__init__(endpoint=endpoint, http_client=http_client, timeout=timeout)

    def fetch(self, request: ObservationRequest) -> ProviderResult:
        meta = {"bbox": request.bbox.as_dict(), "date_range": request.date_range.as_dict()}
        if not self.available():
            return ProviderResult(
                provider=self.name, available=False, observations=[],
                source_url=self.source_url, metadata=meta,
                unavailable_reason=(
                    "VIIRS flaring source not configured (set PB_VIIRS_FLARING_ENDPOINT). "
                    "No detections fabricated."
                ),
            )
        params = {
            "min_lat": request.bbox.min_lat, "min_lon": request.bbox.min_lon,
            "max_lat": request.bbox.max_lat, "max_lon": request.bbox.max_lon,
            "start": request.date_range.start, "end": request.date_range.end,
            **request.params,
        }
        try:
            data = self._get(params)
        except httpx.HTTPError as exc:
            return ProviderResult(
                provider=self.name, available=False, observations=[],
                source_url=self.source_url, metadata=meta,
                unavailable_reason=f"VIIRS flaring request failed: {exc}",
            )
        detections = data.get("detections") if isinstance(data, dict) else data
        if not isinstance(detections, list):
            detections = []
        observations = [self._parse_detection(d) for d in detections if isinstance(d, dict)]
        meta["n_detections"] = len(observations)
        return ProviderResult(
            provider=self.name, available=True, observations=observations,
            source_url=self.source_url, metadata=meta,
        )

    def _parse_detection(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "detection_date": d.get("detection_date") or d.get("date"),
            "lat": _num(d.get("lat") if d.get("lat") is not None else d.get("latitude")),
            "lon": _num(d.get("lon") if d.get("lon") is not None else d.get("longitude")),
            "radiant_heat_mw": _num(d.get("radiant_heat_mw") or d.get("rh_mw")),
            "temperature_k": _num(d.get("temperature_k") or d.get("temp_k")),
            "flared_volume_scf": _flared_scf(d),
            "source": "VIIRS Nightfire (NOAA/EOG)",
        }


class Sentinel5PMethaneProvider(_HttpProvider):
    """Sentinel-5P / TROPOMI methane (CH4) column observations (Copernicus)."""

    name = "sentinel5p_tropomi_methane"
    # TODO: confirm the exact public access path. Sentinel-5P L2/L3 CH4 is available
    # via the Copernicus Data Space Ecosystem / Sentinel Hub statistical API and via
    # Google Earth Engine (COPERNICUS/S5P/OFFL/L3_CH4). Free auth via configuration.
    source_url = "https://dataspace.copernicus.eu/"

    def __init__(self, *, endpoint: str | None = None,
                 http_client: httpx.Client | None = None,
                 timeout: float = DEFAULT_TIMEOUT_S) -> None:
        if endpoint is None and http_client is None:
            endpoint = get_settings().tropomi_methane_endpoint
        super().__init__(endpoint=endpoint, http_client=http_client, timeout=timeout)

    def fetch(self, request: ObservationRequest) -> ProviderResult:
        meta = {"bbox": request.bbox.as_dict(), "date_range": request.date_range.as_dict()}
        if not self.available():
            return ProviderResult(
                provider=self.name, available=False, observations=[],
                source_url=self.source_url, metadata=meta,
                unavailable_reason=(
                    "Sentinel-5P methane source not configured (set "
                    "PB_TROPOMI_METHANE_ENDPOINT). No observations fabricated."
                ),
            )
        params = {
            "min_lat": request.bbox.min_lat, "min_lon": request.bbox.min_lon,
            "max_lat": request.bbox.max_lat, "max_lon": request.bbox.max_lon,
            "start": request.date_range.start, "end": request.date_range.end,
            **request.params,
        }
        try:
            data = self._get(params)
        except httpx.HTTPError as exc:
            return ProviderResult(
                provider=self.name, available=False, observations=[],
                source_url=self.source_url, metadata=meta,
                unavailable_reason=f"Sentinel-5P methane request failed: {exc}",
            )
        rows = data.get("observations") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            rows = []
        observations = [self._parse_row(r) for r in rows if isinstance(r, dict)]
        meta["n_observations"] = len(observations)
        meta["note"] = (
            "TROPOMI provides methane COLUMN concentration, not an emission rate. "
            "Quantitative source attribution requires atmospheric inversion and is "
            "out of scope here; use this as a corroborating signal, not a mass total."
        )
        return ProviderResult(
            provider=self.name, available=True, observations=observations,
            source_url=self.source_url, metadata=meta,
        )

    def _parse_row(self, r: dict[str, Any]) -> dict[str, Any]:
        return {
            "observation_date": r.get("observation_date") or r.get("date"),
            "lat": _num(r.get("lat") if r.get("lat") is not None else r.get("latitude")),
            "lon": _num(r.get("lon") if r.get("lon") is not None else r.get("longitude")),
            "ch4_column_mol_m2": _num(r.get("ch4_column_mol_m2")),
            "xch4_ppb": _num(r.get("xch4_ppb")),
            "qa_value": _num(r.get("qa_value")),
            "source": "Sentinel-5P TROPOMI (Copernicus)",
        }


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flared_scf(d: dict[str, Any]) -> float | None:
    """Normalize a detection's flared volume to standard cubic feet, whatever unit
    the source reports it in. Returns None when no volume is derivable (e.g. only
    radiant heat is given) - we do not invent a volume."""
    if d.get("flared_volume_scf") is not None:
        return _num(d["flared_volume_scf"])
    if d.get("flared_volume_m3") is not None:
        v = _num(d["flared_volume_m3"])
        return v * SCF_PER_M3 if v is not None else None
    if d.get("flared_volume_bcm") is not None:
        v = _num(d["flared_volume_bcm"])
        return v * SCF_PER_BCM if v is not None else None
    return None
