"""SynthOBS Console — the Vessel Console as an OBS Python script.

Load this from OBS via Tools → Scripts. It wraps standard OBS operations in the
Goldilocks layout matrix and the 3-mode console (Observatory / Laboratory /
Expedition), driving everything from the tested SynthOBS engine. The persistent
command line is exposed as a script text property that accepts the grammar:

    /mode --observatory | --lab | --ship
    /transducer bind <source> --ratio=1.618034
    /swo calibrate --flux=130 --spots=3 --target=AR4465
    /dashboard plan --name=Awareness
    /dashboard build --name=Awareness

The engine (../../src/synthobs) is the source of truth; this script is a thin
obspython adapter. ``obspython`` is only available inside OBS, so it is imported
behind a guard and the file stays importable / py_compile-valid anywhere.
"""

from __future__ import annotations

import os
import sys

# --- make the tested engine importable inside OBS's embedded interpreter -----
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthobs import (  # noqa: E402  (path set above)
    CommandError,
    DashboardCommand,
    Mode,
    SynthEngine,
    assemble_viewport,
    dashboard_plan,
    parse,
)
from synthobs.commands import BindCommand, CalibrateCommand, ModeCommand  # noqa: E402

try:  # obspython exists only inside OBS
    import obspython as obs  # type: ignore
    _IN_OBS = True
except ImportError:  # importable everywhere else (tests, py_compile)
    obs = None  # type: ignore
    _IN_OBS = False


# Single engine instance for the broadcast environment.
ENGINE = SynthEngine(mode=Mode.OBSERVATORY)
_DASHBOARD_HOTKEYS = []
_DASHBOARD_ITEMS = []
_DASHBOARD_ACTIVE = 0
_DEFAULT_CANVAS = (1920, 1080)
_DEFAULT_SOURCE = (1280, 720)


def apply_command(line: str) -> str:
    """Parse and apply one command line; return a human-readable status string.

    Pure with respect to OBS — testable without OBS present. Mode switches update
    the engine; bind/calibrate adjust the transducer / oscillator.
    """
    try:
        cmd = parse(line)
    except CommandError as exc:
        return f"ERROR: {exc}"

    if isinstance(cmd, ModeCommand):
        ENGINE.switch_mode(cmd.target)
        if _IN_OBS:
            _sync_scene_for_mode(cmd.target)
        return f"mode → {cmd.target.value}"
    if isinstance(cmd, BindCommand):
        return f"transducer bound {cmd.source} @ ratio {cmd.ratio:.6f}"
    if isinstance(cmd, CalibrateCommand):
        from synthobs.telemetry import SolarTelemetry
        from datetime import datetime, timezone

        telemetry = SolarTelemetry(
            flux=cmd.flux,
            sunspots=cmd.spots,
            source=f"manual:{cmd.target or 'override'}",
            observed_at=datetime.now(timezone.utc),
        )
        # Honor the engine's authoritative fail-closed bool. A finite-but-extreme
        # flux (e.g. flux·φ overflowing to inf) passes the grammar parser but is
        # correctly REFUSED by the SWO (update→False, phase_vector stays None);
        # formatting None as :.4f would crash the OBS command handler.
        ok = ENGINE.update(telemetry)
        vector = ENGINE.phase_vector
        if ok and vector is not None:
            return f"SWO calibrated: phase_vector={vector:.4f}"
        return "SWO held: telemetry refused (non-finite vector) — last verified vector retained"
    if isinstance(cmd, DashboardCommand):
        plan = dashboard_plan(cmd.name)
        if cmd.action == "build" and _IN_OBS:
            _build_dashboard(plan)
            return _dashboard_summary(plan, "built")
        return _dashboard_summary(plan, cmd.action)
    return "ok"  # pragma: no cover - exhaustive above


def viewport_for_canvas(width: int, height: int):
    """Goldilocks viewport for the current OBS canvas (primary 61.8%)."""
    return assemble_viewport(width, height)


def dashboard_layer_transform(
    bounds,
    canvas_width: int,
    canvas_height: int,
    source_width: int = _DEFAULT_SOURCE[0],
    source_height: int = _DEFAULT_SOURCE[1],
):
    """Map normalized dashboard bounds into OBS position/scale values."""
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError(f"canvas dims must be positive, got {canvas_width}x{canvas_height}")
    if source_width <= 0 or source_height <= 0:
        raise ValueError(f"source dims must be positive, got {source_width}x{source_height}")
    x, y, w, h = bounds
    return (
        x * float(canvas_width),
        y * float(canvas_height),
        (w * float(canvas_width)) / float(source_width),
        (h * float(canvas_height)) / float(source_height),
    )


def _dashboard_summary(plan, action: str) -> str:
    labels = ", ".join(layer.name.split(" / ", 1)[-1] for layer in plan.layers)
    return f"dashboard {action} {plan.scene_name}: {len(plan.layers)} layers: {labels}"


# --- obspython adapter layer (only exercised inside OBS) ---------------------
def _register_dashboard_hotkeys() -> None:  # pragma: no cover - needs OBS
    if _DASHBOARD_HOTKEYS:
        return

    def _prev(pressed):
        if pressed:
            _cycle_dashboard_layer(-1)

    def _next(pressed):
        if pressed:
            _cycle_dashboard_layer(1)

    _DASHBOARD_HOTKEYS.append(
        obs.obs_hotkey_register_frontend(
            "synthobs.dashboard.prev_layer", "SynthOBS Dashboard: Previous Layer", _prev
        )
    )
    _DASHBOARD_HOTKEYS.append(
        obs.obs_hotkey_register_frontend(
            "synthobs.dashboard.next_layer", "SynthOBS Dashboard: Next Layer", _next
        )
    )


def _cycle_dashboard_layer(delta: int) -> None:  # pragma: no cover - needs OBS
    global _DASHBOARD_ACTIVE
    if not _DASHBOARD_ITEMS:
        return
    _DASHBOARD_ACTIVE = (_DASHBOARD_ACTIVE + delta) % len(_DASHBOARD_ITEMS)
    for idx, item in enumerate(_DASHBOARD_ITEMS):
        # Keep the wavefield base layer visible; cycle the overlays above it.
        obs.obs_sceneitem_set_visible(item, idx == 0 or idx == _DASHBOARD_ACTIVE)


def _scene_for_dashboard(name: str):  # pragma: no cover - needs OBS
    scene_source = obs.obs_get_source_by_name(name)
    if scene_source:
        scene = obs.obs_scene_from_source(scene_source)
        return scene, scene_source
    scene = obs.obs_scene_create(name)
    scene_source = obs.obs_scene_get_source(scene)
    return scene, scene_source


def _obs_canvas_size():  # pragma: no cover - needs OBS
    if not _IN_OBS:
        return _DEFAULT_CANVAS
    try:
        info = obs.obs_video_info()
        if obs.obs_get_video_info(info):
            width = int(getattr(info, "base_width", 0))
            height = int(getattr(info, "base_height", 0))
            if width > 0 and height > 0:
                return width, height
    except Exception as exc:
        obs.script_log(obs.LOG_WARNING, f"[SynthOBS] canvas size fallback: {exc}")
    return _DEFAULT_CANVAS


def _build_dashboard(plan) -> None:  # pragma: no cover - needs OBS
    global _DASHBOARD_ACTIVE
    _DASHBOARD_ITEMS.clear()
    scene, scene_source = _scene_for_dashboard(plan.scene_name)
    try:
        canvas_width, canvas_height = _obs_canvas_size()
        for layer in plan.layers:
            settings = obs.obs_data_create()
            obs.obs_data_set_int(settings, "feed", int(layer.feed))
            if layer.graph_metric is not None:
                obs.obs_data_set_int(settings, "graph_metric", int(layer.graph_metric))
            obs.obs_data_set_int(settings, "width", _DEFAULT_SOURCE[0])
            obs.obs_data_set_int(settings, "height", _DEFAULT_SOURCE[1])
            source = obs.obs_source_create("fractisynth_console", layer.name, settings, None)
            try:
                item = obs.obs_scene_add(scene, source)
                px, py, sx, sy = dashboard_layer_transform(
                    layer.bounds,
                    canvas_width,
                    canvas_height,
                    _DEFAULT_SOURCE[0],
                    _DEFAULT_SOURCE[1],
                )
                pos = obs.vec2()
                pos.x = px
                pos.y = py
                scale = obs.vec2()
                scale.x = sx
                scale.y = sy
                obs.obs_sceneitem_set_pos(item, pos)
                obs.obs_sceneitem_set_scale(item, scale)
                obs.obs_sceneitem_set_visible(item, layer.visible)
                _DASHBOARD_ITEMS.append(item)
            finally:
                obs.obs_source_release(source)
                obs.obs_data_release(settings)
        _DASHBOARD_ACTIVE = 0
        _register_dashboard_hotkeys()
        obs.script_log(obs.LOG_INFO, f"[SynthOBS] built dashboard {plan.scene_name}")
    finally:
        obs.obs_source_release(scene_source)


def _sync_scene_for_mode(mode: Mode) -> None:  # pragma: no cover - needs OBS
    """Map the active deck to an OBS scene of the same name, if one exists."""
    if not _IN_OBS:
        return
    scenes = obs.obs_frontend_get_scenes()
    try:
        for scene_source in scenes:
            name = obs.obs_source_get_name(scene_source)
            if name and name.lower() == mode.value:
                obs.obs_frontend_set_current_scene(scene_source)
                break
    finally:
        obs.source_list_release(scenes)


def _on_command_modified(props, prop, settings):  # pragma: no cover - needs OBS
    line = obs.obs_data_get_string(settings, "command_line")
    if line:
        status = apply_command(line)
        obs.obs_data_set_string(settings, "command_status", status)
        obs.script_log(obs.LOG_INFO, f"[SynthOBS] {status}")
    return True


# --- obspython entrypoints ---------------------------------------------------
def script_description() -> str:
    return (
        "SynthOBS Console v1.618 — Goldilocks golden-ratio layout + 3-mode console "
        "(Observatory / Laboratory / Expedition), calibrated by live solar telemetry "
        "via the FractiSynth Solar Wavefield Oscillator."
    )


def script_properties():  # pragma: no cover - needs OBS
    props = obs.obs_properties_create()
    obs.obs_properties_add_text(props, "command_line", "Global Command Line", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "command_status", "Status", obs.OBS_TEXT_DEFAULT)
    p = obs.obs_properties_add_list(
        props, "mode", "Modality Deck", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING
    )
    for m in Mode:
        obs.obs_property_list_add_string(p, m.value.title(), m.value)
    return props


def script_update(settings):  # pragma: no cover - needs OBS
    line = obs.obs_data_get_string(settings, "command_line")
    if line:
        apply_command(line)


def script_load(settings):  # pragma: no cover - needs OBS
    obs.script_log(obs.LOG_INFO, "[SynthOBS] console loaded — " + script_description())


def script_unload():  # pragma: no cover - needs OBS
    pass
