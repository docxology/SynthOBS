#!/usr/bin/env python3
"""Install the built wheel into an isolated environment and import it.

This is intentionally a small release gate.  The engine declares no runtime
dependencies, so a wheel must install without an index and import with Python's
isolated mode.  Figure-generation dependencies are deliberately outside this
check.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _default_wheel() -> Path:
    wheels = sorted((ROOT / "dist").glob("synthobs-*.whl"))
    if not wheels:
        raise FileNotFoundError(
            "no synthobs wheel found; run `uv build` before package_smoke.py"
        )
    return wheels[-1]


def run_smoke(wheel: Path) -> dict[str, object]:
    """Return a machine-readable result for an isolated wheel installation."""
    wheel = wheel.resolve()
    if wheel.suffix != ".whl" or not wheel.is_file():
        raise FileNotFoundError(f"wheel does not exist: {wheel}")

    with tempfile.TemporaryDirectory(prefix="synthobs-wheel-") as temp:
        env_dir = Path(temp) / "venv"
        # uv-managed standalone CPython builds on macOS can abort in the bundled
        # ensurepip module. Prefer uv's seeded environment when available, while
        # retaining a stdlib-only fallback for ordinary Python installations.
        uv = shutil.which("uv")
        if uv:
            subprocess.run(
                [uv, "venv", "--seed", str(env_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        python = env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)],
            check=True,
            capture_output=True,
            text=True,
        )
        probe = (
            "import importlib.metadata, json, synthobs\n"
            "assert synthobs.PHI > 1.6\n"
            "assert callable(synthobs.parse_noaa_plasma_series)\n"
            "print(json.dumps({'package': importlib.metadata.version('synthobs'),"
            " 'phi': synthobs.PHI, 'runtime_dependencies': []}, sort_keys=True))\n"
        )
        result = subprocess.run(
            [str(python), "-I", "-c", probe],
            check=True,
            capture_output=True,
            text=True,
        )

    payload = json.loads(result.stdout)
    payload["wheel"] = wheel.name
    payload["isolated"] = True
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wheel",
        type=Path,
        help="wheel to install (default: newest dist/synthobs-*.whl)",
    )
    args = parser.parse_args(argv)
    try:
        result = run_smoke(args.wheel or _default_wheel())
    except (
        FileNotFoundError,
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as exc:
        print(f"FAIL: package smoke: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
