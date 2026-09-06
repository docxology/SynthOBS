# `scripts/` — thin orchestrators

These scripts import the tested engine (`src/synthobs`) and do argparse, path
bootstrap, I/O, and matplotlib/live-OBS coordination only; business logic lives in
`src/synthobs/` and is covered by `tests/`. The contract + inventory + gotchas for
agents are in [`AGENTS.md`](AGENTS.md).

| Script | Purpose | Delegates to | Run command |
| --- | --- | --- | --- |
| `generate_figures.py` | Renders the 13 deterministic analytical figures from the engine and copies the 3 versioned live OBS captures → `output/figures/`; writes `figure_manifest.json` (`FIGURE_FILES` is pinned by the doc-contract test) | `synthobs` engine + matplotlib (`figures` extra) | `uv run python scripts/generate_figures.py` |
| `audit_scholarship.py` | Fail-closed validation of the scholarship source/claim ledger, bibliography keys, repo paths, and evidence artifacts; exits 1 on any error | `synthobs.scholarship.validate_scholarship_ledger` | `uv run python scripts/audit_scholarship.py` |
| `verify_provenance_strip.py` | Extracts and verifies the LSB-embedded HUD provenance signature from a captured PNG; `--hmac-key-env` enables opt-in keyed verification without serializing the key | `synthobs.provenance` (`extract_lsb`, `TelemetryRecord`) | `uv run python scripts/verify_provenance_strip.py <hud.png> --json` |
| `promote_obs_evidence.py` | Fail-closed promotion boundary from a passing live scenario directory into the versioned evidence bundle `manuscript/assets/obs/`; recomputes hashes, PNG dimensions, and WAV metadata | self-contained promotion gate (`synthobs.live_scenario.v2` manifest) | `uv run python scripts/promote_obs_evidence.py output/live/<ts>` |
| `obs_scenario_probe.py` | Live **verification** harness (obs-websocket v5) — creates a verification scene, captures `scene_render`/`audio_silent`/`audio_tone`/`telemetry_hud`, and writes `manifest.json` with explicit pass/fail/skip gates; flags `--verify-audio`, `--verify-provenance`, `--require-live` | `synthobs.verification`, `synthobs.provenance`, `synthobs.interaction`, `scripts.verify_provenance_strip` | `uv run python scripts/obs_scenario_probe.py --out output/live/<ts> --password "$OBS_WEBSOCKET_PASSWORD" --verify-audio --verify-provenance --require-live` |
| `obs_ws_probe.py` | Live render gate — connects, ensures the FractiSynth test scene is active, enumerates sources/filters, and screenshots the scene. Proves the plugin renders in real OBS (not just that the module loads) | self-contained obs-websocket v5 client (`websocket-client`, dev extra) | `uv run python scripts/obs_ws_probe.py --password "$OBS_WEBSOCKET_PASSWORD"` |
| `package_smoke.py` | Installs the newest `dist/synthobs-*.whl` into a fresh no-index virtual environment and imports the stdlib-only engine in isolated (`-I`) mode | `venv`/`subprocess` against the built wheel | `uv build && uv run python scripts/package_smoke.py` |

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
All validation logic lives in the tested engine module
[`../src/synthobs/scholarship.py`](../src/synthobs/scholarship.py); the script only
reads `docs/scholarship_sources.json` + `manuscript/references.bib` and delegates.
