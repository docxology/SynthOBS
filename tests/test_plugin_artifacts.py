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
CMAKE = PLUGIN / "fractisynth" / "CMakeLists.txt"
CONSOLE_PY = PLUGIN / "synthobs" / "synthobs_console.py"


@pytest.fixture(scope="module")
def c_source() -> str:
    return FRACTI_C.read_text(encoding="utf-8")


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


def test_module_load_registers(c_source: str) -> None:  # ISC-61
    assert "bool obs_module_load(void)" in c_source
    assert "return true;" in c_source
    assert "obs_register_source(&fractisynth_audio_filter)" in c_source
    # fail-closed telemetry: non-positive flux/spots returns false, holds vector
    assert "if (current_flux <= 0.0f || active_spots <= 0)" in c_source


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
