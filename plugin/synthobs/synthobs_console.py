"""SynthOBS Console — the Vessel Console as an OBS Python script.

Load this from OBS via Tools → Scripts. It wraps standard OBS operations in the
Goldilocks layout matrix and the 3-mode console (Observatory / Laboratory /
Expedition), driving everything from the tested SynthOBS engine. The persistent
command line is exposed as a script text property that accepts the grammar:

    /mode --observatory | --lab | --ship
    /transducer bind <source> --ratio=1.618034
    /swo calibrate --flux=130 --spots=3 --target=AR4465

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
    Mode,
    SynthEngine,
    assemble_viewport,
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
        ENGINE.update(telemetry)
        return f"SWO calibrated: phase_vector={ENGINE.phase_vector:.4f}"
    return "ok"  # pragma: no cover - exhaustive above


def viewport_for_canvas(width: int, height: int):
    """Goldilocks viewport for the current OBS canvas (primary 61.8%)."""
    return assemble_viewport(width, height)


# --- obspython adapter layer (only exercised inside OBS) ---------------------
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
        "(Observatory / Laboratory / Expedition), phase-locked to live solar telemetry "
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
