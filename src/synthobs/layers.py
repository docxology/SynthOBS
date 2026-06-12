"""Deterministic SynthOBS dashboard layer planning.

The obspython adapter consumes this pure plan to build a reusable awareness-stream
dashboard without inventing OBS-specific layout policy in the script layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .interaction import Feed, GraphMetric

__all__ = ["DashboardLayer", "DashboardPlan", "dashboard_plan"]


@dataclass(frozen=True)
class DashboardLayer:
    """One planned OBS source layer, with normalized scene bounds."""

    name: str
    feed: Feed
    graph_metric: GraphMetric | None
    bounds: tuple[float, float, float, float]
    visible: bool = True


@dataclass(frozen=True)
class DashboardPlan:
    """A full deterministic layer plan for one OBS scene."""

    scene_name: str
    layers: tuple[DashboardLayer, ...]


def dashboard_plan(scene_name: str) -> DashboardPlan:
    """Create the standard seven-layer awareness dashboard plan."""

    name = scene_name.strip()
    if not name:
        raise ValueError("dashboard scene name must be non-empty")

    layers = (
        DashboardLayer(f"{name} / Wavefield", Feed.WAVEFIELD, None, (0.0, 0.0, 1.0, 1.0)),
        DashboardLayer(f"{name} / Telemetry HUD", Feed.TELEMETRY_HUD, None, (0.02, 0.08, 0.38, 0.38)),
        DashboardLayer(f"{name} / Wind Speed", Feed.SOLAR_GRAPH, GraphMetric.WIND_SPEED, (0.42, 0.08, 0.27, 0.26)),
        DashboardLayer(f"{name} / Wind Density", Feed.SOLAR_GRAPH, GraphMetric.WIND_DENSITY, (0.71, 0.08, 0.27, 0.26)),
        DashboardLayer(f"{name} / Wind Temperature", Feed.SOLAR_GRAPH, GraphMetric.WIND_TEMPERATURE, (0.42, 0.38, 0.27, 0.26)),
        DashboardLayer(f"{name} / X-ray Flux", Feed.SOLAR_GRAPH, GraphMetric.XRAY_FLUX, (0.71, 0.38, 0.27, 0.26)),
        DashboardLayer(f"{name} / Kp Index", Feed.SOLAR_GRAPH, GraphMetric.KP_INDEX, (0.42, 0.68, 0.56, 0.24)),
    )
    return DashboardPlan(scene_name=name, layers=layers)

