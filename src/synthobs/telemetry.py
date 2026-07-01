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
  - F10.7 flux:    https://services.swpc.noaa.gov/json/f107_cm_flux.json
  - Active regions: https://services.swpc.noaa.gov/json/solar_regions.json
  - Solar wind:    https://services.swpc.noaa.gov/products/solar-wind/plasma-2-hour.json
"""

from __future__ import annotations

import json
import math
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
    "parse_noaa_solar_regions",
    "NOAA_SOLAR_REGIONS_URL",
    "DEFAULT_REGIONS_MAX_AGE_S",
    "parse_noaa_plasma_series",
    "parse_noaa_xray_flux",
    "parse_noaa_kp_index",
]

NOAA_SOLAR_REGIONS_URL: str = "https://services.swpc.noaa.gov/json/solar_regions.json"

# The solar-regions feed is daily (one ``observed_date`` per day), so its freshness
# bound is deliberately coarser than the intraday flux/wind feeds' 3-hour window: a
# reading older than this is treated as a dead/stalled feed and fails closed rather
# than silently driving the SWO phase vector with a week-old active-region count.
DEFAULT_REGIONS_MAX_AGE_S: float = 3 * 24 * 60 * 60  # 3 days


def parse_noaa_solar_regions(
    data: Any,
    *,
    max_age_s: float = DEFAULT_REGIONS_MAX_AGE_S,
    now: datetime | None = None,
) -> int:
    """Count active solar regions on the LATEST observed_date in NOAA's
    ``solar_regions.json`` (one record per numbered region per day).

    This is the scientifically-meaningful active-region count (≈10 currently),
    NOT the raw record count over the ~month the feed spans, and NOT the hundreds
    of per-station observation rows in the separate ``sunspot_report.json``. It
    mirrors the native plugin's ``extract_active_region_count`` so the SWO phase
    vector (``φ·flux/spots``) divides by a correct, stable count.

    The "latest" date is chosen by actually parsing each ``observed_date`` into a
    timestamp and taking the maximum — never by a lexical ``max()`` over raw
    strings, which would silently pick the wrong record if the feed ever changes
    its date format or is delivered out of order. The latest reading must also be
    no older than ``max_age_s`` (fail closed on a stalled feed).

    Raises :class:`TelemetryUnavailable` on an empty/malformed payload, when no
    record carries a parseable ``observed_date``, or when the latest date is
    stale/in the future.
    """
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise TelemetryUnavailable("solar-regions payload is not valid JSON") from exc
    if not isinstance(data, list) or not data:
        raise TelemetryUnavailable("solar-regions payload must be a non-empty array")

    # Select the latest observed_date by parsing timestamps, not by lexical string
    # comparison, so a reordered feed (or a changed date format) cannot yield a
    # stale-but-structurally-valid count.
    latest_dt: datetime | None = None
    for r in data:
        if not isinstance(r, dict):
            continue
        raw = r.get("observed_date")
        if not raw:
            continue
        try:
            dt = _parse_time_tag(raw)
        except TelemetryUnavailable:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
    if latest_dt is None:
        raise TelemetryUnavailable(
            "solar-regions payload missing a parseable observed_date"
        )

    now = now or datetime.now(timezone.utc)
    age = (now - latest_dt).total_seconds()
    if age > max_age_s:
        raise TelemetryUnavailable(
            f"solar-regions is stale: age {age:.0f}s > max {max_age_s:.0f}s"
        )
    if age < -max_age_s:
        raise TelemetryUnavailable(
            f"solar-regions timestamp is in the future by {-age:.0f}s"
        )

    # Count by parsed-date equality (not raw-string equality) so duplicate rows
    # that spell the same day differently still aggregate onto the latest date.
    count = 0
    for r in data:
        if not isinstance(r, dict):
            continue
        raw = r.get("observed_date")
        if not raw:
            continue
        try:
            if _parse_time_tag(raw) == latest_dt:
                count += 1
        except TelemetryUnavailable:
            continue
    if count <= 0:
        raise TelemetryUnavailable("solar-regions: no regions on the latest date")
    return count


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

    NOAA returns ``[{"time_tag": "...", "flux": 130.4}, ...]`` nominally ordered
    oldest→newest. The most recent record is chosen by actually parsing each
    ``time_tag`` and taking the maximum — never by array position (``data[-1]``),
    which would silently return a stale value if the feed were ever reordered.
    Returns the most recent ``(flux, observed_at)``; fails closed on empty/invalid
    data, a missing valid time_tag, or non-positive/non-finite flux.
    """
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise TelemetryUnavailable("F10.7 payload is not valid JSON") from exc
    if not isinstance(data, list) or not data:
        raise TelemetryUnavailable("F10.7 payload is empty or not a list")

    # Select the most recent record by parsed time_tag, not by array position, so a
    # reordered feed cannot yield a stale-but-structurally-valid reading.
    latest: dict[str, Any] | None = None
    latest_time: datetime | None = None
    for record in data:
        if not isinstance(record, dict):
            continue
        raw_time = record.get("time_tag")
        if not raw_time:
            continue
        try:
            observed = _parse_time_tag(raw_time)
        except TelemetryUnavailable:
            continue
        if latest_time is None or observed > latest_time:
            latest_time = observed
            latest = record
    if latest is None or latest_time is None:
        raise TelemetryUnavailable("F10.7 payload has no record with a valid time_tag")

    if "flux" not in latest:
        raise TelemetryUnavailable(f"F10.7 record missing flux: {latest!r}")
    try:
        flux = float(latest["flux"])
    except (TypeError, ValueError) as exc:
        raise TelemetryUnavailable(f"F10.7 flux not numeric: {latest!r}") from exc
    if not math.isfinite(flux) or flux <= 0.0:
        raise TelemetryUnavailable(f"F10.7 flux must be finite and positive, got {flux}")
    return flux, latest_time


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
        # int(float('inf')) raises OverflowError (NOT a ValueError) — without it a JSON-legal
        # `Infinity` sunspots rides past this guard and crashes ingestion instead of failing
        # closed. json.loads accepts the `Infinity` literal, so this boundary is load-bearing.
        sunspots = int(payload["sunspots"])
    except (TypeError, ValueError, OverflowError) as exc:
        raise TelemetryUnavailable(f"telemetry flux/sunspots not numeric or finite: {payload!r}") from exc

    # Fail-closed enforcement — block stale, default, zeroed, or non-finite indicators.
    # NaN/Inf are JSON-legal (json.loads accepts NaN/Infinity) and silently pass a bare
    # `<= 0.0` gate, so the finiteness check is load-bearing, not decorative.
    if not math.isfinite(flux) or flux <= 0.0:
        raise TelemetryUnavailable(f"flux must be finite and positive, got {flux}")
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
    data. The present reading is the row with the maximum parsed ``time_tag`` —
    chosen by parsing timestamps rather than trusting the array's last position,
    so a reordered feed cannot yield a stale-but-structurally-valid reading.
    Raises :class:`TelemetryUnavailable` when: not a non-empty array of rows; the
    speed column is missing/non-numeric; ``speed <= 0``; no row carries a valid
    timestamp; or the latest reading is older than ``max_age_s``.
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

    # Select the most recent data row by parsing its time_tag, not by array
    # position, so a reordered feed cannot yield a stale-but-valid reading.
    last: list[Any] | None = None
    last_time: datetime | None = None
    for row in data[1:]:
        if not isinstance(row, list) or len(row) <= time_col:
            continue
        try:
            observed = _parse_time_tag(row[time_col])
        except TelemetryUnavailable:
            continue
        if last_time is None or observed > last_time:
            last_time = observed
            last = row
    if last is None or last_time is None:
        raise TelemetryUnavailable("solar-wind payload has no row with a valid time_tag")
    if len(last) <= speed_col:
        raise TelemetryUnavailable(f"solar-wind data row malformed: {last!r}")

    try:
        speed = float(last[speed_col])
    except (TypeError, ValueError) as exc:
        raise TelemetryUnavailable(f"solar-wind speed not numeric: {last!r}") from exc
    if not math.isfinite(speed) or speed <= 0.0:
        raise TelemetryUnavailable(f"solar-wind speed must be finite and positive, got {speed}")

    density: float | None = None
    if density_col is not None and len(last) > density_col:
        try:
            density = float(last[density_col])
        except (TypeError, ValueError):
            density = None
        # density is optional, so a non-finite reading fails closed to None (held),
        # never propagated as a "verified" NaN/Inf.
        if density is not None and not math.isfinite(density):
            density = None

    observed = last_time
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


def parse_noaa_plasma_series(data: Any) -> tuple[list[float], list[float], list[float]]:
    """Parse the full NOAA ``plasma-2-hour`` series into (density, speed, temperature).

    The feed is an array of arrays; the first row is the header
    ``["time_tag","density","speed","temperature"]``. Returns three parallel
    lists in chronological order, skipping the header and any row whose speed is
    non-positive/non-numeric. Mirrors the native ``parse_plasma_series`` so the
    realtime graphs match. Fail-closed on an empty/malformed feed.
    """
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise TelemetryUnavailable("plasma series is not valid JSON") from exc
    if not isinstance(data, list) or len(data) < 2:
        raise TelemetryUnavailable("plasma series must have a header + >=1 row")
    density: list[float] = []
    speed: list[float] = []
    temp: list[float] = []
    for row in data[1:]:
        if not isinstance(row, list) or len(row) < 4:
            continue
        try:
            d, s, t = float(row[1]), float(row[2]), float(row[3])
        except (TypeError, ValueError):
            continue
        # Drop the whole row unless every plotted field is finite AND speed positive:
        # a bare `s > 0.0` lets a NaN/Inf density or temperature ride along into the
        # series and corrupt the HUD sparkline / Solar Graph (NaN<=0 and Inf<=0 both
        # False, so the old guard never rejected them).
        if math.isfinite(d) and s > 0.0 and math.isfinite(s) and math.isfinite(t):
            density.append(d)
            speed.append(s)
            temp.append(t)
    if not speed:
        raise TelemetryUnavailable("plasma series has no valid rows")
    return density, speed, temp


def parse_noaa_xray_flux(data: Any, band: str = "0.1-0.8nm") -> list[float]:
    """Parse the GOES X-ray flux series for one energy band -> list[float].

    NOAA emits two records per minute (one per energy band); we keep the chosen
    ``band`` (default the long 0.1-0.8 nm channel) and its positive flux values
    (W/m^2). Mirrors the native ``parse_xray_series``. Fail-closed.
    """
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise TelemetryUnavailable("xray series is not valid JSON") from exc
    if not isinstance(data, list) or not data:
        raise TelemetryUnavailable("xray series is empty")
    out: list[float] = []
    for r in data:
        if not isinstance(r, dict) or r.get("energy") != band:
            continue
        try:
            v = float(r["flux"])
        except (TypeError, ValueError, KeyError):
            continue
        # `+Inf > 0.0` is True, so a bare positivity gate admits +Infinity into the
        # log-scaled X-ray graph; require finiteness explicitly.
        if math.isfinite(v) and v > 0.0:
            out.append(v)
    if not out:
        raise TelemetryUnavailable(f"xray series has no rows for band {band!r}")
    return out


def parse_noaa_kp_index(data: Any) -> list[float]:
    """Parse the 1-min estimated planetary Kp series -> list[float].

    Reads ``estimated_kp`` from each record (Kp may legitimately be 0). The
    nominal Kp scale runs 0..9, but this guard admits values up to 12.0: NOAA's
    *estimated* planetary Kp is a real-time approximation that can transiently
    overshoot the 9 ceiling of the definitive index, so accepting the overshoot
    avoids silently dropping a live storm reading. Records whose ``estimated_kp``
    falls outside ``[0.0, 12.0]`` (or is non-numeric) are skipped. Mirrors the
    native ``parse_kp_series``. Fail-closed on an empty/malformed feed.
    """
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise TelemetryUnavailable("kp series is not valid JSON") from exc
    if not isinstance(data, list) or not data:
        raise TelemetryUnavailable("kp series is empty")
    out: list[float] = []
    for r in data:
        if not isinstance(r, dict) or "estimated_kp" not in r:
            continue
        try:
            v = float(r["estimated_kp"])
        except (TypeError, ValueError):
            continue
        if 0.0 <= v <= 12.0:
            out.append(v)
    if not out:
        raise TelemetryUnavailable("kp series has no valid rows")
    return out
