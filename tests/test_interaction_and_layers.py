"""Interaction target and dashboard layer planning tests.

These pure-Python contracts are the source of truth for the native OBS click
targets and the obspython dashboard helper. The C plugin mirrors these values.
"""

from __future__ import annotations

import pytest

from synthobs import (
    DashboardCommand,
    Feed,
    GraphMetric,
    TargetAction,
    dashboard_plan,
    parse,
    resolve_target_action,
)


def test_feed_targets_cover_all_seven_cells() -> None:
    width, height = 1400, 700
    expected = (
        Feed.WAVEFIELD,
        Feed.HEX_TUNNEL,
        Feed.INTERFERENCE,
        Feed.SPECTRAL_RINGS,
        Feed.SPIRAL_DRIFT,
        Feed.TELEMETRY_HUD,
        Feed.SOLAR_GRAPH,
    )
    hits = [
        resolve_target_action(
            (i + 0.5) * width / len(expected),
            height * 0.04,
            width,
            height,
            layer_count=4,
        )
        for i in range(len(expected))
    ]
    assert [h.action for h in hits] == [TargetAction.FEED] * len(expected)
    assert [h.feed for h in hits] == list(expected)


def test_layer_toggle_rail_uses_chronological_layer_index() -> None:
    hit = resolve_target_action(20, 300, 1000, 800, layer_count=5)
    assert hit.action is TargetAction.LAYER_TOGGLE
    assert hit.layer_index == 1
    assert hit.feed is None
    assert hit.marker is None


def test_marker_drop_uses_normalized_canvas_coordinates() -> None:
    hit = resolve_target_action(750, 500, 1000, 800, layer_count=3)
    assert hit.action is TargetAction.MARKER
    assert hit.marker == pytest.approx((0.75, 0.625))
    assert hit.feed is None


@pytest.mark.parametrize(
    "x,y,width,height,button",
    [
        (-1, 10, 100, 100, "left"),
        (10, -1, 100, 100, "left"),
        (101, 10, 100, 100, "left"),
        (10, 101, 100, 100, "left"),
        (10, 10, 0, 100, "left"),
        (10, 10, 100, 0, "left"),
        (10, 10, 100, 100, "right"),
        # non-finite coordinates: every comparison against NaN is False, so these
        # would slip past the bounds guard and either raise in int(x/w*len(Feed))
        # (tab row) or emit a MARKER carrying a poisoned NaN — both must fail closed.
        (float("nan"), 10, 100, 100, "left"),
        (10, float("nan"), 100, 100, "left"),
        (float("inf"), 10, 100, 100, "left"),
        (10, float("inf"), 100, 100, "left"),
        (float("nan"), float("nan"), 100, 100, "left"),
    ],
)
def test_invalid_or_non_left_clicks_fail_closed(
    x: float, y: float, width: int, height: int, button: str
) -> None:
    hit = resolve_target_action(x, y, width, height, button=button, layer_count=3)
    assert hit.action is TargetAction.NONE
    assert hit.feed is None
    assert hit.layer_index is None
    assert hit.marker is None


def test_nan_click_in_marker_region_does_not_poison_marker() -> None:
    # A NaN landing in the marker area (below tabs, right of the rail) must NOT
    # return a MARKER whose normalized coordinate is NaN — it must fail closed.
    import math

    hit = resolve_target_action(float("nan"), float("nan"), 1000, 800, layer_count=0)
    assert hit.action is TargetAction.NONE
    assert hit.marker is None
    # and a finite marker still works (the guard didn't over-reject)
    ok = resolve_target_action(750, 500, 1000, 800, layer_count=0)
    assert ok.action is TargetAction.MARKER
    assert ok.marker is not None and all(math.isfinite(c) for c in ok.marker)


def test_dashboard_plan_is_deterministic_and_normalized() -> None:
    plan = dashboard_plan("Awareness")
    assert plan.scene_name == "Awareness"
    assert [layer.name for layer in plan.layers] == [
        "Awareness / Wavefield",
        "Awareness / Telemetry HUD",
        "Awareness / Wind Speed",
        "Awareness / Wind Density",
        "Awareness / Wind Temperature",
        "Awareness / X-ray Flux",
        "Awareness / Kp Index",
    ]
    assert [layer.feed for layer in plan.layers] == [
        Feed.WAVEFIELD,
        Feed.TELEMETRY_HUD,
        Feed.SOLAR_GRAPH,
        Feed.SOLAR_GRAPH,
        Feed.SOLAR_GRAPH,
        Feed.SOLAR_GRAPH,
        Feed.SOLAR_GRAPH,
    ]
    assert [layer.graph_metric for layer in plan.layers[2:]] == list(GraphMetric)
    for layer in plan.layers:
        x, y, w, h = layer.bounds
        assert 0.0 <= x <= 1.0
        assert 0.0 <= y <= 1.0
        assert 0.0 < w <= 1.0
        assert 0.0 < h <= 1.0
        assert x + w <= 1.0
        assert y + h <= 1.0


def test_dashboard_plan_rejects_empty_scene_name() -> None:
    with pytest.raises(ValueError):
        dashboard_plan("   ")


def test_dashboard_command_parses_plan_and_build_actions() -> None:
    plan = parse("/dashboard plan --name=Awareness")
    build = parse('/dashboard build --name="Awareness Stream"')
    assert isinstance(plan, DashboardCommand)
    assert isinstance(build, DashboardCommand)
    assert plan.action == "plan"
    assert plan.name == "Awareness"
    assert build.action == "build"
    assert build.name == "Awareness Stream"


@pytest.mark.parametrize(
    "line",
    [
        "/dashboard",
        "/dashboard inspect --name=Awareness",
        "/dashboard plan",
        "/dashboard build --name=",
    ],
)
def test_dashboard_command_fail_closed(line: str) -> None:
    with pytest.raises(Exception):
        parse(line)


def test_obspython_dashboard_dry_run_returns_layer_summary() -> None:
    import importlib.util
    from pathlib import Path

    console_py = (
        Path(__file__).resolve().parents[1]
        / "plugin"
        / "synthobs"
        / "synthobs_console.py"
    )
    spec = importlib.util.spec_from_file_location("synthobs_console_dashboard", console_py)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    out = mod.apply_command("/dashboard plan --name=Awareness")
    assert "dashboard plan Awareness" in out
    assert "7 layers" in out
    assert "X-ray Flux" in out
    assert "Kp Index" in out

