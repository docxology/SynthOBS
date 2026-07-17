#!/usr/bin/env python3
"""Promote a passing live OBS scenario into the manuscript evidence bundle.

The live probe writes an operator-facing directory with relative capture paths.
This command is the reproducible boundary between that run and the versioned
manuscript assets: it requires every requested gate to pass, copies the exact
bytes, recomputes hashes/format metadata, and writes a normalized manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import tempfile
import wave
from pathlib import Path
from typing import Any

SCHEMA = "synthobs.live_scenario.v2"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "manuscript" / "assets" / "obs"

ASSET_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("scene_render", "scene_render", "obs_scene_render.png", "image/png"),
    ("telemetry_hud", "telemetry_hud", "obs_telemetry_hud.png", "image/png"),
    ("audio_tone", "audio_tone", "obs_audio_tone.png", "image/png"),
    ("audio_silent", "audio_silent", "obs_audio_silent.png", "image/png"),
    ("controlled_tone", "controlled_tone", "controlled_tone.wav", "audio/wav"),
)


class PromotionError(RuntimeError):
    """Raised when a live evidence bundle is not promotion-safe."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_run_id(manifest: dict[str, Any], source_dir: Path) -> str:
    scene = str(manifest.get("scene", ""))
    match = re.search(r"(\d{8}T\d{6}Z)", scene)
    return match.group(1) if match else str(manifest.get("source_run") or source_dir.name)


def _portable_path(path: Path) -> str:
    """Represent repository-local paths without embedding this checkout's home directory."""

    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _capture_path(source_dir: Path, manifest: dict[str, Any], key: str) -> Path:
    if key == "controlled_tone":
        candidate = source_dir / "controlled_tone.wav"
    else:
        raw = manifest.get("captures", {}).get(key)
        if not isinstance(raw, str) or not raw:
            raise PromotionError(f"live manifest has no capture path for {key!r}")
        candidate = source_dir / Path(raw).name
    if not candidate.is_file():
        raise PromotionError(f"required live capture is missing: {candidate}")
    return candidate


def _png_dimensions(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or len(raw) < 24:
        raise PromotionError(f"not a valid PNG capture: {path}")
    return struct.unpack(">II", raw[16:24])


def _wav_metadata(path: Path) -> dict[str, int | str]:
    try:
        with wave.open(str(path), "rb") as handle:
            return {
                "media_type": "audio/wav",
                "sample_rate_hz": handle.getframerate(),
                "channels": handle.getnchannels(),
                "sample_width_bits": handle.getsampwidth() * 8,
                "frames": handle.getnframes(),
            }
    except (EOFError, wave.Error) as exc:
        raise PromotionError(f"not a valid WAV capture: {path}: {exc}") from exc


def validate_source(source_dir: Path) -> dict[str, Any]:
    """Load and validate a live probe result before any target writes."""

    manifest_path = source_dir / "manifest.json"
    if not manifest_path.is_file():
        raise PromotionError(f"live manifest is missing: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromotionError(f"cannot read live manifest: {manifest_path}: {exc}") from exc
    if manifest.get("schema") != SCHEMA:
        raise PromotionError(f"expected {SCHEMA}, found {manifest.get('schema')!r}")
    required = manifest.get("required_gates")
    gates = manifest.get("gates")
    if not isinstance(required, list) or not required:
        raise PromotionError("live manifest has no required_gates list")
    if not isinstance(gates, dict):
        raise PromotionError("live manifest has no gates object")
    failed = [name for name in required if gates.get(name, {}).get("status") != "pass"]
    if failed:
        raise PromotionError(f"refusing to promote failed/skipped gates: {failed}")
    for name, result in gates.items():
        if not isinstance(result, dict) or result.get("status") != "pass":
            raise PromotionError(f"refusing to promote non-pass gate: {name}")
    for key, _, _, _ in ASSET_SPECS:
        _capture_path(source_dir, manifest, key)
    return manifest


def build_promoted_manifest(source_dir: Path, manifest: dict[str, Any], target: Path) -> dict[str, Any]:
    """Build the normalized versioned manifest without writing files."""

    assets: dict[str, dict[str, Any]] = {}
    for key, _, output_name, media_type in ASSET_SPECS:
        source = _capture_path(source_dir, manifest, key)
        item: dict[str, Any] = {
            "path": output_name,
            "sha256": _sha256(source),
            "media_type": media_type,
        }
        if media_type == "image/png":
            width, height = _png_dimensions(source)
            item.update({"width": width, "height": height})
        else:
            item.update(_wav_metadata(source))
            item.pop("media_type", None)
            item["media_type"] = media_type
        assets[key] = item

    promoted = {
        "schema": SCHEMA,
        "source_run": _source_run_id(manifest, source_dir),
        "created_at": manifest.get("created_at"),
        "scene": manifest.get("scene"),
        "url": manifest.get("url"),
        "obs": manifest.get("obs", {}),
        "capture_size": manifest.get("capture_size", {}),
        "assets": assets,
        "required_gates": manifest["required_gates"],
        "gates": manifest["gates"],
        "sources": manifest.get("sources", {}),
        "fallbacks": manifest.get("fallbacks", {}),
        "promotion": {
            "source_directory": _portable_path(source_dir),
            "target_directory": _portable_path(target),
            "method": "scripts/promote_obs_evidence.py",
        },
    }
    return promoted


def promote(source_dir: Path, target: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Promote *source_dir* into *target* and return the normalized manifest."""

    source_dir = source_dir.resolve()
    target = target.resolve()
    manifest = validate_source(source_dir)
    promoted = build_promoted_manifest(source_dir, manifest, target)
    if dry_run:
        return promoted

    target.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    try:
        for key, _, output_name, _ in ASSET_SPECS:
            source = _capture_path(source_dir, manifest, key)
            fd, temp_name = tempfile.mkstemp(prefix=f".{output_name}.", dir=target)
            os.close(fd)
            temp = Path(temp_name)
            shutil.copyfile(source, temp)
            staged.append((temp, target / output_name))
        fd, manifest_temp_name = tempfile.mkstemp(prefix=".obs_manifest.", dir=target)
        os.close(fd)
        manifest_temp = Path(manifest_temp_name)
        manifest_temp.write_text(json.dumps(promoted, indent=2) + "\n", encoding="utf-8")
        staged.append((manifest_temp, target / "obs_manifest.json"))
        for temp, destination in staged:
            temp.replace(destination)
    finally:
        for temp, _ in staged:
            temp.unlink(missing_ok=True)
    return promoted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_run", type=Path, help="Directory emitted by obs_scenario_probe.py")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the normalized manifest only")
    args = parser.parse_args(argv)
    try:
        promoted = promote(args.source_run, args.target, dry_run=args.dry_run)
    except PromotionError as exc:
        parser.error(str(exc))
    print(json.dumps({
        "assets": sorted(promoted["assets"]),
        "required_gates": promoted["required_gates"],
        "source_run": promoted["source_run"],
        "target": str(args.target.resolve()),
        "dry_run": args.dry_run,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
