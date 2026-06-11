"""Tests for the realtime solar-data series parsers (no mocks — real structures).

These mirror the native C parsers (parse_plasma_series / parse_xray_series /
parse_kp_series) that drive the Solar Graph feed, so the realtime graphs match
the tested Python reference.
"""

from __future__ import annotations

import json

import pytest
from synthobs.telemetry import (
    TelemetryUnavailable,
    parse_noaa_kp_index,
    parse_noaa_plasma_series,
    parse_noaa_xray_flux,
)


# --- plasma-2-hour (density / speed / temperature) -----------------------
def test_plasma_series_parses_columns_and_skips_header() -> None:
    feed = [
        ["time_tag", "density", "speed", "temperature"],
        ["2026-06-11 00:00:00", "5.1", "410.0", "120000"],
        ["2026-06-11 00:01:00", "5.3", "412.5", "121000"],
    ]
    dens, speed, temp = parse_noaa_plasma_series(feed)
    assert speed == [410.0, 412.5]
    assert dens == [5.1, 5.3]
    assert temp == [120000.0, 121000.0]


def test_plasma_series_skips_bad_speed_rows() -> None:
    feed = [
        ["time_tag", "density", "speed", "temperature"],
        ["t", "5.0", "0", "100"],  # zero speed -> skipped
        ["t", "6.0", "null", "100"],  # non-numeric -> skipped
        ["t", "7.0", "400", "100"],  # kept
    ]
    dens, speed, temp = parse_noaa_plasma_series(feed)
    assert speed == [400.0] and dens == [7.0]


@pytest.mark.parametrize("bad", ["not json", "[]", json.dumps([["h", "d", "s", "t"]])])
def test_plasma_series_fails_closed(bad: str) -> None:
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_plasma_series(bad)


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
