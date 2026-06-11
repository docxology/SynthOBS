"""Tests for synthobs.history — no mocks, real data and computation only."""

from __future__ import annotations

import math

import pytest

from synthobs.history import Sample, TelemetryHistory


def _sample(flux: float) -> Sample:
    """Build a Sample where ``flux`` carries the distinguishing value."""
    return Sample(
        flux=flux,
        solar_wind_kms=400.0 + flux,
        lock_strength=0.5,
        phase_bias_rad=0.1,
    )


# --- Sample validation -----------------------------------------------------


def test_sample_is_frozen():
    s = _sample(1.0)
    with pytest.raises(Exception):
        s.flux = 2.0  # type: ignore[misc]


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_sample_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        Sample(flux=bad, solar_wind_kms=1.0, lock_strength=1.0, phase_bias_rad=1.0)


def test_sample_rejects_bool():
    with pytest.raises(ValueError):
        Sample(
            flux=True,  # type: ignore[arg-type]
            solar_wind_kms=1.0,
            lock_strength=1.0,
            phase_bias_rad=1.0,
        )


def test_sample_accepts_int_and_negative():
    s = Sample(flux=-3, solar_wind_kms=0, lock_strength=1, phase_bias_rad=-2)
    assert s.flux == -3


# --- Capacity enforcement --------------------------------------------------


@pytest.mark.parametrize("cap", [1, 0, -5])
def test_invalid_capacity_raises(cap):
    with pytest.raises(ValueError):
        TelemetryHistory(capacity=cap)


def test_capacity_must_be_int():
    with pytest.raises(ValueError):
        TelemetryHistory(capacity=4.0)  # type: ignore[arg-type]


def test_default_capacity():
    h = TelemetryHistory()
    assert h.capacity == 128


def test_oldest_evicted_past_capacity():
    h = TelemetryHistory(capacity=3)
    for i in range(5):
        h.append(_sample(float(i)))
    assert len(h) == 3
    # Oldest (0.0, 1.0) evicted; window holds 2.0, 3.0, 4.0 chronologically.
    assert h.series("flux") == [2.0, 3.0, 4.0]


def test_len_grows_until_capacity():
    h = TelemetryHistory(capacity=4)
    assert len(h) == 0
    h.append(_sample(0.0))
    assert len(h) == 1
    for i in range(1, 10):
        h.append(_sample(float(i)))
    assert len(h) == 4


def test_clear_empties():
    h = TelemetryHistory(capacity=4)
    h.append(_sample(1.0))
    h.append(_sample(2.0))
    h.clear()
    assert len(h) == 0
    assert h.series("flux") == []
    assert h.latest() is None


# --- append validation -----------------------------------------------------


def test_append_rejects_non_sample():
    h = TelemetryHistory(capacity=4)
    with pytest.raises(ValueError):
        h.append((1.0, 2.0, 3.0, 4.0))  # type: ignore[arg-type]


# --- series ----------------------------------------------------------------


def test_series_chronological_order():
    h = TelemetryHistory(capacity=8)
    for i in range(4):
        h.append(_sample(float(i)))
    assert h.series("flux") == [0.0, 1.0, 2.0, 3.0]
    assert h.series("solar_wind_kms") == [400.0, 401.0, 402.0, 403.0]


def test_series_empty():
    h = TelemetryHistory(capacity=8)
    assert h.series("flux") == []


def test_series_all_fields():
    h = TelemetryHistory(capacity=4)
    h.append(
        Sample(flux=1.0, solar_wind_kms=2.0, lock_strength=3.0, phase_bias_rad=4.0)
    )
    assert h.series("flux") == [1.0]
    assert h.series("solar_wind_kms") == [2.0]
    assert h.series("lock_strength") == [3.0]
    assert h.series("phase_bias_rad") == [4.0]


def test_series_unknown_field_raises():
    h = TelemetryHistory(capacity=4)
    h.append(_sample(1.0))
    with pytest.raises(ValueError):
        h.series("temperature")


# --- normalized ------------------------------------------------------------


def test_normalized_empty():
    h = TelemetryHistory(capacity=4)
    assert h.normalized("flux") == []


def test_normalized_min_to_zero_max_to_one():
    h = TelemetryHistory(capacity=8)
    for v in (10.0, 20.0, 30.0):
        h.append(_sample(v))
    out = h.normalized("flux")
    assert out[0] == pytest.approx(0.0)
    assert out[-1] == pytest.approx(1.0)
    assert out[1] == pytest.approx(0.5)


def test_normalized_flat_series_to_half():
    h = TelemetryHistory(capacity=8)
    for _ in range(5):
        h.append(_sample(7.0))
    assert h.normalized("flux") == [0.5, 0.5, 0.5, 0.5, 0.5]


def test_normalized_explicit_lo_hi():
    h = TelemetryHistory(capacity=8)
    for v in (0.0, 50.0, 100.0):
        h.append(_sample(v))
    out = h.normalized("flux", lo=0.0, hi=100.0)
    assert out == pytest.approx([0.0, 0.5, 1.0])


def test_normalized_clamps_out_of_range():
    h = TelemetryHistory(capacity=8)
    for v in (-10.0, 50.0, 200.0):
        h.append(_sample(v))
    out = h.normalized("flux", lo=0.0, hi=100.0)
    # -10 -> below 0 clamps to 0; 200 -> above 100 clamps to 1.
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(0.5)
    assert out[2] == pytest.approx(1.0)


def test_normalized_zero_width_explicit_window_to_half():
    h = TelemetryHistory(capacity=8)
    for v in (1.0, 2.0, 3.0):
        h.append(_sample(v))
    assert h.normalized("flux", lo=5.0, hi=5.0) == [0.5, 0.5, 0.5]


def test_normalized_unknown_field_raises():
    h = TelemetryHistory(capacity=4)
    h.append(_sample(1.0))
    with pytest.raises(ValueError):
        h.normalized("nope")


def test_normalized_lo_greater_than_hi_raises():
    h = TelemetryHistory(capacity=4)
    h.append(_sample(1.0))
    with pytest.raises(ValueError):
        h.normalized("flux", lo=10.0, hi=0.0)


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_normalized_non_finite_bound_raises(bad):
    h = TelemetryHistory(capacity=4)
    h.append(_sample(1.0))
    with pytest.raises(ValueError):
        h.normalized("flux", lo=0.0, hi=bad)


# --- latest ----------------------------------------------------------------


def test_latest_none_when_empty():
    h = TelemetryHistory(capacity=4)
    assert h.latest() is None


def test_latest_returns_most_recent():
    h = TelemetryHistory(capacity=4)
    h.append(_sample(1.0))
    h.append(_sample(2.0))
    h.append(_sample(3.0))
    latest = h.latest()
    assert latest is not None
    assert latest.flux == 3.0


def test_latest_after_eviction():
    h = TelemetryHistory(capacity=2)
    for i in range(5):
        h.append(_sample(float(i)))
    latest = h.latest()
    assert latest is not None
    assert latest.flux == 4.0
