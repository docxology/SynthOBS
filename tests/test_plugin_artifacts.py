"""Static + behavioral probes for the native C plugin (ISC-55..61) and the
obspython console bridge (ISC-62..64)."""

from __future__ import annotations

import importlib.util
import py_compile
from pathlib import Path

import pytest
from synthobs.console import Mode
from synthobs.constants import PHI

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
FRACTI_C = PLUGIN / "fractisynth" / "src" / "fractisynth.c"
FRACTI_DOCK = PLUGIN / "fractisynth" / "src" / "fractisynth_dock.cpp"
CMAKE = PLUGIN / "fractisynth" / "CMakeLists.txt"
CONSOLE_PY = PLUGIN / "synthobs" / "synthobs_console.py"
CONSOLE_EFFECT = PLUGIN / "fractisynth" / "data" / "fractisynth_console.effect"
LOCALE = PLUGIN / "fractisynth" / "data" / "locale" / "en-US.ini"


@pytest.fixture(scope="module")
def c_source() -> str:
    return FRACTI_C.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dock_source() -> str:
    return FRACTI_DOCK.read_text(encoding="utf-8")


# --- native plugin static structure -------------------------------------
def test_cmake_exists_and_links_obs_curl() -> None:  # ISC-55
    assert CMAKE.is_file()
    text = CMAKE.read_text(encoding="utf-8")
    assert "OBS::libobs" in text
    assert "CURL" in text
    assert "fractisynth.c" in text


def test_registers_video_filter(c_source: str) -> None:  # ISC-56
    assert "OBS_SOURCE_TYPE_FILTER" in c_source
    assert "obs_register_source(&fractisynth_video_filter)" in c_source
    assert ".video_render = fsv_video_render" in c_source


def test_video_calibration_phi(c_source: str) -> None:  # ISC-57
    assert "/ EGS_PHI" in c_source
    assert "calibrated_width" in c_source and "calibrated_height" in c_source


def test_audio_soft_limiter(c_source: str) -> None:  # ISC-58
    assert "phi_soft_limit_sample" in c_source
    assert "filter_audio = fsa_filter_audio" in c_source
    assert "tanhf" in c_source  # smooth, not hard-clipped
    assert "audio_envelope_store" in c_source
    assert "audio_envelope_read" in c_source
    assert "sqrt(sum_sq / (double)count)" in c_source
    assert "audio_reactivity" in c_source
    # Envelope must release to silence when the source stops feeding the filter
    # (OBS never delivers a final silence buffer), so reads have a staleness hold
    # and the meter falls to zero — a lit-forever meter is the bug this guards.
    assert "AUDIO_ENVELOPE_HOLD_NS" in c_source
    assert "updated_ns" in c_source


def test_reads_shared_swo(c_source: str) -> None:  # ISC-59
    assert "swo_phase_vector()" in c_source
    assert "system_phase_vector" in c_source


def test_phi_literal_matches_python(c_source: str) -> None:  # ISC-60
    assert "#define EGS_PHI 1.61803398875f" in c_source
    assert abs(1.61803398875 - PHI) < 1e-9


def test_egs_gateway_key_literal_matches_python(c_source: str) -> None:  # ISC-93
    # the canonical EGS Fractal Constant (gateway key) is pinned C↔Python
    from synthobs.constants import EGS_GATEWAY_KEY, EGS_GATEWAY_KEY_C_LITERAL

    assert "#define EGS_GATEWAY_KEY 2.53942700f" in c_source
    assert abs(float(EGS_GATEWAY_KEY_C_LITERAL) - EGS_GATEWAY_KEY) < 1e-6


def test_gateway_lock_and_solar_wind_present(c_source: str) -> None:  # ISC-94
    # the EGS gateway phase plane: solar-wind feed + fail-closed lock + reader-side gate
    assert "NOAA_SOLARWIND_URL" in c_source
    assert "synchronize_gateway_lock" in c_source
    assert "extract_last_wind_speed" in c_source
    assert "lock_strength" in c_source and "wind_phase" in c_source
    # the new shader-facing uniforms are wired
    assert 'gs_effect_get_param_by_name(f->effect, "egs_key")' in c_source
    assert 'gs_effect_get_param_by_name(f->effect, "lock_strength")' in c_source


def test_console_interactive_targets_cover_all_feeds(c_source: str) -> None:
    effect = CONSOLE_EFFECT.read_text(encoding="utf-8")
    locale = LOCALE.read_text(encoding="utf-8")
    assert "FCV_FEED_COUNT 7" in c_source
    assert "FCV_TAB_CELLS 7.0f" in c_source
    assert "TargetActionMarker" in c_source
    assert "marker_x" in c_source and "marker_age" in c_source
    assert "layer_visible_mask" in c_source
    assert "OBS_SOURCE_INTERACTION" in c_source and ".mouse_click = fcv_mouse_click" in c_source
    assert "if (!isfinite(x) || !isfinite(y))" in c_source
    assert "float fcell = uv.x * 7.0" in effect
    assert "marker_age" in effect and "layer_visible_mask" in effect
    assert "uniform float audio_rms" in effect
    assert "uniform float audio_peak" in effect
    assert "uniform float audio_reactivity" in effect
    assert "AUDIO RMS" in c_source and "AUDIO REACT" in c_source
    assert "hud_signature_strip" in c_source
    assert "LSB+VISIBLE" in c_source
    for key in (
        "FeedWavefield",
        "FeedHexTunnel",
        "FeedInterference",
        "FeedSpectral",
        "FeedSpiralDrift",
        "FeedTelemetryHUD",
        "FeedSolarGraph",
        "ShowTargets",
    ):
        assert key in locale


def test_solar_graph_xray_kp_wiring_is_pinned(c_source: str) -> None:
    locale = LOCALE.read_text(encoding="utf-8")
    assert "SER_XRAY = 3" in c_source
    assert "SER_KP = 4" in c_source
    assert "NOAA_XRAY_URL" in c_source and "NOAA_KP_URL" in c_source
    assert "parse_xray_series" in c_source and "parse_kp_series" in c_source
    assert "GOES X-RAY FLUX 0.1-0.8NM" in c_source
    assert "PLANETARY K-INDEX (KP)" in c_source
    assert "MetricXray" in locale and "MetricKp" in locale


def test_native_fail_closed_finiteness_guards_are_pinned(c_source: str) -> None:
    assert "if (!isfinite(current_flux) || current_flux <= 0.0f || active_spots <= 0)" in c_source
    assert "if (!isfinite(solar_wind_kms) || solar_wind_kms <= 0.0f)" in c_source
    assert "end != p && isfinite(val) && val > 0.0f" in c_source
    assert "end == p || !isfinite(val) || val <= 0.0f" in c_source
    assert "if (isfinite(v) && v >= 0.0f && v <= 12.0f)" in c_source
    assert "if (!isfinite(f->threshold) || f->threshold <= 0.0f)" in c_source


def test_solar_graph_metric_time_axes_are_pinned(c_source: str) -> None:
    assert 'axis_left = "-2H"' in c_source
    assert 'axis_left = "-6H"' in c_source
    assert '"-%d MIN"' in c_source
    assert "metric-aware horizon" in c_source
    assert '"OLDEST"' not in c_source


def test_zoom_inspector_modes_annotation_and_locale(c_source: str) -> None:
    locale = LOCALE.read_text(encoding="utf-8")
    assert 'obs_properties_add_list(p, "inspector_mode"' in c_source
    assert "InspectorModeFixed" in c_source and "InspectorModeFollowMouse" in c_source
    assert 'obs_properties_add_bool(p, "show_annotation"' in c_source
    assert ".mouse_move = fpi_mouse_move" in c_source
    assert "OBS_SOURCE_VIDEO | OBS_SOURCE_INTERACTION" in c_source
    assert "f->inspector_mode == 1 && f->have_mouse" in c_source
    assert "INSPECTOR %s  UV" in c_source
    for key in (
        "InspectorMode",
        "InspectorModeFixed",
        "InspectorModeFollowMouse",
        "InspectorShowAnnotation",
    ):
        assert key in locale


def test_frontend_dock_polish_and_theme_following(dock_source: str, c_source: str) -> None:
    assert "static atomic_int g_console_theme" in c_source
    assert "int fractisynth_get_console_theme(void)" in c_source
    assert "atomic_store(&g_console_theme" in c_source
    assert "fractisynth_get_console_theme" in dock_source
    assert "palette_for_theme" in dock_source
    assert "m_gauge_style" in dock_source
    assert "Ring" in dock_source and "Bar" in dock_source and "Needle" in dock_source
    assert "m_precision" in dock_source
    assert "%d dp" in dock_source
    assert "m_freeze" in dock_source
    assert "audio_rms" in dock_source
    assert "audio_peak" in dock_source
    assert "audio_reactivity" in dock_source
    assert "audio rms / peak" in dock_source


def test_module_load_registers(c_source: str) -> None:  # ISC-61
    assert "bool obs_module_load(void)" in c_source
    assert "return true;" in c_source
    assert "obs_register_source(&fractisynth_audio_filter)" in c_source
    # fail-closed telemetry: non-positive/non-finite flux or non-positive spots holds.
    assert "if (!isfinite(current_flux) || current_flux <= 0.0f || active_spots <= 0)" in c_source


# --- obspython console bridge -------------------------------------------
def test_console_py_compiles() -> None:  # ISC-62
    py_compile.compile(str(CONSOLE_PY), doraise=True)


def _load_console():
    spec = importlib.util.spec_from_file_location("synthobs_console", CONSOLE_PY)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_console_entrypoints_defined() -> None:  # ISC-63
    mod = _load_console()
    assert callable(mod.script_load)
    assert callable(mod.script_description)
    assert "SynthOBS" in mod.script_description()
    assert mod._IN_OBS is False  # guarded import keeps it importable outside OBS


def test_console_apply_command_maps_modes() -> None:  # ISC-64
    mod = _load_console()
    assert "observatory" in mod.apply_command("/mode --observatory")
    assert mod.ENGINE.mode == Mode.OBSERVATORY
    assert "laboratory" in mod.apply_command("/mode --lab")
    assert mod.ENGINE.mode == Mode.LABORATORY
    # calibrate flows through the real engine
    out = mod.apply_command("/swo calibrate --flux=130 --spots=3 --target=AR4465")
    assert "phase_vector" in out
    assert mod.ENGINE.phase_vector is not None
    # bind
    assert "bound" in mod.apply_command("/transducer bind source_cam_01 --ratio=1.618034")
    # invalid → error string, not a crash
    assert mod.apply_command("/warp --core").startswith("ERROR")


def test_console_viewport_helper() -> None:
    mod = _load_console()
    vp = mod.viewport_for_canvas(1920, 1080)
    assert vp.tiles_exactly()


def test_console_dashboard_transform_uses_supplied_canvas() -> None:
    mod = _load_console()
    assert mod.dashboard_layer_transform((0.5, 0.25, 0.25, 0.5), 1280, 720) == (
        640.0,
        180.0,
        0.25,
        0.5,
    )
    assert mod.dashboard_layer_transform((0.5, 0.25, 0.25, 0.5), 2560, 1080) == (
        1280.0,
        270.0,
        0.5,
        0.75,
    )


def test_console_dashboard_no_longer_hardcodes_1080p_scene_math() -> None:
    text = CONSOLE_PY.read_text(encoding="utf-8")
    assert "x * 1920.0" not in text
    assert "y * 1080.0" not in text
    assert "_obs_canvas_size" in text
