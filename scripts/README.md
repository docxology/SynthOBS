# `scripts/` — thin orchestrators

These are **thin orchestrators**: they import the tested engine (`src/synthobs`), do I/O,
matplotlib, and live-OBS coordination only, and implement no engine math themselves. The
live-OBS scripts are interactive instruments (they talk to a real OBS process over
obs-websocket), so they are not unit-tested modules — they live here by design.

| Script | What it does |
| --- | --- |
| `generate_figures.py` | Renders the 13 deterministic analytical figures from the engine and copies the 3 versioned live OBS captures → `output/figures/`. `FIGURE_FILES` is the manifest the doc-contract test pins. |
| `obs_ws_probe.py` | Live render gate — connects, ensures the FractiSynth test scene is active, enumerates sources/filters, and screenshots the scene. Proves the plugin renders in real OBS (not just that the module loads). |
| `obs_scenario_probe.py` | Live **verification** harness (obs-websocket v5) — creates a verification scene, captures `audio_silent`/`audio_tone`/`telemetry_hud`, and writes `manifest.json` with explicit pass/fail/skip gates. Flags: `--verify-audio`, `--verify-provenance`, `--require-live`. |
| `promote_obs_evidence.py` | Fail-closed promotion boundary from a passing live scenario directory into the versioned manuscript OBS evidence bundle; recomputes hashes, PNG dimensions, and WAV metadata. |
| `verify_provenance_strip.py` | Extracts and verifies the LSB-embedded HUD provenance signature from a captured PNG, using the same checksum/validation as `src/synthobs/provenance.py`; `--hmac-key-env` enables opt-in keyed verification without serializing the key. |
| `package_smoke.py` | Installs a selected wheel into a fresh no-index virtual environment and imports the stdlib-only engine in isolated mode. |

## Live-OBS gates

The plugin must be built and installed first ([`../docs/build-and-install.md`](../docs/build-and-install.md)),
OBS running with obs-websocket enabled. The versioned scenario run records all six
required `obs_scenario_probe.py` gates as passing against real OBS 32.1.2; the
interaction gate is explicitly engine-level and does not claim live click transport:

```bash
uv run python scripts/obs_scenario_probe.py --out output/live/<ts> \
  --password "$OBS_WEBSOCKET_PASSWORD" --verify-audio --verify-provenance --require-live
uv run python scripts/verify_provenance_strip.py output/live/<ts>/telemetry_hud.png --json
uv run python scripts/promote_obs_evidence.py output/live/<ts>
```

The probe's `--password` is optional only when OBS authentication is disabled. For an
authenticated OBS installation, provide the password through the environment or another
secret-bearing shell mechanism; never commit it into a manifest or manuscript.

See [`../docs/native-plugin.md`](../docs/native-plugin.md) ("Verifying a source renders")
for the methodology and the live-OBS pitfalls these scripts work around.

## Scholarship audit

[`audit_scholarship.py`](audit_scholarship.py) validates the machine-readable source
ledger, bibliography keys, local source-of-truth paths, tests, and evidence artifacts.
