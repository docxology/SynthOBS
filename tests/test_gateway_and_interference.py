"""Tests for the EGS Gateway, holographic interference, solar-wind telemetry, and
their engine integration (ISC-91..110). No mocks — real math + a local HTTP server.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import pytest
from synthobs import constants as C
from synthobs.engine import SynthEngine
from synthobs.gateway import GatewayLock, egs_fractal_constant, gateway_filter
from synthobs.interference import (
    InterferenceVerdict,
    NodeField,
    holographic_gate,
    interference_intensity,
    is_holographic_false,
    is_holographic_true,
    rsi_is_stable,
    rsi_step,
)
from synthobs.telemetry import (
    SolarWind,
    TelemetryUnavailable,
    fetch_live_solar_wind,
    parse_noaa_solar_wind,
)


# --- constants: the canonical EGS gateway key ----------------------------
def test_egs_gateway_key_is_phi_weighted_optical_ratio() -> None:
    # K_EGS = φ · (λ_reader / λ_Hα), NOT bare φ.
    expected = C.PHI * (C.LAMBDA_READER_NM / C.LAMBDA_H_ALPHA_NM)
    assert C.EGS_GATEWAY_KEY == pytest.approx(expected)
    assert C.EGS_GATEWAY_KEY == pytest.approx(2.539427, abs=1e-5)
    # genuinely distinct from the golden ratio
    assert abs(C.EGS_GATEWAY_KEY - C.PHI) > 0.9


def test_egs_gateway_key_c_literal_matches_python() -> None:
    # the C plugin pins this literal; drift is a failure (mirror of ISC-60)
    assert float(C.EGS_GATEWAY_KEY_C_LITERAL) == pytest.approx(C.EGS_GATEWAY_KEY, abs=1e-6)


def test_canonical_anchors_present() -> None:
    assert C.LAMBDA_READER_NM == 1030.0
    assert C.LAMBDA_H_ALPHA_NM == 656.28
    assert C.REFERENCE_SOLAR_WIND_KMS == 400.0
    assert C.DEFAULT_SOLAR_WIND_KMS == 551.7
    assert C.CRAB_PULSAR_HZ == pytest.approx(29.94)
    assert C.H_LINE_MHZ == pytest.approx(1420.405751)


# --- gateway -------------------------------------------------------------
def test_gateway_fractal_constant_function() -> None:
    assert egs_fractal_constant() == pytest.approx(C.EGS_GATEWAY_KEY)


def test_gateway_filter_lock_strength_in_unit_interval() -> None:
    for wind in (300.0, 400.0, 551.7, 700.0, 900.0):
        lock = gateway_filter(wind)
        assert isinstance(lock, GatewayLock)
        assert 0.0 <= lock.lock_strength <= 1.0
        assert 0.0 <= lock.phase_bias_rad < 2.0 * math.pi
        assert lock.lock_strength == pytest.approx(abs(math.cos(lock.phase_bias_rad)))


def test_gateway_phase_bias_formula() -> None:
    wind = 551.7
    lock = gateway_filter(wind)
    norm = wind / C.REFERENCE_SOLAR_WIND_KMS
    expected_phase = (2.0 * math.pi * norm * C.EGS_GATEWAY_KEY) % (2.0 * math.pi)
    assert lock.phase_bias_rad == pytest.approx(expected_phase)


def test_gateway_fails_closed_on_nonpositive_wind() -> None:
    with pytest.raises(ValueError):
        gateway_filter(0.0)
    with pytest.raises(ValueError):
        gateway_filter(-100.0)


def test_gateway_fails_closed_on_nonfinite_wind() -> None:
    # NaN/Inf are the canonical garbage indicators — must fail closed at the API,
    # not produce a NaN "lock" (regression guard for the public-API fail-closed gap).
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            gateway_filter(bad)


def test_egs_gateway_key_full_precision_anchor() -> None:
    # Pin the computed value to full precision so a silent λ-anchor regression is
    # caught, not just the loose 1e-5 literal.
    assert C.EGS_GATEWAY_KEY == pytest.approx(2.5394267818802825, abs=1e-12)


# --- holographic interference --------------------------------------------
def test_nodefield_magnitude_and_ops() -> None:
    a = NodeField(3.0, 4.0)
    assert a.magnitude == pytest.approx(5.0)
    assert (a + NodeField(1.0, -1.0)) == NodeField(4.0, 3.0)
    assert a.scaled(2.0) == NodeField(6.0, 8.0)
    assert a.conjugate() == NodeField(3.0, -4.0)


def test_interference_intensity_constructive_vs_destructive() -> None:
    a = NodeField(1.0, 0.0)
    # in-phase doubles amplitude → 4× intensity
    assert interference_intensity(a, NodeField(1.0, 0.0)) == pytest.approx(4.0)
    # anti-phase cancels → 0 intensity
    assert interference_intensity(a, NodeField(-1.0, 0.0)) == pytest.approx(0.0)


def test_holographic_gate_constructive_true() -> None:
    # strong AR node, weak (near-real) phase-flip → constructive AR14409
    verdict = holographic_gate(NodeField(2.0, 0.0), NodeField(0.01, 0.0))
    assert verdict is InterferenceVerdict.CONSTRUCTIVE_AR14409
    assert is_holographic_true(verdict)
    assert not is_holographic_false(verdict)


def test_holographic_gate_destructive_false() -> None:
    # AR node cancels against the reference (i_ar≈0); the phase-flip node beats
    # strongly against its own conjugate (real part survives → big i_h).
    verdict = holographic_gate(
        NodeField(-1.0, 0.0), NodeField(5.0, 0.0), reference=NodeField(1.0, 0.0)
    )
    assert verdict is InterferenceVerdict.DESTRUCTIVE_H_PHASE_FLIP
    assert is_holographic_false(verdict)


def test_holographic_gate_mixed_within_margin() -> None:
    # construct a tie: AR intensity equals H intensity
    ar = NodeField(0.0, 1.0)  # i_ar = |(0,1)+(1,0)|^2 = 2
    h = NodeField(math.sqrt(0.5), 0.0)  # i_h = |(.707,0)+(.707,0)|^2 = 2
    assert holographic_gate(ar, h) is InterferenceVerdict.MIXED


def test_holographic_gate_fails_closed_on_nonfinite() -> None:
    # A non-finite node must raise, not silently resolve to MIXED (NaN) or a
    # spurious CONSTRUCTIVE verdict (Inf).
    nan = float("nan")
    inf = float("inf")
    for bad in (
        NodeField(nan, 0.0),
        NodeField(0.0, inf),
        NodeField(inf, 0.0),
    ):
        with pytest.raises(ValueError):
            holographic_gate(bad, NodeField(1.0, 0.0))
        with pytest.raises(ValueError):
            holographic_gate(NodeField(1.0, 0.0), bad)


def test_rsi_stability_criterion() -> None:
    assert rsi_is_stable(0.5, 0.5) is True
    assert rsi_is_stable(2.0, 1.0) is False
    # a stable RSI contracts toward zero
    x = 1.0
    for _ in range(50):
        x = rsi_step(x, 0.5, 0.5)
    assert abs(x) < 1e-6
    # an unstable RSI diverges
    x = 1.0
    for _ in range(20):
        x = rsi_step(x, 2.0, 1.0)
    assert abs(x) > 100.0


# --- solar-wind telemetry (fail-closed, no mocks) ------------------------
def _wind_feed(speed: str, *, when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    ts = when.strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps(
        [
            ["time_tag", "density", "speed", "temperature"],
            ["2026-06-10 00:00:00", "3.1", "480.0", "1.0e5"],
            [ts, "4.5", speed, "1.2e5"],
        ]
    )


def test_parse_solar_regions_counts_latest_date_only() -> None:
    from synthobs.telemetry import parse_noaa_solar_regions

    # a month of history: 3 regions on the latest date, 20 on an older date.
    feed = (
        [{"observed_date": "2026-06-01", "region": 4450 + i} for i in range(20)]
        + [{"observed_date": "2026-06-10", "region": 4467 + i} for i in range(3)]
    )
    # must return 3 (latest date), NOT 23 (all records) — the over-count bug.
    # `now` is pinned near the latest observed_date so the freshness guard passes
    # deterministically regardless of the wall clock.
    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    assert parse_noaa_solar_regions(feed, now=now) == 3


def test_parse_solar_regions_selects_latest_by_parsed_date_not_lexical() -> None:
    from synthobs.telemetry import parse_noaa_solar_regions

    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    # Rows are shuffled and include a duplicate spelling of the latest day
    # ("2026-06-10" and "2026-06-10T00:00:00" both parse to the same date). The
    # latest date (2026-06-10) has 3 records total; older dates must be ignored.
    # A naive lexical max() over raw strings would mis-rank "2026-06-10T00:00:00"
    # vs "2026-06-10" and could under/over-count; parsed-date comparison must not.
    feed = [
        {"observed_date": "2026-06-10", "region": 4467},
        {"observed_date": "2026-06-01", "region": 4450},
        {"observed_date": "2026-06-10T00:00:00", "region": 4468},
        {"observed_date": "2026-06-09", "region": 4460},
        {"observed_date": "2026-06-10", "region": 4469},
        {"observed_date": "2026-06-01", "region": 4451},
    ]
    assert parse_noaa_solar_regions(feed, now=now) == 3


def test_parse_solar_regions_rejects_stale_feed() -> None:
    from synthobs.telemetry import parse_noaa_solar_regions

    # Latest date is ~10 days before `now` — well past the 3-day regions window.
    now = datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)
    feed = [{"observed_date": "2026-06-10", "region": 4467 + i} for i in range(3)]
    with pytest.raises(TelemetryUnavailable, match="stale"):
        parse_noaa_solar_regions(feed, now=now)


def test_parse_solar_regions_rejects_future_feed() -> None:
    from synthobs.telemetry import parse_noaa_solar_regions

    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Latest date is ~9 days in the future relative to `now`.
    feed = [{"observed_date": "2026-06-10", "region": 4467 + i} for i in range(2)]
    with pytest.raises(TelemetryUnavailable, match="future"):
        parse_noaa_solar_regions(feed, now=now)


@pytest.mark.parametrize("bad", ["not json", "[]", '[{"region": 1}]', '{"observed_date": "x"}'])
def test_parse_solar_regions_fails_closed(bad: str) -> None:
    from synthobs.telemetry import parse_noaa_solar_regions

    with pytest.raises(TelemetryUnavailable):
        parse_noaa_solar_regions(bad)


def test_parse_solar_wind_happy_path() -> None:
    wind = parse_noaa_solar_wind(_wind_feed("551.7"))
    assert isinstance(wind, SolarWind)
    assert wind.speed_kms == pytest.approx(551.7)
    assert wind.density == pytest.approx(4.5)


def test_parse_solar_wind_uses_last_row() -> None:
    wind = parse_noaa_solar_wind(_wind_feed("612.3"))
    assert wind.speed_kms == pytest.approx(612.3)  # last row, not the 480 first row


def test_parse_solar_wind_selects_latest_by_timestamp_not_position() -> None:
    # The most recent reading (by time_tag) is NOT the last array row here, and a
    # duplicate-timestamp row is present. Selecting by array position (data[-1])
    # would return the stale 400.0 reading; parsing timestamps must return 590.0.
    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    feed = json.dumps(
        [
            ["time_tag", "density", "speed", "temperature"],
            ["2026-06-10 11:59:00", "4.5", "590.0", "1.2e5"],  # newest, mid-array
            ["2026-06-10 11:58:00", "4.2", "540.0", "1.1e5"],  # duplicate-ish older
            ["2026-06-10 11:57:00", "4.0", "400.0", "1.0e5"],  # oldest, but LAST
        ]
    )
    wind = parse_noaa_solar_wind(feed, now=now)
    assert wind.speed_kms == pytest.approx(590.0)
    assert wind.density == pytest.approx(4.5)


def test_parse_solar_wind_bad_density_is_optional() -> None:
    feed = json.dumps(
        [
            ["time_tag", "density", "speed", "temperature"],
            [datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "not-density", "500.0", "1.0e5"],
        ]
    )
    wind = parse_noaa_solar_wind(feed)
    assert wind.speed_kms == pytest.approx(500.0)
    assert wind.density is None


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps([]),  # empty
        json.dumps([["time_tag", "density", "speed", "temperature"]]),  # header only
        json.dumps(["time_tag", ["2026-06-10 00:00:00", "1", "2"]]),  # malformed header
        json.dumps([["time_tag", "density", "temperature"], ["t", "1", "2"]]),  # no speed col
        json.dumps([["time_tag", "speed"], "not-row"]),  # malformed data row
        json.dumps([["time_tag", "density", "speed"], ["2026-06-10 00:00:00", "1", "x"]]),  # non-numeric
        json.dumps([["time_tag", "density", "speed"], ["2026-06-10 00:00:00", "1", "-5"]]),  # negative
    ],
)
def test_parse_solar_wind_fails_closed(payload: str) -> None:
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_solar_wind(payload)


def test_parse_solar_wind_rejects_stale() -> None:
    old = datetime.now(timezone.utc) - timedelta(hours=5)
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_solar_wind(_wind_feed("500.0", when=old))


def test_parse_solar_wind_rejects_future_timestamp() -> None:
    future = datetime.now(timezone.utc) + timedelta(hours=5)
    with pytest.raises(TelemetryUnavailable):
        parse_noaa_solar_wind(_wind_feed("500.0", when=future))


def test_fetch_live_solar_wind_against_local_server(httpserver) -> None:
    httpserver.expect_request("/wind").respond_with_data(
        _wind_feed("543.2"), content_type="application/json"
    )
    wind = fetch_live_solar_wind(httpserver.url_for("/wind"))
    assert wind.speed_kms == pytest.approx(543.2)


def test_fetch_live_solar_wind_non200_fails_closed(httpserver) -> None:
    httpserver.expect_request("/down").respond_with_data("nope", status=503)
    with pytest.raises(TelemetryUnavailable):
        fetch_live_solar_wind(httpserver.url_for("/down"))


# --- engine integration --------------------------------------------------
def test_swo_lock_gateway_fails_closed() -> None:
    from synthobs.swo import SolarWavefieldOscillator

    osc = SolarWavefieldOscillator()
    assert osc.lock_gateway(551.7) is True
    held = osc.lock_strength
    assert osc.lock_gateway(-5.0) is False  # negative wind → hold
    assert osc.lock_gateway(0.0) is False  # zero wind → hold
    assert osc.lock_gateway(float("nan")) is False  # NaN → hold
    assert osc.lock_gateway(float("inf")) is False  # Inf → hold
    assert osc.lock_strength == held  # unchanged across all bad inputs


def test_engine_gateway_lock_and_state() -> None:
    eng = SynthEngine()
    assert eng.lock_strength == 0.0
    assert eng.wind_phase == 0.0
    assert eng.state().verdict is None  # no gateway lock yet

    assert eng.update_gateway(SolarWind(551.7, 4.5, "test", datetime.now(timezone.utc))) is True
    assert 0.0 <= eng.lock_strength <= 1.0
    st = eng.state()
    assert st.lock_strength == eng.lock_strength
    assert st.verdict in set(InterferenceVerdict)


def test_engine_gateway_holds_on_none() -> None:
    eng = SynthEngine()
    eng.update_gateway(SolarWind(551.7, 4.5, "t", datetime.now(timezone.utc)))
    held = eng.lock_strength
    assert eng.update_gateway(None) is False  # dropout → hold
    assert eng.lock_strength == held  # unchanged


def test_engine_gateway_independent_of_amplitude_calibration() -> None:
    from synthobs.telemetry import SolarTelemetry

    eng = SynthEngine()
    # gateway locks from wind even though flux/spots never calibrated
    eng.update_gateway(SolarWind(600.0, 5.0, "t", datetime.now(timezone.utc)))
    assert eng.lock_strength >= 0.0
    assert eng.phase_vector is None  # amplitude plane still un-calibrated
    # now calibrate amplitude; gateway lock survives
    lock_before = eng.lock_strength
    eng.update(SolarTelemetry(130.0, 3, "t", datetime.now(timezone.utc)))
    assert eng.phase_vector is not None
    assert eng.lock_strength == lock_before
