"""Scenario harness contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.obs_scenario_probe import (
    SCHEMA,
    initial_manifest,
    manifest_exit_code,
    set_gate,
    write_manifest,
)
from synthobs.verification import GateResult


def test_initial_manifest_schema_and_required_sections() -> None:
    manifest = initial_manifest(
        scene="SynthOBSVerify",
        url="ws://localhost:4455",
        width=1280,
        height=720,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert manifest["schema"] == SCHEMA
    assert manifest["scene"] == "SynthOBSVerify"
    assert manifest["capture_size"] == {"width": 1280, "height": 720}
    assert manifest["obs"] == {"connected": False}
    assert manifest["gates"] == {}
    assert manifest["captures"] == {}


def test_manifest_skip_semantics_are_non_fatal_unless_live_required(tmp_path: Path) -> None:
    manifest = initial_manifest(
        scene="SynthOBSVerify",
        url="ws://localhost:4455",
        width=1280,
        height=720,
    )
    set_gate(manifest, "connection", GateResult.skipped("OBS websocket unavailable"))

    path = write_manifest(tmp_path, manifest)
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded["gates"]["connection"]["status"] == "skip"
    assert manifest_exit_code(loaded, require_live=False) == 0
    assert manifest_exit_code(loaded, require_live=True) == 1


def test_manifest_requires_all_gates_to_pass_when_live_required() -> None:
    manifest = initial_manifest(
        scene="SynthOBSVerify",
        url="ws://localhost:4455",
        width=1280,
        height=720,
    )
    set_gate(manifest, "connection", GateResult.passed("identified"))
    set_gate(manifest, "audio_reactivity", GateResult.failed("delta below threshold"))

    assert manifest_exit_code(manifest, require_live=True) == 1

    set_gate(manifest, "audio_reactivity", GateResult.passed("delta passed"))
    assert manifest_exit_code(manifest, require_live=True) == 0
