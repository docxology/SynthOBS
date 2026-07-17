"""Tests for constants (ISC-1,2) and the Goldilocks layout matrix (ISC-3..10)."""

from __future__ import annotations

import math

import pytest
from synthobs.constants import EGS_CONSTANT, INV_PHI, INV_PHI_SQ, PHI, PHI_C_LITERAL
from synthobs.layout import (
    Region,
    Viewport,
    assemble_viewport,
    golden_spiral_points,
    golden_split,
    recursive_subdivision,
)


# --- constants -----------------------------------------------------------
def test_phi_value_single_source() -> None:  # ISC-1
    assert abs(PHI - 1.6180339887498949) < 1e-12
    assert PHI == (1.0 + 5.0**0.5) / 2.0
    assert EGS_CONSTANT == PHI  # brand alias is identical


def test_inv_phi() -> None:  # ISC-2
    assert abs(INV_PHI - 0.6180339887498949) < 1e-12
    assert abs(INV_PHI - (PHI - 1.0)) < 1e-12  # 1/φ = φ−1
    assert abs(INV_PHI_SQ - (1.0 - INV_PHI)) < 1e-12  # 1/φ² = 1−1/φ


def test_phi_c_literal_matches_python() -> None:  # ISC-60 (Python side)
    assert abs(float(PHI_C_LITERAL) - PHI) < 1e-9


# --- golden_split --------------------------------------------------------
def test_golden_split_ratio() -> None:  # ISC-3
    major, minor = golden_split(1000)
    assert major + minor == 1000
    assert abs(major / 1000 - INV_PHI) < 0.001


@pytest.mark.parametrize("total", list(range(0, 5000, 7)))
def test_golden_split_integer_exact(total: int) -> None:  # ISC-4
    major, minor = golden_split(total)
    assert major + minor == total  # no lost pixels
    assert major >= 0 and minor >= 0  # ISC-10


def test_golden_split_negative_rejected() -> None:
    with pytest.raises(ValueError):
        golden_split(-1)


# --- recursive_subdivision ----------------------------------------------
@pytest.mark.parametrize("depth", [1, 2, 3, 5, 8])
def test_recursive_subdivision_sums(depth: int) -> None:  # ISC-5
    sizes = recursive_subdivision(1597, depth)
    assert len(sizes) == depth
    assert sum(sizes) == 1597


def test_recursive_subdivision_ratio_approaches_inv_phi() -> None:  # ISC-6
    sizes = recursive_subdivision(100000, 6)
    # The golden property: each cut takes 1/φ of the span it was cut from, i.e.
    # sizes[i] / sum(sizes[i:]) ≈ 1/φ for every interior cut.
    for i in range(len(sizes) - 1):
        span = sum(sizes[i:])
        assert abs(sizes[i] / span - INV_PHI) < 0.01


def test_recursive_subdivision_bad_depth() -> None:
    with pytest.raises(ValueError):
        recursive_subdivision(100, 0)


# --- viewport assembly ---------------------------------------------------
def test_viewport_fractions() -> None:  # ISC-7
    vp = assemble_viewport(1920, 1080)
    assert abs(vp.primary.width / 1920 - INV_PHI) < 0.001
    # primary occupies the full height, so its area fraction ≈ 61.8%
    assert abs(vp.primary_fraction() - INV_PHI) < 0.001


@pytest.mark.parametrize(
    "w,h", [(1920, 1080), (1280, 720), (3840, 2160), (640, 480), (101, 57)]
)
def test_viewport_tiles_exactly(w: int, h: int) -> None:  # ISC-8, ISC-10
    vp = assemble_viewport(w, h)
    assert vp.tiles_exactly()
    for r in vp.regions():
        assert r.width > 0 and r.height > 0  # no zero/negative dims


def test_viewport_rejects_nonpositive() -> None:
    with pytest.raises(ValueError):
        assemble_viewport(0, 100)


def test_region_overlap_and_area() -> None:
    a = Region(0, 0, 10, 10)
    b = Region(5, 5, 10, 10)
    c = Region(10, 0, 5, 5)
    assert a.area == 100
    assert a.overlaps(b)
    assert not a.overlaps(c)  # shares an edge only


def test_viewport_tiles_exactly_rejects_area_mismatch_and_overlap() -> None:
    canvas = Region(0, 0, 10, 10)
    assert not Viewport(
        canvas=canvas,
        primary=Region(0, 0, 4, 10),
        console=Region(4, 0, 3, 10),
        telemetry=Region(7, 0, 2, 10),
    ).tiles_exactly()
    assert not Viewport(
        canvas=canvas,
        primary=Region(0, 0, 5, 10),
        console=Region(4, 0, 5, 10),
        telemetry=Region(9, 0, 1, 10),
    ).tiles_exactly()
    assert not Viewport(
        canvas=canvas,
        primary=Region(-1, 0, 4, 10),
        console=Region(3, 0, 4, 10),
        telemetry=Region(7, 0, 3, 10),
    ).tiles_exactly()


# --- golden spiral -------------------------------------------------------
def test_golden_spiral_growth() -> None:  # ISC-9
    pts = golden_spiral_points(17)
    assert len(pts) == 17
    # radius after one full quarter-turn (4 samples) grows by φ
    r0 = math.hypot(*pts[0])
    r4 = math.hypot(*pts[4])
    assert abs(r4 / r0 - PHI) < 1e-6


def test_golden_spiral_empty() -> None:
    assert golden_spiral_points(0) == []
    with pytest.raises(ValueError):
        golden_spiral_points(-1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"a": float("nan")},
        {"a": float("inf")},
        {"start_theta": float("nan")},
        {"start_theta": float("-inf")},
    ],
)
def test_golden_spiral_rejects_nonfinite_parameters(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        golden_spiral_points(2, **kwargs)
