"""Tests for the realtime solar-data series parsers using real structures.

These mirror the native C parsers (parse_plasma_series / parse_xray_series /
parse_kp_series) that drive the Solar Graph feed, so the realtime graphs match
the tested Python reference.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from synthobs.telemetry import (
    TelemetryUnavailable,
    parse_noaa_kp_index,
    parse_noaa_plasma_series,
    parse_noaa_xray_flux,
)

_HISTORICAL_NOW = datetime(2026, 7, 16, 2, 30, tzinfo=timezone.utc)


def _parse_series(feed):
    return parse_noaa_plasma_series(feed, max_age_s=10**9, now=_HISTORICAL_NOW)


# --- real-time solar wind (density / speed / temperature) -----------------
def test_plasma_series_parses_current_rtsw_object_schema_chronologically() -> None:
    feed = [
        {
            "time_tag": "2026-07-16T02:18:00",
            "active": False,
            "proton_density": 99.0,
            "proton_speed": 999.0,
            "proton_temperature": 999.0,
        },
        {
            "time_tag": "2026-07-16T02:17:00",
            "active": True,
            "proton_density": 3.14,
            "proton_speed": 451.0,
            "proton_temperature": 190801,
        },
        {
            "time_tag": "2026-07-16T02:16:00",
            "active": True,
            "proton_density": 2.71,
            "proton_speed": 449.0,
            "proton_temperature": 188000,
        },
    ]

    dens, speed, temp = _parse_series(feed)

    assert dens == [2.71, 3.14]
    assert speed == [449.0, 451.0]
    assert temp == [188000.0, 190801.0]


def test_plasma_series_parses_current_object_rows() -> None:
    feed = [
        {"time_tag": "2026-06-11T00:00:00Z", "active": True, "proton_density": 5.1, "proton_speed": 410.0, "proton_temperature": 120000},
        {"time_tag": "2026-06-11T00:01:00Z", "active": True, "proton_density": 5.3, "proton_speed": 412.5, "proton_temperature": 121000},
    ]
    dens, speed, temp = _parse_series(feed)
    assert speed == [410.0, 412.5]
    assert dens == [5.1, 5.3]
    assert temp == [120000.0, 121000.0]


def test_plasma_series_rejects_non_object_rows() -> None:
    with pytest.raises(TelemetryUnavailable):
        _parse_series([["time_tag", "proton_speed"], ["t", 400.0]])


def test_plasma_series_skips_bad_speed_rows() -> None:
    feed = [
        {"time_tag": "2026-06-11T00:00:00Z", "active": True, "proton_density": 5.0, "proton_speed": 0.0, "proton_temperature": 100},
        {"time_tag": "2026-06-11T00:01:00Z", "active": True, "proton_density": 6.0, "proton_speed": "null", "proton_temperature": 100},
        {"time_tag": "2026-06-11T00:02:00Z", "active": True, "proton_density": 7.0, "proton_speed": 400.0, "proton_temperature": 100},
    ]
    dens, speed, temp = _parse_series(feed)
    assert speed == [400.0] and dens == [7.0]


def test_plasma_series_fails_closed_on_overflowing_object_measurement() -> None:
    feed = [
        {
            "time_tag": "2026-07-16T02:17:00",
            "active": True,
            "proton_density": 10**1000,
            "proton_speed": 451.0,
            "proton_temperature": 190801,
        }
    ]
    with pytest.raises(TelemetryUnavailable):
        _parse_series(feed)


@pytest.mark.parametrize("bad", ["not json", "[]", json.dumps([{"time_tag": "t"}])])
def test_plasma_series_fails_closed(bad: str) -> None:
    with pytest.raises(TelemetryUnavailable):
        _parse_series(bad)


def test_plasma_series_rejects_stale_rows() -> None:
    feed = [{
        "time_tag": "2026-07-15T00:00:00Z",
        "active": True,
        "proton_density": 5.0,
        "proton_speed": 400.0,
        "proton_temperature": 100000.0,
    }]
    with pytest.raises(TelemetryUnavailable, match="no valid rows"):
        parse_noaa_plasma_series(feed, max_age_s=3600.0, now=_HISTORICAL_NOW)


# --- GOES X-ray flux -----------------------------------------------------
def test_xray_keeps_only_chosen_band() -> None:
    feed = [
        {"time_tag": "t", "flux": 1.0e-8, "energy": "0.05-0.4nm"},
        {"time_tag": "t", "flux": 2.0e-8, "energy": "0.1-0.8nm"},
        {"time_tag": "t", "flux": 3.0e-8, "energy": "0.1-0.8nm"},
    ]
    assert parse_noaa_xray_flux(feed) == [2.0e-8, 3.0e-8]
    assert parse_noaa_xray_flux(feed, band="0.05-0.4nm") == [1.0e-8]


def test_xray_skips_nonpositive_and_bad() -> None:
    feed = [
        {"flux": 0.0, "energy": "0.1-0.8nm"},
        {"flux": "x", "energy": "0.1-0.8nm"},
        {"flux": 5.0e-7, "energy": "0.1-0.8nm"},
    ]
    assert parse_noaa_xray_flux(feed) == [5.0e-7]


def test_xray_and_kp_reject_boolean_measurements() -> None:
    assert parse_noaa_xray_flux([{"flux": True, "energy": "0.1-0.8nm"}, {"flux": 1e-8, "energy": "0.1-0.8nm"}]) == [1e-8]
    assert parse_noaa_kp_index([{"estimated_kp": True}, {"estimated_kp": 2.0}]) == [2.0]


@pytest.mark.parametrize("bad", ["not json", "[]", json.dumps([{"flux": 1.0, "energy": "x"}])])
def test_xray_fails_closed(bad: str) -> None:
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_xray_flux(bad)


# --- planetary Kp --------------------------------------------------------
def test_kp_reads_estimated_kp_including_zero() -> None:
    feed = [
        {"time_tag": "t", "kp_index": 0, "estimated_kp": 0.0, "kp": "0Z"},
        {"time_tag": "t", "kp_index": 3, "estimated_kp": 2.67, "kp": "3M"},
    ]
    assert parse_noaa_kp_index(feed) == [0.0, 2.67]


def test_kp_skips_out_of_range_and_missing() -> None:
    feed = [
        {"estimated_kp": 99.0},  # out of range
        {"kp": "5"},  # missing estimated_kp
        {"estimated_kp": 4.33},
    ]
    assert parse_noaa_kp_index(feed) == [4.33]


@pytest.mark.parametrize("bad", ["not json", "[]", json.dumps([{"kp": "5"}])])
def test_kp_fails_closed(bad: str) -> None:
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_kp_index(bad)
