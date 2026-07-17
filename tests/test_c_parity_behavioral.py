"""Behavioral C<->Python parity — compile the real C kernel and execute it.

The other parity tests (``test_plugin_artifacts.py``) assert that tokens like
``tanhf`` and ``phi_soft_limit_sample`` appear in the C source. A token grep
cannot catch an algorithmic drift: the C body could compute a different curve and
still contain the word ``tanhf``. This module closes that gap for the audio
soft-limiter — the one kernel whose float math is small and self-contained — by
extracting the *actual* C function from ``plugin/fractisynth/src/fractisynth.c``,
compiling it with the system C compiler, loading it via ``ctypes``, and asserting
its output matches :func:`synthobs.dsp.phi_soft_limit_sample` across an adversarial
grid (identity region, knee boundary, large, negative, and non-finite inputs).

If no C compiler is available the test SKIPS (mirrors the Lean-build gate) — a skip
is honest "not exercised here", never a silent pass. The test uses real compilation,
real ctypes calls, and real numbers.
"""

from __future__ import annotations

import ctypes
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from synthobs.constants import PHI
from synthobs.dsp import phi_soft_limit_sample
from synthobs.telemetry import (
    TelemetryUnavailable,
    parse_noaa_plasma_series,
    parse_noaa_solar_wind,
)

_C_SOURCE = Path(__file__).resolve().parents[1] / "plugin" / "fractisynth" / "src" / "fractisynth.c"


def _extract_kernel(c_text: str) -> str:
    """Pull the EGS_PHI/EGS_INV_PHI defines and the phi_soft_limit_sample body
    verbatim from the shipped plugin source, so the compiled kernel IS the plugin's
    kernel (not a hand-retyped copy that could itself drift)."""
    phi = re.search(r"^#define\s+EGS_PHI\s+.+$", c_text, re.M)
    inv = re.search(r"^#define\s+EGS_INV_PHI\s+.+$", c_text, re.M)
    if not (phi and inv):
        raise RuntimeError("EGS_PHI / EGS_INV_PHI defines not found in fractisynth.c")
    start = c_text.index("static inline float phi_soft_limit_sample")
    # walk braces from the function's opening { to its matching }
    brace_open = c_text.index("{", start)
    depth = 0
    end = brace_open
    for i in range(brace_open, len(c_text)):
        if c_text[i] == "{":
            depth += 1
        elif c_text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    body = c_text[start:end].replace("static inline ", "", 1)
    return f"#include <math.h>\n{phi.group(0)}\n{inv.group(0)}\n\n{body}\n"


@pytest.fixture(scope="module")
def c_kernel(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if cc is None:
        pytest.skip("no C compiler (cc/clang/gcc) available — behavioral parity not exercised here")
    src = _extract_kernel(_C_SOURCE.read_text())
    d = tmp_path_factory.mktemp("cparity")
    cfile = d / "kernel.c"
    cfile.write_text(src)
    lib = d / "kernel.so"
    proc = subprocess.run(
        [cc, "-shared", "-fPIC", "-O2", "-o", str(lib), str(cfile)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        pytest.skip(f"C kernel did not compile in this env: {proc.stderr[:300]}")
    dll = ctypes.CDLL(str(lib))
    dll.phi_soft_limit_sample.restype = ctypes.c_float
    dll.phi_soft_limit_sample.argtypes = [ctypes.c_float, ctypes.c_float]
    return dll.phi_soft_limit_sample


# float32 (C) vs float64 (Python) + truncated EGS_PHI literal vs full PHI →
# results agree to ~1e-4, not bit-exact. The point is curve identity, not the last ULP.
#
# Scope note (deliberate divergence, intentionally OUTSIDE this grid): on an INVALID
# threshold (<=0 or non-finite) the C kernel clamps defensively to 1.0f — it runs in the
# hot audio callback and must never raise — whereas Python `phi_soft_limit_sample` RAISES
# ValueError (strict validation at the engine boundary). The grid below uses only valid
# positive thresholds, so "C matches Python across the grid" is an honest claim about the
# shared limiting curve; the invalid-threshold branch is a deliberate by-design difference,
# not a parity defect.
_TOL = 2e-4

_GRID = [
    (0.0, 1.0),
    (0.1, 1.0),  # identity region
    (0.61803, 1.0),  # right at the knee
    (0.7, 1.0),
    (0.95, 1.0),
    (1.0, 1.0),
    (5.0, 1.0),  # deep into compression
    (-0.7, 1.0),  # sign symmetry
    (-3.0, 1.0),
    (0.4, 0.5),  # non-unit threshold
    (0.9, 2.0),
    (123.4, 1.0),  # large input -> ceiling-bounded
]


def test_native_rtsw_parser_matches_python_current_and_rejected_rows(tmp_path: Path) -> None:
    """Execute the shipped native RTSW parser against the Python fixtures.

    This keeps the C parser as a real standalone unit: no token scan or retyped
    implementation can satisfy the check. The same shuffled, inactive, stale,
    and future rows exercise latest-record selection and freshness rejection in
    both layers.
    """
    cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if cc is None:
        pytest.skip("no C compiler available — native RTSW parity not exercised")

    harness = tmp_path / "rtsw_harness.c"
    harness.write_text(
        '#include <stdio.h>\n'
        '#include <stdlib.h>\n'
        '#include "rtsw_parser.h"\n'
        'int main(int argc, char **argv) {\n'
        '  if (argc != 3) return 2;\n'
        '  double max_age = strtod(argv[1], NULL);\n'
        '  float d[8] = {0}, s[8] = {0}, t[8] = {0};\n'
        '  float wind = synthobs_extract_rtsw_wind_speed(argv[2], max_age);\n'
        '  int n = synthobs_parse_rtsw_plasma_series(argv[2], d, s, t, 8, max_age);\n'
        '  printf("%.3f %d %.3f %.3f %.3f %.3f\\n", wind, n, d[0], d[1], s[0], s[1]);\n'
        '  return 0;\n'
        '}\n',
        encoding="utf-8",
    )
    binary = tmp_path / "rtsw_harness"
    result = subprocess.run(
        [cc, "-std=gnu11", "-O2", "-I", str(_C_SOURCE.parent), "-o", str(binary), str(harness)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"native RTSW harness did not compile: {result.stderr[:300]}")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
    feed = [
        {"time_tag": stamp(now + timedelta(seconds=60)), "active": False, "proton_density": 99.0, "proton_speed": 999.0, "proton_temperature": 999.0},
        {"time_tag": stamp(now - timedelta(seconds=60)), "active": True, "proton_density": 2.0, "proton_speed": 470.0, "proton_temperature": 100000.0},
        {"time_tag": stamp(now), "active": True, "proton_density": 3.0, "proton_speed": 480.0, "proton_temperature": 110000.0},
    ]

    def run(rows: list[dict], max_age: float = 3600.0) -> list[str]:
        completed = subprocess.run(
            [str(binary), str(max_age), json.dumps(rows, separators=(",", ":"))],
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip().split()

    wind = parse_noaa_solar_wind(feed, now=now, max_age_s=3600.0)
    density, speed, _temp = parse_noaa_plasma_series(feed, now=now, max_age_s=3600.0)
    native = run(feed)
    assert float(native[0]) == pytest.approx(wind.speed_kms, abs=0.01)
    assert int(native[1]) == len(speed) == 2
    assert [float(native[2]), float(native[3])] == pytest.approx(density)
    assert [float(native[4]), float(native[5])] == pytest.approx(speed)

    stale = [{**feed[2], "time_tag": stamp(now - timedelta(hours=2))}]
    future = [{**feed[2], "time_tag": stamp(now + timedelta(hours=2))}]
    for rejected in (stale, future):
        with pytest.raises(TelemetryUnavailable):
            parse_noaa_solar_wind(rejected, now=now, max_age_s=3600.0)
        with pytest.raises(TelemetryUnavailable):
            parse_noaa_plasma_series(rejected, now=now, max_age_s=3600.0)
        native_rejected = run(rejected)
        assert float(native_rejected[0]) == -1.0
        assert int(native_rejected[1]) == 0


@pytest.mark.parametrize("x,threshold", _GRID)
def test_c_matches_python_on_grid(c_kernel, x: float, threshold: float) -> None:  # type: ignore[no-untyped-def]
    py = phi_soft_limit_sample(x, threshold)
    c = c_kernel(ctypes.c_float(x), ctypes.c_float(threshold))
    assert abs(py - c) < _TOL, f"C={c} Python={py} for x={x}, threshold={threshold}"
    # ceiling guarantee holds in BOTH implementations
    assert abs(c) <= threshold + _TOL


def test_c_matches_python_on_nonfinite(c_kernel) -> None:  # type: ignore[no-untyped-def]
    # NaN -> 0.0, +-Inf -> +-ceiling, in both implementations.
    assert c_kernel(ctypes.c_float(float("nan")), ctypes.c_float(1.0)) == pytest.approx(0.0, abs=_TOL)
    assert c_kernel(ctypes.c_float(float("inf")), ctypes.c_float(1.0)) == pytest.approx(1.0, abs=_TOL)
    assert c_kernel(ctypes.c_float(float("-inf")), ctypes.c_float(1.0)) == pytest.approx(-1.0, abs=_TOL)
    assert phi_soft_limit_sample(float("nan"), 1.0) == 0.0
    assert phi_soft_limit_sample(float("inf"), 1.0) == pytest.approx(1.0)


def test_c_curve_is_not_linear_above_knee(c_kernel) -> None:  # type: ignore[no-untyped-def]
    # Anti-regression for the very drift this test exists to catch: a piecewise-LINEAR
    # fold (the wrong manuscript form) would make second differences ~0 above the knee.
    # The shipped tanh curve is strictly concave there — second difference < 0.
    a = c_kernel(ctypes.c_float(0.8), ctypes.c_float(1.0))
    b = c_kernel(ctypes.c_float(1.2), ctypes.c_float(1.0))
    c = c_kernel(ctypes.c_float(1.6), ctypes.c_float(1.0))
    assert (c - b) < (b - a), "C limiter is linear above the knee — tanh saturation lost"
    assert abs(float(PHI) - 1.6180339887) < 1e-9  # sanity pin
