# `scripts/` — thin orchestrators

These are **thin orchestrators**: they import the tested engine (`src/synthobs`), do I/O,
matplotlib, and live-OBS coordination only, and implement no engine math themselves. The
live-OBS scripts are interactive instruments (they talk to a real OBS process over
obs-websocket), so they are not unit-tested modules — they live here by design.

| Script | What it does |
| --- | --- |
| `generate_figures.py` | Renders the five manuscript figures from the engine: `goldilocks_layout`, `golden_spiral`, `swo_calibration`, `phi_soft_limiter`, `gateway_lock` → `output/figures/`. `FIGURE_FILES` is the manifest the doc-contract test pins. |
| `obs_ws_probe.py` | Live render gate — connects, ensures the FractiSynth test scene is active, enumerates sources/filters, and screenshots the scene. Proves the plugin renders in real OBS (not just that the module loads). |
| `obs_scenario_probe.py` | Live **verification** harness (obs-websocket v5) — creates a verification scene, captures `audio_silent`/`audio_tone`/`telemetry_hud`, and writes `manifest.json` with explicit pass/fail/skip gates. Flags: `--verify-audio`, `--verify-provenance`, `--require-live`. |
| `verify_provenance_strip.py` | Extracts and verifies the LSB-embedded HUD provenance signature from a captured PNG, using the same checksum/validation as `src/synthobs/provenance.py`. |

## Live-OBS gates

The plugin must be built and installed first ([`../docs/build-and-install.md`](../docs/build-and-install.md)),
OBS running with obs-websocket enabled. All five `obs_scenario_probe.py` gates pass against
real OBS 32.1.2:

```bash
uv run python scripts/obs_scenario_probe.py --out output/live/<ts> --verify-audio --verify-provenance
uv run python scripts/verify_provenance_strip.py output/live/<ts>/telemetry_hud.png --json
```

See [`../docs/native-plugin.md`](../docs/native-plugin.md) ("Verifying a source renders")
for the methodology and the live-OBS pitfalls these scripts work around.
