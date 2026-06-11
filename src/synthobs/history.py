"""Telemetry history ring buffer for overlay waveform plotting.

This module keeps a fixed-size rolling window of recent telemetry samples so
the SynthOBS overlay can draw sparkline waveforms (solar wind, lock strength,
flux, phase bias). It is deliberately simple and integer/index-exact so the
native C plugin can mirror it with a fixed ``float[CAP]`` ring buffer plus a
head index and a count.

Design notes for the C mirror
-----------------------------
- Capacity is fixed at construction. The Python implementation uses a bounded
  ``collections.deque`` that evicts the oldest sample once full; the C mirror
  uses a fixed array with a ``head`` write index and a ``count`` clamped to
  ``CAP`` (overwriting the oldest slot on overflow, which is the same eviction
  behavior).
- ``series`` returns values in chronological order (oldest first). In C this
  means reading from ``(head - count + CAP) % CAP`` forward for ``count`` slots.
- ``normalized`` performs a single linear map ``(v - lo) / (hi - lo)`` clamped
  to ``[0, 1]``; a flat series (``hi == lo``) maps to a constant ``0.5``.

Pure stdlib only. No numpy, no third-party dependencies.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

__all__ = ["Sample", "TelemetryHistory"]

# Valid telemetry field names, matching the Sample dataclass fields.
_FIELDS: tuple[str, ...] = (
    "flux",
    "solar_wind_kms",
    "lock_strength",
    "phase_bias_rad",
)


@dataclass(frozen=True)
class Sample:
    """A single immutable telemetry sample.

    All four fields must be finite real numbers. A non-finite value (NaN or
    infinity) raises ``ValueError`` at construction time (fail-closed): the
    overlay must never plot garbage.

    Attributes:
        flux: Gateway flux magnitude (arbitrary units).
        solar_wind_kms: Solar wind speed in kilometers per second.
        lock_strength: Phase-lock strength, typically in ``[0, 1]``.
        phase_bias_rad: Phase bias in radians.
    """

    flux: float
    solar_wind_kms: float
    lock_strength: float
    phase_bias_rad: float

    def __post_init__(self) -> None:
        """Validate that every field is a finite real number."""
        for name in _FIELDS:
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(
                    f"Sample field {name!r} must be a real number, "
                    f"got {type(value).__name__}"
                )
            if not math.isfinite(float(value)):
                raise ValueError(f"Sample field {name!r} must be finite, got {value!r}")


class TelemetryHistory:
    """Fixed-size rolling window of recent telemetry samples.

    The most recent ``capacity`` samples are retained in chronological order
    (oldest first). Appending past capacity evicts the oldest sample, exactly
    mirroring a fixed-size ring buffer in C.

    Args:
        capacity: Maximum number of samples retained. Must be at least 2 so a
            waveform can actually be drawn.

    Raises:
        ValueError: If ``capacity`` is less than 2.
    """

    def __init__(self, capacity: int = 128) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise ValueError(f"capacity must be an int, got {type(capacity).__name__}")
        if capacity < 2:
            raise ValueError(f"capacity must be >= 2, got {capacity}")
        self._capacity: int = capacity
        self._buf: deque[Sample] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        """Return the fixed maximum number of retained samples."""
        return self._capacity

    def append(self, sample: Sample) -> None:
        """Append a sample, evicting the oldest if at capacity.

        Args:
            sample: The telemetry sample to append.

        Raises:
            ValueError: If ``sample`` is not a :class:`Sample` instance.
        """
        if not isinstance(sample, Sample):
            raise ValueError(f"append expects a Sample, got {type(sample).__name__}")
        self._buf.append(sample)

    def clear(self) -> None:
        """Remove all samples from the history."""
        self._buf.clear()

    def __len__(self) -> int:
        """Return the number of samples currently retained."""
        return len(self._buf)

    def latest(self) -> Sample | None:
        """Return the most recently appended sample, or ``None`` if empty."""
        if not self._buf:
            return None
        return self._buf[-1]

    def series(self, field: str) -> list[float]:
        """Return one field's recent values in chronological order.

        Args:
            field: One of ``'flux'``, ``'solar_wind_kms'``,
                ``'lock_strength'``, or ``'phase_bias_rad'``.

        Returns:
            The retained values for ``field``, oldest first. Empty if the
            history is empty.

        Raises:
            ValueError: If ``field`` is not a known telemetry field.
        """
        if field not in _FIELDS:
            raise ValueError(f"unknown field {field!r}; expected one of {_FIELDS}")
        return [float(getattr(s, field)) for s in self._buf]

    def normalized(
        self,
        field: str,
        lo: float | None = None,
        hi: float | None = None,
    ) -> list[float]:
        """Return one field's values linearly mapped to ``[0, 1]`` for plotting.

        Each value ``v`` is mapped as ``(v - lo) / (hi - lo)`` and clamped to
        ``[0, 1]`` so out-of-range values (when explicit ``lo``/``hi`` are
        given) saturate rather than escape the plot box.

        Behavior:
            - If ``lo`` and/or ``hi`` are omitted, the missing bound defaults to
              the series minimum / maximum respectively.
            - A flat series (``hi == lo``) maps every value to ``0.5`` (the
              midline), which is the natural rest position for a sparkline.
            - An empty history returns ``[]``.

        Args:
            field: One of the known telemetry fields (see :meth:`series`).
            lo: Optional lower bound mapped to ``0.0``. Defaults to series min.
            hi: Optional upper bound mapped to ``1.0``. Defaults to series max.

        Returns:
            Normalized values in ``[0, 1]``, chronological order. ``[]`` if
            empty.

        Raises:
            ValueError: If ``field`` is unknown, if a provided bound is not
                finite, or if ``lo > hi``.
        """
        values = self.series(field)
        if not values:
            return []

        low = min(values) if lo is None else float(lo)
        high = max(values) if hi is None else float(hi)

        if not math.isfinite(low) or not math.isfinite(high):
            raise ValueError(f"bounds must be finite, got lo={lo!r}, hi={hi!r}")
        if low > high:
            raise ValueError(f"lo must be <= hi, got lo={low!r}, hi={high!r}")

        span = high - low
        if span == 0.0:
            # Flat series (or zero-width explicit window): rest at midline.
            return [0.5 for _ in values]

        out: list[float] = []
        for v in values:
            t = (v - low) / span
            # Clamp to [0, 1] so explicit windows saturate cleanly.
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
            out.append(t)
        return out
