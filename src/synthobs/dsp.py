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
from dataclasses import dataclass

from .constants import INV_PHI, PHI

__all__ = [
    "AudioEnvelope",
    "audio_envelope",
    "video_calibrated_dims",
    "spatial_scale_matrix",
    "phi_soft_limit",
    "phi_soft_limit_sample",
]


@dataclass(frozen=True)
class AudioEnvelope:
    """Post-limiter buffer envelope for audio-reactive visual uniforms."""

    rms: float
    peak: float
    reactivity: float
    sample_count: int


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
    plugin. ``factor`` must be finite and non-zero.
    """
    if not math.isfinite(factor) or factor == 0:
        raise ValueError(f"scale factor must be finite and non-zero, got {factor}")
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
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError(f"threshold must be finite and positive, got {threshold}")
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


def audio_envelope(samples: Iterable[float], threshold: float = 1.0) -> AudioEnvelope:
    """Measure the post-limiter RMS/peak envelope for audio-reactive visuals.

    The envelope is computed after the same φ soft limiter used by
    :func:`phi_soft_limit`, so non-finite inputs are absorbed into finite output and
    the reported peak never exceeds ``threshold``. ``reactivity`` is a bounded
    ``[0, 1]`` scalar derived from RMS/threshold and φ-scaled for shader use.
    """
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError(f"threshold must be finite and positive, got {threshold}")

    count = 0
    sum_sq = 0.0
    peak = 0.0
    for sample in samples:
        limited = phi_soft_limit_sample(float(sample), threshold)
        mag = abs(limited)
        peak = max(peak, mag)
        sum_sq += limited * limited
        count += 1

    if count == 0:
        return AudioEnvelope(rms=0.0, peak=0.0, reactivity=0.0, sample_count=0)

    rms = math.sqrt(sum_sq / count)
    reactivity = min(1.0, max(0.0, (rms / threshold) * PHI))
    return AudioEnvelope(rms=rms, peak=peak, reactivity=reactivity, sample_count=count)


def is_monotone_non_decreasing(values: Sequence[float]) -> bool:
    """Helper used by tests: True iff ``values`` never decreases."""
    return all(b >= a - 1e-12 for a, b in zip(values, values[1:]))
