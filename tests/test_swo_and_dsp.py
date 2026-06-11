"""SWO calibration (ISC-19..25) and FractiSynth DSP (ISC-26..32) tests."""

from __future__ import annotations

import math

import pytest
from synthobs.constants import INV_PHI, PHI
from synthobs.dsp import (
    is_monotone_non_decreasing,
    phi_soft_limit,
    phi_soft_limit_sample,
    spatial_scale_matrix,
    video_calibrated_dims,
)
from synthobs.swo import SolarWavefieldOscillator, phase_vector


# --- SWO -----------------------------------------------------------------
def test_phase_vector_formula() -> None:  # ISC-19, ISC-23
    assert phase_vector(130.0, 2) == (130.0 / 2.0) * PHI
    # deterministic
    assert phase_vector(130.0, 2) == phase_vector(130.0, 2)


def test_calibrate_sets_vector() -> None:  # ISC-19
    swo = SolarWavefieldOscillator()
    assert swo.calibrate(130.0, 2) is True
    assert swo.is_calibrated
    assert swo.system_phase_vector == pytest.approx((130.0 / 2) * PHI)


def test_starts_uncalibrated() -> None:  # ISC-25
    swo = SolarWavefieldOscillator()
    assert swo.is_calibrated is False
    assert swo.system_phase_vector is None
    assert swo.hold_vector() is None


@pytest.mark.parametrize("flux,spots", [(0.0, 3), (-1.0, 3)])
def test_calibrate_bad_flux_holds(flux, spots) -> None:  # ISC-20
    swo = SolarWavefieldOscillator()
    swo.calibrate(100.0, 2)  # establish a good vector
    good = swo.system_phase_vector
    assert swo.calibrate(flux, spots) is False
    assert swo.is_calibrated is False
    assert swo.system_phase_vector == good  # HOLD last good vector


@pytest.mark.parametrize("spots", [0, -2])
def test_calibrate_bad_spots_holds(spots) -> None:  # ISC-21
    swo = SolarWavefieldOscillator()
    swo.calibrate(100.0, 2)
    good = swo.system_phase_vector
    assert swo.calibrate(120.0, spots) is False  # no div-by-zero
    assert swo.system_phase_vector == good
    assert math.isfinite(swo.system_phase_vector)


def test_hold_state_after_good_then_bad() -> None:  # ISC-22
    swo = SolarWavefieldOscillator()
    swo.calibrate(150.0, 3)
    held = swo.system_phase_vector
    swo.calibrate(-5.0, 3)  # connectivity-style failure
    assert swo.hold_vector() == held


@pytest.mark.parametrize("flux", [70.0, 130.0, 250.0, 400.0])
@pytest.mark.parametrize("spots", [1, 3, 7, 12])
def test_phase_vector_finite_grid(flux, spots) -> None:  # ISC-24
    swo = SolarWavefieldOscillator()
    assert swo.calibrate(flux, spots) is True
    assert math.isfinite(swo.system_phase_vector)
    assert swo.system_phase_vector > 0


# --- video DSP -----------------------------------------------------------
@pytest.mark.parametrize("w,h", [(1920, 1080), (2, 2), (100, 50), (4096, 2160)])
def test_video_calibrated_dims(w, h) -> None:  # ISC-26
    cw, ch = video_calibrated_dims(w, h)
    assert cw == int(round(w * INV_PHI))
    assert ch == int(round(h * INV_PHI))
    assert cw >= 1 and ch >= 1


def test_video_dims_reject_negative() -> None:
    with pytest.raises(ValueError):
        video_calibrated_dims(-1, 10)


def test_spatial_scale_matrix() -> None:  # ISC-32
    m = spatial_scale_matrix(PHI)
    assert m[0][0] == pytest.approx(INV_PHI)
    assert m[1][1] == pytest.approx(INV_PHI)
    assert m[2][2] == 1.0
    with pytest.raises(ValueError):
        spatial_scale_matrix(0.0)


# --- audio soft limiter --------------------------------------------------
def test_soft_limit_monotone() -> None:  # ISC-27
    xs = [i * 0.05 for i in range(0, 80)]  # 0 .. 3.95
    ys = phi_soft_limit(xs, threshold=1.0)
    assert is_monotone_non_decreasing(ys)


@pytest.mark.parametrize("x", [0.0, 0.3, 0.9, 1.0, 5.0, 100.0, -100.0, 1e9])
def test_soft_limit_ceiling(x) -> None:  # ISC-28, ISC-31
    y = phi_soft_limit_sample(x, threshold=1.0)
    assert abs(y) <= 1.0 + 1e-12
    assert math.isfinite(y)


def test_soft_limit_identity_below_knee() -> None:  # ISC-29
    knee = INV_PHI  # threshold 1.0 → knee = 1/φ
    for x in [0.0, 0.1, 0.3, knee - 0.01]:
        assert phi_soft_limit_sample(x, 1.0) == pytest.approx(x)


def test_soft_limit_knee_uses_inv_phi() -> None:  # ISC-30
    # exactly at the knee the curve is still the identity; just past it, it bends.
    knee = 1.0 * INV_PHI
    assert phi_soft_limit_sample(knee, 1.0) == pytest.approx(knee)
    just_past = phi_soft_limit_sample(knee + 0.2, 1.0)
    assert just_past < knee + 0.2  # compressed
    assert just_past > knee  # but still increasing


def test_soft_limit_nan_safe() -> None:  # ISC-31
    assert phi_soft_limit_sample(float("nan"), 1.0) == 0.0
    assert abs(phi_soft_limit_sample(float("inf"), 1.0)) == 1.0
    assert phi_soft_limit_sample(float("-inf"), 1.0) == -1.0


def test_soft_limit_sign_preserving() -> None:
    assert phi_soft_limit_sample(-2.0, 1.0) < 0
    assert phi_soft_limit_sample(2.0, 1.0) > 0


def test_soft_limit_bad_threshold() -> None:
    with pytest.raises(ValueError):
        phi_soft_limit_sample(1.0, 0.0)
