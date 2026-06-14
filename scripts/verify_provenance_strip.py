#!/usr/bin/env python3
"""Verify a SynthOBS HUD provenance strip from a captured PNG frame.

The native console embeds a length-prefixed telemetry payload into the blue-channel
least-significant bits of the rendered frame. This thin orchestrator performs only
image I/O; extraction, checksum validation, and record validation remain in
``src/synthobs/provenance.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.image as mpimg  # noqa: E402
import numpy as np  # noqa: E402

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from synthobs.provenance import (  # noqa: E402
    ProvenanceError,
    TelemetryRecord,
    extract_lsb,
    short_signature,
    verify_payload,
)


def _png_to_rgba_bytes(path: Path) -> tuple[bytes, int, int]:
    """Load a PNG and return row-major RGBA bytes plus width/height."""
    if not path.is_file():
        raise ProvenanceError(f"image does not exist: {path}")

    arr = np.asarray(mpimg.imread(path))
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise ProvenanceError(f"expected RGB/RGBA PNG, got shape {arr.shape!r}")

    if arr.dtype.kind == "f":
        arr = np.rint(np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8)
    elif arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)

    if arr.shape[2] == 3:
        alpha = np.full((*arr.shape[:2], 1), 255, dtype=np.uint8)
        arr = np.concatenate((arr, alpha), axis=2)

    height, width = arr.shape[:2]
    return arr.tobytes(order="C"), width, height


def verify_png(path: str | Path) -> TelemetryRecord:
    """Extract and verify the provenance record embedded in ``path``."""
    rgba, width, height = _png_to_rgba_bytes(Path(path))
    return verify_payload(extract_lsb(rgba, width, height))


def record_summary(rec: TelemetryRecord) -> dict[str, Any]:
    """JSON-serializable summary for operator-facing CLI output."""
    return {
        "flux": rec.flux,
        "sunspots": rec.sunspots,
        "solar_wind_kms": rec.solar_wind_kms,
        "lock_strength": rec.lock_strength,
        "phase_bias_rad": rec.phase_bias_rad,
        "observed_unix": rec.observed_unix,
        "signature": short_signature(rec),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the LSB provenance strip embedded in a SynthOBS HUD PNG."
    )
    parser.add_argument("image", help="PNG frame captured from the Telemetry HUD feed")
    parser.add_argument(
        "--expect-signature",
        help="Optional 8-hex on-screen signature that must match the recovered record",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        rec = verify_png(args.image)
        summary = record_summary(rec)
        if args.expect_signature and summary["signature"] != args.expect_signature.lower():
            raise ProvenanceError(
                f"signature mismatch: expected {args.expect_signature}, got {summary['signature']}"
            )
    except ProvenanceError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(
            "OK "
            f"signature={summary['signature']} "
            f"flux={summary['flux']:.3f} "
            f"sunspots={summary['sunspots']} "
            f"wind={summary['solar_wind_kms']:.3f}km/s "
            f"lock={summary['lock_strength']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
