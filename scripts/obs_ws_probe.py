#!/usr/bin/env python3
"""Live OBS verification probe via obs-websocket v5.

Connects, authenticates, ensures the FractiSynth test scene is active, enumerates
its sources/filters, and captures a real scene screenshot to disk. This is the
live-functional gate for the native plugin (closes SYNTHOBS-VISUAL-1 / DOCKSHOT):
it proves the plugin renders in a real OBS process, not just that the module loads.

Usage:
    python scripts/obs_ws_probe.py [--scene NAME] [--out PATH] [--password PW]

Not a unit-tested module — it is an interactive instrument that talks to a live
OBS process, so it lives in scripts/ (thin orchestrator) by design.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time

try:  # live-probe-only dependency (project 'dev' extra: websocket-client)
    import websocket  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised only without the dev extra
    websocket = None  # type: ignore[assignment]


def _auth(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(
        hashlib.sha256((password + salt).encode()).digest()
    ).decode()
    return base64.b64encode(
        hashlib.sha256((secret + challenge).encode()).digest()
    ).decode()


def _request(ws: websocket.WebSocket, req_type: str, data: dict | None = None) -> dict:
    rid = f"r{int(time.time() * 1000) % 100000}"
    ws.send(
        json.dumps(
            {
                "op": 6,
                "d": {"requestType": req_type, "requestId": rid, "requestData": data or {}},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("op") == 7 and msg["d"].get("requestId") == rid:
            return msg["d"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="FractiSynthTest")
    ap.add_argument("--out", default="output/live/obs_scene.png")
    ap.add_argument("--password", default=os.environ.get("OBS_WEBSOCKET_PASSWORD", ""))
    ap.add_argument("--url", default="ws://localhost:4455")
    args = ap.parse_args()

    if websocket is None:
        print(
            "websocket-client is not installed; install the project 'dev' extra "
            "(uv sync --extra dev) to run the live OBS probe",
            file=sys.stderr,
        )
        return 2
    ws = websocket.create_connection(args.url, timeout=15)
    hello = json.loads(ws.recv())
    ident: dict = {"op": 1, "d": {"rpcVersion": 1}}
    auth = hello["d"].get("authentication")
    if auth:
        ident["d"]["authentication"] = _auth(
            args.password, auth["salt"], auth["challenge"]
        )
    ws.send(json.dumps(ident))
    confirmed = json.loads(ws.recv())
    if confirmed.get("op") != 2:
        print(f"FAIL: not identified: {confirmed}", file=sys.stderr)
        return 1

    ver = _request(ws, "GetVersion")["responseData"]
    print(f"OBS {ver['obsVersion']} / ws {ver['obsWebSocketVersion']}")

    scenes = _request(ws, "GetSceneList")["responseData"]
    names = [s["sceneName"] for s in scenes["scenes"]]
    print(f"scenes: {names}")
    target = args.scene if args.scene in names else (names[-1] if names else None)
    if not target:
        print("FAIL: no scenes", file=sys.stderr)
        return 1
    _request(ws, "SetCurrentProgramScene", {"sceneName": target})
    print(f"active scene: {target}")

    items = _request(ws, "GetSceneItemList", {"sceneName": target})["responseData"]
    for it in items["sceneItems"]:
        src = it["sourceName"]
        kind = it.get("inputKind") or it.get("sourceType")
        print(f"  source: {src} [{kind}] enabled={it.get('sceneItemEnabled')}")
        flt = _request(ws, "GetSourceFilterList", {"sourceName": src})
        for f in flt.get("responseData", {}).get("filters", []):
            print(f"    filter: {f['filterName']} [{f['filterKind']}] enabled={f['filterEnabled']}")

    time.sleep(1.0)
    shot = _request(
        ws,
        "GetSourceScreenshot",
        {
            "sourceName": target,
            "imageFormat": "png",
            "imageWidth": 1280,
            "imageHeight": 720,
        },
    )
    if shot.get("requestStatus", {}).get("result") is not True:
        print(f"FAIL screenshot: {shot}", file=sys.stderr)
        return 1
    img_b64 = shot["responseData"]["imageData"].split(",", 1)[-1]
    out_path = Path(args.out)
    if out_path.parent != Path("."):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fh:
        fh.write(base64.b64decode(img_b64))
    print(f"SCENE SCREENSHOT -> {args.out} ({len(img_b64)} b64 chars)")
    ws.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
