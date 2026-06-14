"""Provenance-strip verifier tests.

These exercise a real PNG round-trip through matplotlib image I/O and the same
byte-exact provenance module used by the native plugin mirror.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import pytest

from scripts.verify_provenance_strip import verify_png
from synthobs.provenance import (
    ProvenanceError,
    TelemetryRecord,
    build_payload,
    embed_lsb,
    short_signature,
)

ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = ROOT / "scripts" / "verify_provenance_strip.py"


def _record() -> TelemetryRecord:
    return TelemetryRecord(
        flux=145.25,
        sunspots=7,
        solar_wind_kms=397.5,
        lock_strength=0.989,
        phase_bias_rad=3.29,
        observed_unix=1_781_000_000,
    )


def _write_embedded_png(path: Path, rec: TelemetryRecord, *, rgb: bool = False) -> None:
    width, height = 64, 64
    rgba = bytearray([80, 120, 160, 255] * (width * height))
    embed_lsb(rgba, width, height, build_payload(rec))
    arr = np.frombuffer(bytes(rgba), dtype=np.uint8).reshape((height, width, 4))
    if rgb:
        arr = arr[:, :, :3]
    mpimg.imsave(path, arr)


def test_verify_png_round_trips_real_rgba_image(tmp_path: Path) -> None:
    rec = _record()
    path = tmp_path / "hud.png"
    _write_embedded_png(path, rec)

    recovered = verify_png(path)

    assert recovered.sunspots == rec.sunspots
    assert recovered.observed_unix == rec.observed_unix
    assert short_signature(recovered) == short_signature(rec)


def test_verify_png_accepts_rgb_screenshots(tmp_path: Path) -> None:
    rec = _record()
    path = tmp_path / "hud_rgb.png"
    _write_embedded_png(path, rec, rgb=True)

    assert short_signature(verify_png(path)) == short_signature(rec)


def test_verify_png_fails_closed_on_too_small_image(tmp_path: Path) -> None:
    path = tmp_path / "tiny.png"
    mpimg.imsave(path, np.zeros((1, 1, 4), dtype=np.uint8))

    with pytest.raises(ProvenanceError, match="length prefix"):
        verify_png(path)


def test_verifier_cli_outputs_json_and_checks_signature(tmp_path: Path) -> None:
    rec = _record()
    path = tmp_path / "hud.png"
    _write_embedded_png(path, rec)
    signature = short_signature(rec)

    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            str(path),
            "--json",
            "--expect-signature",
            signature,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["signature"] == signature
    assert payload["sunspots"] == rec.sunspots


def test_verifier_cli_rejects_signature_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "hud.png"
    _write_embedded_png(path, _record())

    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), str(path), "--expect-signature", "deadbeef"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "signature mismatch" in result.stderr
