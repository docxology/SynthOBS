#!/usr/bin/env python3
"""Live SynthOBS scenario verifier for obs-websocket v5.

This is an operator-facing harness, not a unit-test replacement. It creates or
selects an isolated OBS scene, adds a FractiSynth console source, captures live
PNG frames, and writes a manifest with explicit pass/fail/skip gates.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import struct
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.image as mpimg  # noqa: E402
import numpy as np  # noqa: E402

try:  # live-probe-only dependency; the pure manifest helpers (and their tests) never touch it
    import websocket  # type: ignore  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - exercised only in envs without the dev extra
    websocket = None  # type: ignore[assignment]

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from scripts.verify_provenance_strip import record_summary, verify_png  # noqa: E402
from synthobs.interaction import TargetAction, resolve_target_action  # noqa: E402
from synthobs.provenance import ProvenanceError  # noqa: E402
from synthobs.verification import (  # noqa: E402
    GateResult,
    score_audio_meter_delta,
)

SCHEMA = "synthobs.live_scenario.v1"
DEFAULT_PASSWORD = os.environ.get("OBS_WEBSOCKET_PASSWORD", "***REDACTED-DEFAULT-PASSWORD***")
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720


class ObsScenarioError(RuntimeError):
    """Raised when a live OBS request cannot satisfy a scenario step."""


class ObsClient:
    """Minimal obs-websocket v5 client for the scenario harness."""

    def __init__(self, url: str, password: str, *, timeout: float = 15.0) -> None:
        self.url = url
        self.password = password
        self.timeout = timeout
        self.ws: websocket.WebSocket | None = None

    def connect(self) -> None:
        if websocket is None:  # pragma: no cover - guarded live path
            raise ObsScenarioError(
                "websocket-client is not installed; install the project 'dev' extra "
                "(uv sync --extra dev) to run the live OBS scenario probe"
            )
        ws = websocket.create_connection(self.url, timeout=self.timeout)
        hello = json.loads(ws.recv())
        ident: dict[str, Any] = {"op": 1, "d": {"rpcVersion": 1}}
        auth = hello["d"].get("authentication")
        if auth:
            ident["d"]["authentication"] = _auth(
                self.password, auth["salt"], auth["challenge"]
            )
        ws.send(json.dumps(ident))
        confirmed = json.loads(ws.recv())
        if confirmed.get("op") != 2:
            ws.close()
            raise ObsScenarioError(f"not identified: {confirmed}")
        self.ws = ws

    def close(self) -> None:
        if self.ws is not None:
            self.ws.close()
            self.ws = None

    def request(self, req_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.ws is None:
            raise ObsScenarioError("OBS websocket is not connected")
        rid = f"r{int(time.time() * 1000)}"
        self.ws.send(
            json.dumps(
                {
                    "op": 6,
                    "d": {
                        "requestType": req_type,
                        "requestId": rid,
                        "requestData": data or {},
                    },
                }
            )
        )
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("op") == 7 and msg["d"].get("requestId") == rid:
                status = msg["d"].get("requestStatus", {})
                if status.get("result") is not True:
                    code = status.get("code", "unknown")
                    comment = status.get("comment", "request failed")
                    raise ObsScenarioError(f"{req_type} failed [{code}]: {comment}")
                return msg["d"].get("responseData", {})


def _auth(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(hashlib.sha256((password + salt).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def initial_manifest(
    *,
    scene: str,
    url: str,
    width: int,
    height: int,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Return the stable manifest skeleton used by tests and the live harness."""

    return {
        "schema": SCHEMA,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "scene": scene,
        "url": url,
        "capture_size": {"width": width, "height": height},
        "obs": {"connected": False},
        "sources": {},
        "captures": {},
        "gates": {},
        "fallbacks": {},
    }


def set_gate(manifest: dict[str, Any], name: str, result: GateResult) -> None:
    manifest["gates"][name] = result.to_dict()


def manifest_exit_code(manifest: dict[str, Any], *, require_live: bool) -> int:
    if not require_live:
        return 0
    for gate in manifest.get("gates", {}).values():
        if gate.get("status") != "pass":
            return 1
    return 0


def write_manifest(out_dir: Path, manifest: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _ensure_scene(client: ObsClient, scene: str) -> None:
    scenes = client.request("GetSceneList")
    names = [s["sceneName"] for s in scenes.get("scenes", [])]
    if scene not in names:
        client.request("CreateScene", {"sceneName": scene})
    client.request("SetCurrentProgramScene", {"sceneName": scene})


def _create_or_update_input(
    client: ObsClient,
    *,
    scene: str,
    name: str,
    kind: str,
    settings: dict[str, Any],
) -> None:
    try:
        client.request(
            "CreateInput",
            {
                "sceneName": scene,
                "inputName": name,
                "inputKind": kind,
                "inputSettings": settings,
                "sceneItemEnabled": True,
            },
        )
    except ObsScenarioError:
        client.request(
            "SetInputSettings",
            {"inputName": name, "inputSettings": settings, "overlay": True},
        )


def _video_settings(client: ObsClient) -> tuple[int, int]:
    data = client.request("GetVideoSettings")
    width = int(data.get("baseWidth") or data.get("base_width") or DEFAULT_WIDTH)
    height = int(data.get("baseHeight") or data.get("base_height") or DEFAULT_HEIGHT)
    if width <= 0 or height <= 0:
        return DEFAULT_WIDTH, DEFAULT_HEIGHT
    return width, height


def _fit_scene_item(
    client: ObsClient,
    *,
    scene: str,
    source: str,
    base_width: int,
    base_height: int,
    source_width: int,
    source_height: int,
) -> dict[str, float]:
    data = client.request("GetSceneItemId", {"sceneName": scene, "sourceName": source})
    item_id = data["sceneItemId"]
    transform = {
        "positionX": 0.0,
        "positionY": 0.0,
        "scaleX": base_width / float(source_width),
        "scaleY": base_height / float(source_height),
    }
    client.request(
        "SetSceneItemTransform",
        {
            "sceneName": scene,
            "sceneItemId": item_id,
            "sceneItemTransform": transform,
        },
    )
    return transform


def _capture_png(
    client: ObsClient,
    *,
    source_name: str,
    out_path: Path,
    width: int,
    height: int,
) -> None:
    shot = client.request(
        "GetSourceScreenshot",
        {
            "sourceName": source_name,
            "imageFormat": "png",
            "imageWidth": width,
            "imageHeight": height,
        },
    )
    data = shot["imageData"].split(",", 1)[-1]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(data))


def _png_to_rgba_bytes(path: Path) -> tuple[bytes, int, int]:
    arr = np.asarray(mpimg.imread(path))
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise ValueError(f"expected RGB/RGBA PNG, got shape {arr.shape!r}")
    if arr.dtype.kind == "f":
        arr = np.rint(np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8)
    elif arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.shape[2] == 3:
        alpha = np.full((*arr.shape[:2], 1), 255, dtype=np.uint8)
        arr = np.concatenate((arr, alpha), axis=2)
    height, width = arr.shape[:2]
    return arr.tobytes(order="C"), width, height


def _write_tone(path: Path, *, seconds: float = 2.0, sample_rate: int = 48_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sample_rate)
    freq = 440.0
    amp = 0.35
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sample_rate)
        for i in range(frames):
            val = int(amp * 32767.0 * math.sin(2.0 * math.pi * freq * i / sample_rate))
            fh.writeframesraw(struct.pack("<h", val))


def _interaction_gate() -> GateResult:
    feed = resolve_target_action(100, 20, 700, 700, layer_count=7)
    rail = resolve_target_action(10, 300, 700, 700, layer_count=7)
    marker = resolve_target_action(500, 500, 700, 700, layer_count=7)
    ok = (
        feed.action is TargetAction.FEED
        and rail.action is TargetAction.LAYER_TOGGLE
        and marker.action is TargetAction.MARKER
    )
    if ok:
        return GateResult.passed(
            "deterministic interaction model covers feed tabs, layer rail, and marker drop"
        )
    return GateResult.failed("deterministic interaction model did not resolve all targets")


def _verify_audio(
    client: ObsClient,
    *,
    manifest: dict[str, Any],
    scene: str,
    console_source: str,
    out_dir: Path,
    width: int,
    height: int,
    audio_input_kind: str,
    settle_s: float,
) -> None:
    silent = out_dir / "audio_silent.png"
    tone = out_dir / "audio_tone.png"
    try:
        client.request(
            "SetInputSettings",
            {"inputName": console_source, "inputSettings": {"feed": 0}, "overlay": True},
        )
        time.sleep(settle_s)
        _capture_png(client, source_name=scene, out_path=silent, width=width, height=height)
        manifest["captures"]["audio_silent"] = str(silent)

        tone_path = (out_dir / "controlled_tone.wav").resolve()
        _write_tone(tone_path)
        media_name = f"{console_source} / controlled tone"
        # ffmpeg_source resolves local_file against OBS's own CWD, not ours — it must
        # be absolute or the media never plays and the audio meter never reacts.
        _create_or_update_input(
            client,
            scene=scene,
            name=media_name,
            kind=audio_input_kind,
            settings={
                "is_local_file": True,
                "local_file": str(tone_path),
                "looping": True,
                "restart_on_activate": True,
            },
        )
        client.request(
            "CreateSourceFilter",
            {
                "sourceName": media_name,
                "filterName": "SynthOBS audio envelope",
                "filterKind": "fractisynth_audio",
                "filterSettings": {},
            },
        )
        try:
            client.request(
                "TriggerMediaInputAction",
                {
                    "inputName": media_name,
                    "mediaAction": "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART",
                },
            )
        except ObsScenarioError:
            pass
        time.sleep(max(settle_s, 1.0))
        _capture_png(client, source_name=scene, out_path=tone, width=width, height=height)
        manifest["captures"]["audio_tone"] = str(tone)

        before, w0, h0 = _png_to_rgba_bytes(silent)
        after, w1, h1 = _png_to_rgba_bytes(tone)
        if (w0, h0) != (w1, h1):
            raise ValueError(f"audio captures differ in size: {w0}x{h0} vs {w1}x{h1}")
        delta = score_audio_meter_delta(before, after, w0, h0, channels=4)
        x, y, rw, rh = delta.roi
        metrics = {
            "width": delta.width,
            "height": delta.height,
            "channels": delta.channels,
            "roi_x": x,
            "roi_y": y,
            "roi_width": rw,
            "roi_height": rh,
            "compared_pixels": delta.compared_pixels,
            "mean_abs_delta": delta.mean_abs_delta,
            "max_abs_delta": delta.max_abs_delta,
            "threshold": delta.threshold,
        }
        if delta.passed:
            set_gate(
                manifest,
                "audio_reactivity",
                GateResult.passed("silent/tone audio-meter ROI delta passed", **metrics),
            )
        else:
            set_gate(
                manifest,
                "audio_reactivity",
                GateResult.failed(
                    "silent/tone audio-meter ROI delta was below threshold",
                    **metrics,
                ),
            )
    except ObsScenarioError as exc:
        set_gate(
            manifest,
            "audio_reactivity",
            GateResult.skipped("controlled OBS audio source unavailable", error=str(exc)),
        )
    except (OSError, ValueError) as exc:
        set_gate(manifest, "audio_reactivity", GateResult.failed(str(exc)))


def _verify_provenance(
    client: ObsClient,
    *,
    manifest: dict[str, Any],
    scene: str,
    console_source: str,
    out_dir: Path,
    width: int,
    height: int,
    settle_s: float,
) -> None:
    path = out_dir / "telemetry_hud.png"
    try:
        client.request(
            "SetInputSettings",
            {"inputName": console_source, "inputSettings": {"feed": 5}, "overlay": True},
        )
        time.sleep(settle_s)
        _capture_png(client, source_name=scene, out_path=path, width=width, height=height)
        manifest["captures"]["telemetry_hud"] = str(path)
        rec = verify_png(path)
        summary = record_summary(rec)
        set_gate(
            manifest,
            "provenance_lsb",
            GateResult.passed("Telemetry HUD LSB strip verified from live capture", **summary),
        )
    except ProvenanceError as exc:
        manifest["fallbacks"]["provenance"] = (
            "LSB verification failed; use native render-target readback when available, "
            "or the HUD visible signature strip as the survivable capture fallback."
        )
        set_gate(
            manifest,
            "provenance_lsb",
            GateResult.failed("Telemetry HUD LSB strip did not verify", error=str(exc)),
        )
    except ObsScenarioError as exc:
        set_gate(
            manifest,
            "provenance_lsb",
            GateResult.skipped("Telemetry HUD capture unavailable", error=str(exc)),
        )


def main(argv: list[str] | None = None) -> int:
    stamp = utc_stamp()
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default=f"SynthOBSVerify-{stamp}")
    parser.add_argument("--out", default=str(_ROOT / "output" / "live" / stamp))
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--url", default="ws://localhost:4455")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--source-name", default=f"SynthOBS Scenario Console {stamp}")
    parser.add_argument("--audio-input-kind", default="ffmpeg_source")
    parser.add_argument("--settle", type=float, default=1.0)
    parser.add_argument("--verify-audio", action="store_true")
    parser.add_argument("--verify-provenance", action="store_true")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Return non-zero on any non-pass gate; default writes skips for unavailable OBS.",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    manifest = initial_manifest(
        scene=args.scene,
        url=args.url,
        width=args.width,
        height=args.height,
    )
    client = ObsClient(args.url, args.password)
    try:
        try:
            client.connect()
        except Exception as exc:  # noqa: BLE001 - live probe records exact environment error
            set_gate(
                manifest,
                "connection",
                GateResult.skipped("OBS websocket unavailable", error=str(exc), url=args.url),
            )
            if args.verify_audio:
                set_gate(
                    manifest,
                    "audio_reactivity",
                    GateResult.skipped("OBS websocket unavailable"),
                )
            if args.verify_provenance:
                set_gate(
                    manifest,
                    "provenance_lsb",
                    GateResult.skipped("OBS websocket unavailable"),
                )
            write_manifest(out_dir, manifest)
            print(json.dumps(manifest["gates"], indent=2, sort_keys=True))
            return manifest_exit_code(manifest, require_live=args.require_live)

        version = client.request("GetVersion")
        manifest["obs"] = {
            "connected": True,
            "obs_version": version.get("obsVersion", ""),
            "websocket_version": version.get("obsWebSocketVersion", ""),
        }
        set_gate(manifest, "connection", GateResult.passed("OBS websocket identified"))

        _ensure_scene(client, args.scene)
        base_width, base_height = _video_settings(client)
        manifest["obs"]["base_canvas"] = {"width": base_width, "height": base_height}
        settings = {"feed": 0, "width": args.width, "height": args.height}
        _create_or_update_input(
            client,
            scene=args.scene,
            name=args.source_name,
            kind="fractisynth_console",
            settings=settings,
        )
        manifest["sources"]["console"] = args.source_name
        try:
            transform = _fit_scene_item(
                client,
                scene=args.scene,
                source=args.source_name,
                base_width=base_width,
                base_height=base_height,
                source_width=args.width,
                source_height=args.height,
            )
            set_gate(
                manifest,
                "dashboard_fit_to_canvas",
                GateResult.passed("console source scaled to OBS base canvas", **transform),
            )
        except ObsScenarioError as exc:
            set_gate(
                manifest,
                "dashboard_fit_to_canvas",
                GateResult.skipped("OBS scene-item transform unavailable", error=str(exc)),
            )

        set_gate(manifest, "interaction_model", _interaction_gate())

        if args.verify_audio:
            _verify_audio(
                client,
                manifest=manifest,
                scene=args.scene,
                console_source=args.source_name,
                out_dir=out_dir,
                width=args.width,
                height=args.height,
                audio_input_kind=args.audio_input_kind,
                settle_s=args.settle,
            )
        if args.verify_provenance:
            _verify_provenance(
                client,
                manifest=manifest,
                scene=args.scene,
                console_source=args.source_name,
                out_dir=out_dir,
                width=args.width,
                height=args.height,
                settle_s=args.settle,
            )

        manifest_path = write_manifest(out_dir, manifest)
        print(f"SCENARIO MANIFEST -> {manifest_path}")
        print(json.dumps(manifest["gates"], indent=2, sort_keys=True))
        return manifest_exit_code(manifest, require_live=args.require_live)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
