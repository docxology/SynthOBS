"""Telemetry ingestion tests (ISC-11..18) — real HTTP via pytest-httpserver, no mocks."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from synthobs.telemetry import (
    DEFAULT_MAX_AGE_S,
    SolarTelemetry,
    TelemetryUnavailable,
    fetch_live_telemetry,
    parse_noaa_f107_flux,
    telemetry_from_payload,
)

pytest_httpserver = pytest.importorskip("pytest_httpserver")


def _now() -> datetime:
    return datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)


def _fresh_payload(**over) -> dict:
    base = {
        "flux": 130.4,
        "sunspots": 3,
        "time_tag": "2026-06-10T11:30:00Z",
        "regions": ["AR4465", "AR4464", "AR4456"],
    }
    base.update(over)
    return base


# --- dataclass / payload parsing ----------------------------------------
def test_telemetry_dataclass_fields() -> None:  # ISC-11
    t = telemetry_from_payload(_fresh_payload(), now=_now())
    assert isinstance(t, SolarTelemetry)
    assert t.flux == 130.4
    assert t.sunspots == 3
    assert t.regions == ("AR4465", "AR4464", "AR4456")
    assert t.observed_at.tzinfo is not None
    assert t.age_seconds(_now()) == pytest.approx(1800.0)


def test_payload_well_formed(httpserver) -> None:  # ISC-12, ISC-17
    httpserver.expect_request("/swo").respond_with_json(_fresh_payload())
    t = fetch_live_telemetry(httpserver.url_for("/swo"), now=_now())
    assert t.flux == 130.4 and t.sunspots == 3


def test_non_200_fails_closed(httpserver) -> None:  # ISC-13
    httpserver.expect_request("/swo").respond_with_data("nope", status=503)
    with pytest.raises(TelemetryUnavailable):
        fetch_live_telemetry(httpserver.url_for("/swo"), now=_now())


def test_malformed_json_fails_closed(httpserver) -> None:  # ISC-14
    httpserver.expect_request("/swo").respond_with_data("{not json", status=200)
    with pytest.raises(TelemetryUnavailable):
        fetch_live_telemetry(httpserver.url_for("/swo"), now=_now())


def test_empty_body_fails_closed(httpserver) -> None:  # ISC-14
    httpserver.expect_request("/swo").respond_with_data("", status=200)
    with pytest.raises(TelemetryUnavailable):
        fetch_live_telemetry(httpserver.url_for("/swo"), now=_now())


@pytest.mark.parametrize("flux", [0, -1, -130.4])
def test_nonpositive_flux_fails_closed(flux) -> None:  # ISC-15
    with pytest.raises(TelemetryUnavailable):
        telemetry_from_payload(_fresh_payload(flux=flux), now=_now())


@pytest.mark.parametrize("spots", [0, -1, -5])
def test_nonpositive_spots_fails_closed(spots) -> None:  # ISC-16
    with pytest.raises(TelemetryUnavailable):
        telemetry_from_payload(_fresh_payload(sunspots=spots), now=_now())


def test_missing_keys_fail_closed() -> None:
    with pytest.raises(TelemetryUnavailable):
        telemetry_from_payload({"flux": 100.0}, now=_now())
    with pytest.raises(TelemetryUnavailable):
        telemetry_from_payload("[]", now=_now())  # list, not dict


def test_stale_timestamp_fails_closed() -> None:  # ISC-18
    old = (_now() - timedelta(seconds=DEFAULT_MAX_AGE_S + 60)).isoformat()
    with pytest.raises(TelemetryUnavailable):
        telemetry_from_payload(_fresh_payload(time_tag=old), now=_now())


def test_future_timestamp_fails_closed() -> None:
    future = (_now() + timedelta(seconds=DEFAULT_MAX_AGE_S + 600)).isoformat()
    with pytest.raises(TelemetryUnavailable):
        telemetry_from_payload(_fresh_payload(time_tag=future), now=_now())


def test_malformed_time_tag_fails_closed() -> None:
    with pytest.raises(TelemetryUnavailable):
        telemetry_from_payload(_fresh_payload(time_tag="not-a-date"), now=_now())
    with pytest.raises(TelemetryUnavailable):
        telemetry_from_payload(_fresh_payload(time_tag=None), now=_now())


def test_connection_failure_fails_closed() -> None:
    # Nothing listening on this port → URLError → TelemetryUnavailable.
    with pytest.raises(TelemetryUnavailable):
        fetch_live_telemetry("http://127.0.0.1:1/swo", timeout=0.5, now=_now())


# --- NOAA F10.7 array parser --------------------------------------------
def test_parse_noaa_f107_latest() -> None:
    data = [
        {"time_tag": "2026-06-08T00:00:00", "flux": 120.0},
        {"time_tag": "2026-06-10T00:00:00", "flux": 131.7},
    ]
    flux, observed = parse_noaa_f107_flux(data)
    assert flux == 131.7
    assert observed.year == 2026 and observed.day == 10


def test_parse_noaa_f107_as_text() -> None:
    text = json.dumps([{"time_tag": "2026-06-10T00:00:00Z", "flux": 99.5}])
    flux, _ = parse_noaa_f107_flux(text)
    assert flux == 99.5


@pytest.mark.parametrize("bad", ["[]", "not json", json.dumps([{"time_tag": "2026-06-10T00:00:00", "flux": 0}])])
def test_parse_noaa_f107_fails_closed(bad: str) -> None:
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_f107_flux(bad)
