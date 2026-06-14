"""Pure verification helpers for live SynthOBS proof artifacts.

Scripts may do OBS/websocket/image I/O, but the scoring rules for live gates live
here so they can be tested without a running OBS process.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

__all__ = [
    "AUDIO_METER_TOP_FRACTION",
    "GateResult",
    "RoiDelta",
    "audio_meter_roi",
    "score_roi_delta",
    "score_audio_meter_delta",
]

AUDIO_METER_TOP_FRACTION = 0.955
_GATE_STATUSES = frozenset(("pass", "fail", "skip"))


@dataclass(frozen=True)
class GateResult:
    """One live-verification gate outcome for manifests and tests."""

    status: str
    reason: str
    metrics: Mapping[str, int | float | str | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in _GATE_STATUSES:
            raise ValueError(f"gate status must be one of {_GATE_STATUSES}, got {self.status!r}")
        if not self.reason.strip():
            raise ValueError("gate reason must be non-empty")
        for key, value in self.metrics.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"metric keys must be non-empty strings, got {key!r}")
            if not isinstance(value, (int, float, str, bool)):
                raise ValueError(f"metric {key!r} has non-scalar value {value!r}")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"metric {key!r} must be finite, got {value!r}")

    @classmethod
    def passed(
        cls, reason: str, **metrics: int | float | str | bool
    ) -> "GateResult":
        return cls("pass", reason, metrics)

    @classmethod
    def failed(
        cls, reason: str, **metrics: int | float | str | bool
    ) -> "GateResult":
        return cls("fail", reason, metrics)

    @classmethod
    def skipped(
        cls, reason: str, **metrics: int | float | str | bool
    ) -> "GateResult":
        return cls("skip", reason, metrics)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True)
class RoiDelta:
    """Mean absolute color-channel difference inside a rectangular ROI."""

    width: int
    height: int
    channels: int
    roi: tuple[int, int, int, int]
    compared_pixels: int
    mean_abs_delta: float
    max_abs_delta: int
    threshold: float
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "width": self.width,
            "height": self.height,
            "channels": self.channels,
            "roi": list(self.roi),
            "compared_pixels": self.compared_pixels,
            "mean_abs_delta": self.mean_abs_delta,
            "max_abs_delta": self.max_abs_delta,
            "threshold": self.threshold,
            "passed": self.passed,
        }


def audio_meter_roi(width: int, height: int) -> tuple[int, int, int, int]:
    """Return the shader-pinned bottom audio-meter ROI.

    The console shader draws the meter when ``uv.y > 0.955``. The returned tuple
    is ``(x, y, w, h)`` in integer image pixels.
    """

    _validate_dims(width, height)
    top = int(height * AUDIO_METER_TOP_FRACTION)
    top = min(max(top, 0), height - 1)
    return (0, top, width, height - top)


def score_audio_meter_delta(
    before: bytes,
    after: bytes,
    width: int,
    height: int,
    *,
    channels: int = 4,
    threshold: float = 8.0,
) -> RoiDelta:
    """Score a silent-vs-tone capture pair in the shader's audio-meter ROI."""

    return score_roi_delta(
        before,
        after,
        width,
        height,
        channels=channels,
        roi=audio_meter_roi(width, height),
        threshold=threshold,
    )


def score_roi_delta(
    before: bytes,
    after: bytes,
    width: int,
    height: int,
    *,
    channels: int = 4,
    roi: tuple[int, int, int, int],
    threshold: float,
) -> RoiDelta:
    """Return the mean absolute RGB delta inside ``roi``.

    Alpha is ignored for RGBA input because OBS screenshot alpha can be constant
    even when rendered pixels change. Invalid buffers, dimensions, channels,
    ROIs, or thresholds raise ``ValueError`` instead of producing a soft pass.
    """

    _validate_dims(width, height)
    if channels not in (3, 4):
        raise ValueError(f"channels must be 3 or 4, got {channels!r}")
    if not math.isfinite(threshold) or threshold < 0.0:
        raise ValueError(f"threshold must be finite and >= 0, got {threshold!r}")
    expected = width * height * channels
    if len(before) != expected:
        raise ValueError(f"before image is {len(before)} bytes, expected {expected}")
    if len(after) != expected:
        raise ValueError(f"after image is {len(after)} bytes, expected {expected}")

    x0, y0, rw, rh = _validate_roi(roi, width, height)
    components = min(channels, 3)
    total = 0
    count = 0
    max_delta = 0
    for y in range(y0, y0 + rh):
        row = y * width * channels
        for x in range(x0, x0 + rw):
            base = row + x * channels
            for channel in range(components):
                delta = abs(before[base + channel] - after[base + channel])
                total += delta
                count += 1
                if delta > max_delta:
                    max_delta = delta

    mean = total / float(count)
    return RoiDelta(
        width=width,
        height=height,
        channels=channels,
        roi=(x0, y0, rw, rh),
        compared_pixels=rw * rh,
        mean_abs_delta=mean,
        max_abs_delta=max_delta,
        threshold=threshold,
        passed=mean >= threshold,
    )


def _validate_dims(width: int, height: int) -> None:
    if not isinstance(width, int) or not isinstance(height, int):
        raise ValueError(f"width/height must be integers, got {width!r}x{height!r}")
    if width <= 0 or height <= 0:
        raise ValueError(f"width/height must be positive, got {width}x{height}")


def _validate_roi(
    roi: tuple[int, int, int, int], width: int, height: int
) -> tuple[int, int, int, int]:
    if len(roi) != 4:
        raise ValueError(f"roi must be (x, y, w, h), got {roi!r}")
    x, y, w, h = roi
    if not all(isinstance(v, int) for v in roi):
        raise ValueError(f"roi values must be integers, got {roi!r}")
    if w <= 0 or h <= 0:
        raise ValueError(f"roi width/height must be positive, got {roi!r}")
    if x < 0 or y < 0 or x + w > width or y + h > height:
        raise ValueError(f"roi {roi!r} is outside image bounds {width}x{height}")
    return x, y, w, h
