"""FractiSynth DSP — φ-scaled audio harmonic balancing and video spatial scaling.

These are the Python mirrors of the native FractiSynth audio/video filter callbacks.

Audio: instead of harsh linear peak limiting that clips frequencies, sample buffers
are compressed along a smooth recursive curve scaled by ``1/φ``. Below a knee the
signal passes through untouched (no premature distortion); above it, the excess is
soft-compressed so the output asymptotically approaches — but never exceeds — the
ceiling, maximizing acoustic presence while preventing compression fatigue.

Video: before frames reach the hardware encoder, spatial bounds are scaled against
the EGS fractal constant — ``calibrated = source / φ`` — establishing the harmonic
bounding box used by the geometric transform pass.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from .constants import INV_PHI, PHI

__all__ = [
    "video_calibrated_dims",
    "spatial_scale_matrix",
    "phi_soft_limit",
    "phi_soft_limit_sample",
]


def video_calibrated_dims(width: int, height: int) -> tuple[int, int]:
    """Calibrated harmonic bounding box ``(w/φ, h/φ)`` rounded to ints (ISC-26).

    Both dimensions are at least 1 for inputs ``>= 2`` so the transform pass never
    collapses a source to zero extent.
    """
    if width < 0 or height < 0:
        raise ValueError(f"dims must be non-negative, got {width}x{height}")
    cw = int(round(width * INV_PHI))
    ch = int(round(height * INV_PHI))
    if width >= 1:
        cw = max(1, cw)
    if height >= 1:
        ch = max(1, ch)
    return cw, ch


def spatial_scale_matrix(factor: float = PHI) -> list[list[float]]:
    """3×3 homogeneous matrix that scales by ``1/factor`` (ISC-32).

    With the default ``factor = φ`` this scales geometry to ``1/φ`` of its source
    extent — the calibrated bounding box used by ``video_render`` in the native
    plugin. ``factor`` must be non-zero.
    """
    if factor == 0:
        raise ValueError("scale factor must be non-zero")
    s = 1.0 / factor
    return [
        [s, 0.0, 0.0],
        [0.0, s, 0.0],
        [0.0, 0.0, 1.0],
    ]


def phi_soft_limit_sample(x: float, threshold: float) -> float:
    """Soft-limit a single sample along the φ-scaled recursive knee curve.

    For ``|x| <= knee`` (where ``knee = threshold · 1/φ``) the sample passes through
    unchanged. Above the knee the excess ``e = |x| − knee`` is compressed by
    ``headroom · tanh(e / (headroom·φ))`` so the magnitude approaches but never
    reaches ``threshold``. The curve is monotone, sign-preserving, and NaN/Inf-safe
    (ISC-27..31).
    """
    if threshold <= 0:
        raise ValueError(f"threshold must be positive, got {threshold}")
    if not math.isfinite(x):
        # Defensive: a non-finite input is clamped to the ceiling, never propagated.
        return math.copysign(threshold, x) if not math.isnan(x) else 0.0
    sign = -1.0 if x < 0 else 1.0
    mag = abs(x)
    knee = threshold * INV_PHI
    if mag <= knee:
        return x  # identity region — no premature distortion
    headroom = threshold - knee  # == threshold · (1 − 1/φ) == threshold · 1/φ²
    excess = mag - knee
    compressed = headroom * math.tanh(excess / (headroom * PHI))
    out = sign * (knee + compressed)
    # Strict ceiling guarantee.
    if abs(out) > threshold:
        out = sign * threshold
    return out


def phi_soft_limit(samples: Iterable[float], threshold: float = 1.0) -> list[float]:
    """Apply :func:`phi_soft_limit_sample` across a buffer (ISC-27..31).

    Monotone non-decreasing in input magnitude, bounded by ``threshold``, identity
    well below the knee, and free of NaN/Inf for any finite input.
    """
    return [phi_soft_limit_sample(float(s), threshold) for s in samples]


def is_monotone_non_decreasing(values: Sequence[float]) -> bool:
    """Helper used by tests: True iff ``values`` never decreases."""
    return all(b >= a - 1e-12 for a, b in zip(values, values[1:]))
