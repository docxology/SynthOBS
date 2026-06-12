"""Interactive target geometry for the SynthOBS overlay source.

This module is the Python source of truth for click targets mirrored by the native
``fractisynth_console`` source: seven feed tabs, a layer-toggle rail, and marker
drops in the remaining canvas. Invalid input fails closed to ``TargetAction.NONE``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum

__all__ = [
    "Feed",
    "GraphMetric",
    "TargetAction",
    "TargetHit",
    "resolve_target_action",
]

FEED_TAB_HEIGHT_FRACTION = 0.09
LAYER_RAIL_WIDTH_FRACTION = 0.07


class Feed(IntEnum):
    """Native ``fractisynth_console`` feed identifiers."""

    WAVEFIELD = 0
    HEX_TUNNEL = 1
    INTERFERENCE = 2
    SPECTRAL_RINGS = 3
    SPIRAL_DRIFT = 4
    TELEMETRY_HUD = 5
    SOLAR_GRAPH = 6


class GraphMetric(IntEnum):
    """Solar Graph metric identifiers."""

    WIND_SPEED = 0
    WIND_DENSITY = 1
    WIND_TEMPERATURE = 2
    XRAY_FLUX = 3
    KP_INDEX = 4


class TargetAction(str, Enum):
    """Resolved action for one canvas click."""

    NONE = "none"
    FEED = "feed"
    LAYER_TOGGLE = "layer_toggle"
    MARKER = "marker"


@dataclass(frozen=True)
class TargetHit:
    """Resolved click target.

    ``marker`` is normalized ``(x, y)`` in canvas coordinates.
    """

    action: TargetAction
    feed: Feed | None = None
    layer_index: int | None = None
    marker: tuple[float, float] | None = None


def _none() -> TargetHit:
    return TargetHit(TargetAction.NONE)


def resolve_target_action(
    x: float,
    y: float,
    width: int,
    height: int,
    *,
    button: str = "left",
    show_targets: bool = True,
    layer_count: int = 0,
) -> TargetHit:
    """Resolve one overlay click into a feed switch, layer toggle, marker, or none.

    Geometry is intentionally simple and deterministic:
    - top 9% of the canvas is split into seven feed tabs;
    - left 7% below the tabs is a layer-toggle rail;
    - the remaining area drops a normalized marker.
    """

    if (
        button != "left"
        or not show_targets
        or width <= 0
        or height <= 0
        or x < 0.0
        or y < 0.0
        or x >= float(width)
        or y >= float(height)
    ):
        return _none()

    tab_h = height * FEED_TAB_HEIGHT_FRACTION
    if y < tab_h:
        cell = int(x / float(width) * len(Feed))
        cell = min(max(cell, 0), len(Feed) - 1)
        return TargetHit(TargetAction.FEED, feed=Feed(cell))

    if layer_count > 0 and x < width * LAYER_RAIL_WIDTH_FRACTION:
        usable_h = height - tab_h
        idx = int((y - tab_h) / usable_h * layer_count)
        idx = min(max(idx, 0), layer_count - 1)
        return TargetHit(TargetAction.LAYER_TOGGLE, layer_index=idx)

    return TargetHit(TargetAction.MARKER, marker=(x / float(width), y / float(height)))

