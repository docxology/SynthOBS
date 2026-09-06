"""Promotion-boundary tool tests: thin script wiring over ``synthobs.artifacts``."""

from __future__ import annotations

import hashlib
import io
import json
import struct
import wave
from pathlib import Path
from typing import Any

import pytest

from scripts.promote_obs_evidence import (
    PromotionError,
    build_promoted_manifest,
    promote,
)
from synthobs.artifacts import PNG_SIGNATURE

SCHEMA = "synthobs.live_scenario.v2"


def _png_bytes(width: int, height: int) -> bytes:
    return (
        PNG_SIGNATURE
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
    )


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setframerate(48000)
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.writeframes(b"\x00\x00" * 8)
    return buffer.getvalue()


def _manifest(**overrides: Any) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "scene": "FractiSynth-20260906T000000Z",
        "created_at": "2026-09-06T00:00:00Z",
        "url": "ws://localhost:4455",
        "obs": {"version": "32.1.2"},
        "capture_size": {"width": 64, "height": 48},
        "required_gates": ["connection"],
        "gates": {"connection": {"status": "pass"}},
        "sources": {},
        "fallbacks": {},
        "captures": {
            "scene_render": "scene.png",
            "telemetry_hud": "hud.png",
            "audio_tone": "tone.png",
            "audio_silent": "silent.png",
        },
    }
    manifest.update(overrides)
    return manifest


def _live_dir(tmp_path: Path, manifest: dict[str, Any], *, corrupt_png: bool = False) -> Path:
    source = tmp_path / "live" / "20260906T000000Z"
    source.mkdir(parents=True)
    png = b"broken capture bytes" if corrupt_png else _png_bytes(64, 48)
    for name in ("scene.png", "hud.png", "tone.png", "silent.png"):
        (source / name).write_bytes(png)
    (source / "controlled_tone.wav").write_bytes(_wav_bytes())
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return source


def test_build_promoted_manifest_hashes_and_profiles_captures(tmp_path: Path) -> None:
    source = _live_dir(tmp_path, _manifest())
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))

    promoted = build_promoted_manifest(source, manifest, tmp_path / "target")

    assert promoted["schema"] == SCHEMA
    scene = promoted["assets"]["scene_render"]
    assert scene["sha256"] == hashlib.sha256((source / "scene.png").read_bytes()).hexdigest()
    assert (scene["width"], scene["height"]) == (64, 48)
    tone = promoted["assets"]["controlled_tone"]
    assert tone["sha256"] == hashlib.sha256((source / "controlled_tone.wav").read_bytes()).hexdigest()
    assert tone["sample_rate_hz"] == 48000
    assert tone["frames"] == 8
    assert tone["media_type"] == "audio/wav"


def test_promote_writes_staged_bundle_and_dry_run_writes_nothing(tmp_path: Path) -> None:
    source = _live_dir(tmp_path, _manifest())
    target = tmp_path / "bundle"

    dry = promote(source, target, dry_run=True)
    assert not target.exists()
    assert dry["assets"]["telemetry_hud"]["path"] == "obs_telemetry_hud.png"

    promoted = promote(source, target)
    written = json.loads((target / "obs_manifest.json").read_text(encoding="utf-8"))
    assert written == promoted
    for _, _, output_name, _ in [
        ("scene_render", "", "obs_scene_render.png", ""),
        ("telemetry_hud", "", "obs_telemetry_hud.png", ""),
        ("audio_tone", "", "obs_audio_tone.png", ""),
        ("audio_silent", "", "obs_audio_silent.png", ""),
        ("controlled_tone", "", "controlled_tone.wav", ""),
    ]:
        assert (target / output_name).is_file()


def test_promote_refuses_failed_gates(tmp_path: Path) -> None:
    source = _live_dir(
        tmp_path, _manifest(gates={"connection": {"status": "fail"}})
    )
    with pytest.raises(PromotionError, match="refusing to promote"):
        promote(source, tmp_path / "bundle")


def test_promote_fails_closed_on_corrupt_png(tmp_path: Path) -> None:
    source = _live_dir(tmp_path, _manifest(), corrupt_png=True)
    with pytest.raises(PromotionError, match="not a valid PNG capture"):
        promote(source, tmp_path / "bundle")
