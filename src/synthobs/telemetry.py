"""Solar Wavefield Oscillator — live telemetry ingestion (fail-closed).

The SWO is the digital bridge to the magnetosphere. It consumes **current, active**
space-weather streams (10.7 cm solar radio flux + active sunspot count) and refuses
to run on anything else: the system completely bans historical databases, static
baseline logs, and placeholder constants. Falling back to artificial averages causes
phase drift, so on any failure — connectivity drop, non-200, malformed payload,
non-positive flux/spots, or a stale timestamp — ingestion raises
:class:`TelemetryUnavailable` and the engine holds its last verified vector.

This module performs real HTTP (stdlib ``urllib``) so it is exercised in tests
against a local ``pytest-httpserver`` instance — no mocks. The native FractiSynth C
plugin hits the same NOAA SWPC endpoints via a libcurl background thread.

NOAA SWPC reference endpoints (consumed by the C telemetry thread):
  - F10.7 flux:  https://services.swpc.noaa.gov/json/f107_cm_flux.json
  - Sunspots:    https://services.swpc.noaa.gov/json/sunspot_report.json
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

__all__ = [
    "SolarTelemetry",
    "TelemetryUnavailable",
    "parse_noaa_f107_flux",
    "telemetry_from_payload",
    "fetch_live_telemetry",
    "DEFAULT_MAX_AGE_S",
    "SolarWind",
    "parse_noaa_solar_wind",
    "fetch_live_solar_wind",
    "NOAA_SOLAR_WIND_URL",
]

# NOAA SWPC real-time solar-wind plasma feed (the EGS gateway's phase driver).
NOAA_SOLAR_WIND_URL: str = (
    "https://services.swpc.noaa.gov/products/solar-wind/plasma-2-hour.json"
)

# Telemetry older than three hours is "stale" — the sun's disk has materially
# rotated and the vector can no longer be trusted as "the present moment".
DEFAULT_MAX_AGE_S: float = 3 * 60 * 60


class TelemetryUnavailable(RuntimeError):
    """Raised whenever live, valid telemetry cannot be obtained. Never swallowed
    into a default — the caller must enter the Hold State."""


@dataclass(frozen=True)
class SolarTelemetry:
    """One verified live reading of the solar wavefield."""

    flux: float
    """Current 10.7 cm solar radio flux (F10.7), solar flux units."""
    sunspots: int
    """Count of active sunspot regions on the disk."""
    source: str
    """Provenance of this reading (URL or 'override')."""
    observed_at: datetime
    """UTC timestamp the reading was observed."""
    regions: tuple[str, ...] = ()
    """Active region designators, e.g. ('AR4465', 'AR4464')."""

    def age_seconds(self, now: datetime) -> float:
        return (now - self.observed_at).total_seconds()


def _parse_time_tag(raw: Any) -> datetime:
    if not isinstance(raw, str) or not raw:
        raise TelemetryUnavailable(f"missing/invalid time_tag: {raw!r}")
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:  # malformed timestamp → fail closed
        raise TelemetryUnavailable(f"unparseable time_tag: {raw!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_noaa_f107_flux(data: Any) -> tuple[float, datetime]:
    """Extract the latest F10.7 flux + time from NOAA's real array payload.

    NOAA returns ``[{"time_tag": "...", "flux": 130.4}, ...]`` ordered oldest→newest.
    Returns the most recent ``(flux, observed_at)``; fails closed on empty/invalid
    data or non-positive flux.
    """
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise TelemetryUnavailable("F10.7 payload is not valid JSON") from exc
    if not isinstance(data, list) or not data:
        raise TelemetryUnavailable("F10.7 payload is empty or not a list")
    latest = data[-1]
    if not isinstance(latest, dict) or "flux" not in latest:
        raise TelemetryUnavailable(f"F10.7 record missing flux: {latest!r}")
    try:
        flux = float(latest["flux"])
    except (TypeError, ValueError) as exc:
        raise TelemetryUnavailable(f"F10.7 flux not numeric: {latest!r}") from exc
    if flux <= 0.0:
        raise TelemetryUnavailable(f"F10.7 flux must be positive, got {flux}")
    observed = _parse_time_tag(latest.get("time_tag"))
    return flux, observed


def telemetry_from_payload(
    payload: Any,
    *,
    source: str = "payload",
    max_age_s: float = DEFAULT_MAX_AGE_S,
    now: datetime | None = None,
) -> SolarTelemetry:
    """Validate a combined SWO telemetry payload, failing closed.

    Expected shape (the SynthOBS SWO contract)::

        {"flux": 130.4, "sunspots": 3, "time_tag": "2026-06-10T12:00:00Z",
         "regions": ["AR4465", "AR4464"]}

    Rejects (raises :class:`TelemetryUnavailable`) when: not a dict; flux/sunspots
    missing or non-numeric; ``flux <= 0``; ``sunspots <= 0``; timestamp missing/
    malformed; or the reading is older than ``max_age_s`` (ISC-12..16, ISC-18).
    """
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise TelemetryUnavailable("telemetry payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise TelemetryUnavailable(f"telemetry payload must be an object, got {type(payload).__name__}")

    if "flux" not in payload or "sunspots" not in payload:
        raise TelemetryUnavailable("telemetry payload missing flux/sunspots")
    try:
        flux = float(payload["flux"])
        sunspots = int(payload["sunspots"])
    except (TypeError, ValueError) as exc:
        raise TelemetryUnavailable(f"telemetry flux/sunspots not numeric: {payload!r}") from exc

    # Fail-closed enforcement — block stale, default, or zeroed indicators.
    if flux <= 0.0:
        raise TelemetryUnavailable(f"flux must be positive, got {flux}")
    if sunspots <= 0:
        raise TelemetryUnavailable(f"sunspots must be positive, got {sunspots}")

    observed = _parse_time_tag(payload.get("time_tag"))
    now = now or datetime.now(timezone.utc)
    age = (now - observed).total_seconds()
    if age > max_age_s:
        raise TelemetryUnavailable(f"telemetry is stale: age {age:.0f}s > max {max_age_s:.0f}s")
    if age < -max_age_s:
        raise TelemetryUnavailable(f"telemetry timestamp is in the future by {-age:.0f}s")

    regions_raw = payload.get("regions", [])
    regions = tuple(str(r) for r in regions_raw) if isinstance(regions_raw, (list, tuple)) else ()
    return SolarTelemetry(flux=flux, sunspots=sunspots, source=source, observed_at=observed, regions=regions)


@dataclass(frozen=True)
class SolarWind:
    """One verified live solar-wind plasma reading — the gateway phase driver."""

    speed_kms: float
    """Bulk solar-wind speed (km/s)."""
    density: float | None
    """Proton density (p/cm³), if present in the feed."""
    source: str
    """Provenance of this reading (URL or 'override')."""
    observed_at: datetime
    """UTC timestamp the reading was observed."""

    def age_seconds(self, now: datetime) -> float:
        return (now - self.observed_at).total_seconds()


def parse_noaa_solar_wind(
    data: Any,
    *,
    source: str = "payload",
    max_age_s: float = DEFAULT_MAX_AGE_S,
    now: datetime | None = None,
) -> SolarWind:
    """Validate NOAA's ``plasma-2-hour.json`` feed, failing closed.

    The feed is an array of arrays: row 0 is the header
    ``["time_tag", "density", "speed", "temperature"]`` and subsequent rows are
    data; the *last* data row is the present reading. Raises
    :class:`TelemetryUnavailable` when: not a non-empty array of rows; the speed
    column is missing/non-numeric; ``speed <= 0``; the timestamp is missing/
    malformed; or the reading is older than ``max_age_s``.
    """
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise TelemetryUnavailable("solar-wind payload is not valid JSON") from exc
    if not isinstance(data, list) or len(data) < 2:
        raise TelemetryUnavailable("solar-wind payload must be a header + data rows")

    header = data[0]
    if not isinstance(header, list):
        raise TelemetryUnavailable("solar-wind header row malformed")
    try:
        speed_col = header.index("speed")
        time_col = header.index("time_tag")
    except ValueError as exc:
        raise TelemetryUnavailable(f"solar-wind header missing columns: {header!r}") from exc
    density_col = header.index("density") if "density" in header else None

    last = data[-1]
    if not isinstance(last, list) or len(last) <= speed_col:
        raise TelemetryUnavailable(f"solar-wind data row malformed: {last!r}")

    try:
        speed = float(last[speed_col])
    except (TypeError, ValueError) as exc:
        raise TelemetryUnavailable(f"solar-wind speed not numeric: {last!r}") from exc
    if speed <= 0.0:
        raise TelemetryUnavailable(f"solar-wind speed must be positive, got {speed}")

    density: float | None = None
    if density_col is not None and len(last) > density_col:
        try:
            density = float(last[density_col])
        except (TypeError, ValueError):
            density = None

    observed = _parse_time_tag(last[time_col] if len(last) > time_col else None)
    now = now or datetime.now(timezone.utc)
    age = (now - observed).total_seconds()
    if age > max_age_s:
        raise TelemetryUnavailable(f"solar-wind is stale: age {age:.0f}s > max {max_age_s:.0f}s")
    if age < -max_age_s:
        raise TelemetryUnavailable(f"solar-wind timestamp is in the future by {-age:.0f}s")

    return SolarWind(speed_kms=speed, density=density, source=source, observed_at=observed)


def _http_get(url: str, *, timeout: float, opener: Callable[..., Any] | None) -> tuple[int, bytes]:
    get = opener or urllib.request.urlopen
    try:
        with get(url, timeout=timeout) as resp:  # type: ignore[call-arg]
            status = getattr(resp, "status", None) or resp.getcode()
            body = resp.read()
    except urllib.error.HTTPError as exc:  # non-2xx
        raise TelemetryUnavailable(f"telemetry HTTP {exc.code} from {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:  # connectivity drop
        raise TelemetryUnavailable(f"telemetry connection failed for {url}: {exc}") from exc
    if status != 200:
        raise TelemetryUnavailable(f"telemetry non-200 ({status}) from {url}")
    return status, body


def fetch_live_telemetry(
    url: str,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    timeout: float = 10.0,
    now: datetime | None = None,
    opener: Callable[..., Any] | None = None,
) -> SolarTelemetry:
    """Fetch and validate live SWO telemetry from ``url`` (fail-closed).

    Performs a real HTTP GET; on any failure raises :class:`TelemetryUnavailable`
    so the engine can hold its last verified vector. ``opener`` is injectable only
    to point tests at a local server; production passes a real URL (ISC-17).
    """
    _status, body = _http_get(url, timeout=timeout, opener=opener)
    return telemetry_from_payload(body, source=url, max_age_s=max_age_s, now=now)


def fetch_live_solar_wind(
    url: str = NOAA_SOLAR_WIND_URL,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    timeout: float = 10.0,
    now: datetime | None = None,
    opener: Callable[..., Any] | None = None,
) -> SolarWind:
    """Fetch and validate live NOAA solar-wind plasma (fail-closed).

    Performs a real HTTP GET against the SWPC plasma feed; on any failure raises
    :class:`TelemetryUnavailable` so the gateway holds its last verified lock.
    ``opener`` is injectable only to point tests at a local server (ISC-17 twin).
    """
    _status, body = _http_get(url, timeout=timeout, opener=opener)
    return parse_noaa_solar_wind(body, source=url, max_age_s=max_age_s, now=now)
