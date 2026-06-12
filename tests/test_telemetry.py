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


def test_custom_opener_non_200_fails_closed() -> None:
    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def getcode(self) -> int:
            return self.status

        def read(self) -> bytes:
            return b""

    def opener(url: str, *, timeout: float) -> Response:
        assert url == "https://example.invalid/swo"
        assert timeout == 1.0
        return Response()

    with pytest.raises(TelemetryUnavailable, match="non-200"):
        fetch_live_telemetry(
            "https://example.invalid/swo", timeout=1.0, now=_now(), opener=opener
        )


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


@pytest.mark.parametrize(
    "data",
    [
        [{"time_tag": "2026-06-10T00:00:00"}],
        [{"time_tag": "2026-06-10T00:00:00", "flux": "x"}],
    ],
)
def test_parse_noaa_f107_missing_or_nonnumeric_flux_fails_closed(data: list[dict]) -> None:
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_f107_flux(data)


# --- non-finite (NaN/Inf) fail-closed regression (boundary leak the bare `<= 0.0`
#     guards missed; NaN/Inf are JSON-legal and slip past `x <= 0.0`) --------------
_NONFINITE = ["NaN", "Infinity", "-Infinity"]


@pytest.mark.parametrize("tok", _NONFINITE)
def test_telemetry_from_payload_rejects_nonfinite_flux(tok: str) -> None:
    # Build the JSON by hand so the literal NaN/Infinity reaches json.loads, which
    # accepts them by default — the exact path a malformed NOAA feed would take.
    raw = '{"flux": %s, "sunspots": 3, "time_tag": "2026-06-10T11:30:00Z"}' % tok
    with pytest.raises(TelemetryUnavailable):
        telemetry_from_payload(raw, now=_now())


@pytest.mark.parametrize("tok", _NONFINITE)
def test_parse_noaa_f107_rejects_nonfinite_flux(tok: str) -> None:
    raw = '[{"time_tag": "2026-06-10T00:00:00", "flux": %s}]' % tok
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_f107_flux(raw)


@pytest.mark.parametrize("tok", _NONFINITE)
def test_parse_noaa_solar_wind_rejects_nonfinite_speed(tok: str) -> None:
    from synthobs.telemetry import parse_noaa_solar_wind

    raw = (
        '[["time_tag","density","speed","temperature"],'
        '["2026-06-10T11:59:00", 5.0, %s, 1.0e5]]' % tok
    )
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_solar_wind(raw, now=_now())


@pytest.mark.parametrize("tok", _NONFINITE)
def test_parse_noaa_solar_wind_nonfinite_density_held_to_none(tok: str) -> None:
    from synthobs.telemetry import parse_noaa_solar_wind

    raw = (
        '[["time_tag","density","speed","temperature"],'
        '["2026-06-10T11:59:00", %s, 420.0, 1.0e5]]' % tok
    )
    wind = parse_noaa_solar_wind(raw, now=_now())
    assert wind.speed_kms == 420.0
    assert wind.density is None  # non-finite optional field fails closed to held/None
