# SynthOBS & FractiSynth (v1.618)

> A golden-ratio broadcast console and native `libobs` transducer, calibrated by
> live solar telemetry.

SynthOBS packages a three-mode operator console and a native `libobs` transducer
around tested layout, DSP, telemetry, and interaction contracts. The golden-ratio
constant supplies the layout and DSP rules; a separate EGS gateway key supplies the
solar-wind phase calculation. The Solar Wavefield Oscillator consumes live NOAA
space-weather telemetry and holds its last verified state on invalid input.

Two layers, two pinned constants with separate roles:

- **SynthOBS** — the Vessel Console: a recursive golden-ratio layout matrix
  (primary output = $1/\varphi \approx 61.8\%$ of canvas) + a 3-mode, 7-button
  console + a persistent command line. Shipped as an `obspython` script.
- **FractiSynth** — the Transducer Core: a native C `libobs` plugin with a
  $\varphi$-scaling video filter and a $\varphi$-soft-limiter audio filter, both
  driven by the shared SWO vector and a background `libcurl` telemetry thread.

A **tested Python engine** (`src/synthobs`) is the verified source of truth for the
portable contracts. The C plugin implements native counterparts at the OBS boundary
and is checked against the constants and selected behavioral contracts; the
obspython script imports the engine.

## Public v1 distribution

SynthOBS is public at
[`github.com/docxology/SynthOBS`](https://github.com/docxology/SynthOBS), the
canonical source for the Python engine, native FractiSynth OBS module, obspython
bridge, tests, installation and usage guides, manuscript, citation metadata, and
versioned OBS evidence. Release `v1.618.0` is tagged and published:
[GitHub release](https://github.com/docxology/SynthOBS/releases/tag/v1.618.0) ·
[Zenodo archival deposit, DOI 10.5281/zenodo.21418687](https://doi.org/10.5281/zenodo.21418687)
(concept DOI, always resolves to the latest archived version — the exact
`v1.618.0` deposit is `10.5281/zenodo.21418901`).
Release gates and clean-clone instructions are in [`RELEASE.md`](RELEASE.md).

Author affiliation: **FractiAI / Active Inference Institute**.

## Layout

```
src/synthobs/        tested engine, 15 public modules (constants, layout, telemetry, swo, gateway, dsp, console, commands, interaction, layers, interference, history, provenance, engine, verification)
plugin/fractisynth/  native libobs C plugin (CMake + src/fractisynth.c + locale)
plugin/synthobs/     obspython console script (synthobs_console.py)
scripts/             thin orchestrators (generate_figures.py, obs_scenario_probe.py, obs_ws_probe.py, verify_provenance_strip.py)
lean/                Lean 4 invariant scaffold (console shape + fail-closed gates)
manuscript/          Technical Design Blueprint (brand voice)
tests/               real-input suite, ≥90% coverage on src/
ISA.md               Ideal State Artifact — system of record
```

## Test

```bash
# From a public clone (or this project root)
uv run python -m pytest tests/ --cov=synthobs --cov-report=term-missing

# In the template sidecar checkout, use the symlinked project path instead:
uv run python -m pytest projects/ongoing/Fracti/SynthOBS/tests/ --cov=synthobs --cov-report=term-missing
```

1217 tests, **94.44%** coverage, real I/O (HTTP exercised via `pytest-httpserver`,
real numeric examples, fixed seeds); these values are regenerated from the verification run.

Lean invariant scaffold:

```bash
cd lean
lake build
```

## Regenerate figures

```bash
uv run python scripts/generate_figures.py
```

Package smoke gate:

```bash
uv build
uv run python scripts/package_smoke.py
```

Generated manifest (16 figure entries: 13 analytical figures and 3 promoted live
captures). The manuscript bundle also retains one operator-context screenshot outside
the analytical manifest:

- `output/figures/goldilocks_layout.png`
- `output/figures/golden_spiral.png`
- `output/figures/swo_calibration.png`
- `output/figures/phi_soft_limiter.png`
- `output/figures/gateway_lock.png`
- `output/figures/architecture_layers.png`
- `output/figures/command_parse_pipeline.png`
- `output/figures/telemetry_pipeline.png`
- `output/figures/telemetry_thread.png`
- `output/figures/golden_split.png`
- `output/figures/phi_matrix.png`
- `output/figures/parity_bridge.png`
- `output/figures/plugin_lifecycle.png`
- `output/figures/obs_scene_render.png`
- `output/figures/obs_telemetry_hud.png`
- `output/figures/obs_audio_tone.png`
- `output/figures/figure_manifest.json` — source-labelled manifest separating 13 analytical and 3 live-capture figures; operator-context screenshots remain versioned manuscript assets and are not promoted as analytical evidence

## Scholarship and citation

The manuscript uses verified primary OBS/libobs and NOAA product documentation,
peer-reviewed reproducibility and visualization literature, and explicit project
evidence boundaries. The source-to-claim ledger is in
[`docs/scholarship.md`](docs/scholarship.md) and
[`docs/scholarship_sources.json`](docs/scholarship_sources.json); reusable citation
metadata is in [`CITATION.cff`](CITATION.cff).

### How to cite

```text
Friedman, Daniel Ari. SynthOBS & FractiSynth v1.618.0. FractiAI /
Active Inference Institute. https://github.com/docxology/SynthOBS/releases/tag/v1.618.0
DOI: 10.5281/zenodo.21418687
```

See [`docs/scholarship.md`](docs/scholarship.md) for the claim-to-evidence and
version-specific citation policy, and [`CITATION.cff`](CITATION.cff) for
machine-readable citation metadata.

## Future work

The single scoped backlog is [`TODO.md`](TODO.md). Completed phases and historical
decisions remain in [`ROADMAP.md`](ROADMAP.md) and [`ISA.md`](ISA.md).

## Verify a Telemetry HUD provenance strip

```bash
uv run python projects/ongoing/Fracti/SynthOBS/scripts/verify_provenance_strip.py \
  projects/ongoing/Fracti/SynthOBS/manuscript/assets/obs/obs_telemetry_hud.png --json --expect-signature 8b1f58c1
```

The verifier extracts the LSB-embedded HUD payload from a PNG, recomputes the
checksum, and reports the recovered flux, active-region count, wind speed, lock
strength, phase bias, timestamp, and on-screen signature. RGB and RGBA screenshots are
both accepted; tampered or undersized captures fail closed.

## Run the live OBS scenario verifier

```bash
uv run python projects/ongoing/Fracti/SynthOBS/scripts/obs_scenario_probe.py \
  --out output/live/$(date -u +%Y%m%dT%H%M%SZ) \
  --password "$OBS_WEBSOCKET_PASSWORD" \
  --verify-audio --verify-provenance --require-live
```

The harness talks to obs-websocket v5, creates/selects a verification scene, adds a
`fractisynth_console` source, captures `scene_render.png`, `audio_silent.png`,
`audio_tone.png`, and `telemetry_hud.png`, then writes `manifest.json`. If OBS or a
controlled audio route is unavailable, the relevant gate is marked `skip` with a reason;
use `--require-live` when a missing, skipped, failed, or visually blank live gate should
fail the command. The promoted manuscript bundle contains all five evidence assets:
scene, HUD, tone, silent baseline, and controlled WAV. The live manifest names the
same files and records the exact hashes and audio metadata used by the comparison.

After a passing run, promote its exact bytes into the versioned manuscript bundle:

```bash
uv run python projects/ongoing/Fracti/SynthOBS/scripts/promote_obs_evidence.py output/live/<ts>
```

## Build the native plugin (FractiSynth)

```bash
cd plugin/fractisynth
cmake -B build -DCMAKE_BUILD_TYPE=Release -DOBS_ROOT=/path/to/OBS.app/Contents
cmake --build build
```

Drop the built module into your OBS `plugins/` (or `obs-plugins/64bit/`) directory.
Release builds require `libcurl` so live NOAA telemetry cannot silently enter an
uncalibrated native path.

## Install the SynthOBS console

In OBS: **Tools → Scripts → +** and select `plugin/synthobs/synthobs_console.py`.
The script exposes the global command line:

```text
/mode --observatory | --lab | --ship
/transducer bind source_cam_01 --ratio=1.618034
/swo calibrate --flux=130 --spots=3 --target=AR4465
/dashboard plan --name=Awareness
/dashboard build --name=Awareness
```

The native console exposes seven clickable feed targets (Wavefield, Hex,
Interference, Spectral, Spiral, Telemetry HUD, Solar Graph), a layer-toggle rail, and
a marker-drop area. Solar Graph metrics cover wind speed, density, temperature,
GOES X-ray flux, and Kp index. The φ harmonic audio limiter now also exports
post-limiter RMS, peak, and reactivity into the console shader, Telemetry HUD, and dock
so the synthetic feeds visibly breathe with stream audio.

## Design principles

- **Fail closed.** Invalid, stale, zeroed, or absent telemetry → Hold State, never a
  guessed average. Enforced in the telemetry client, the SWO, the command parser,
  and the libcurl thread.
- **Single source of truth.** All math lives in `src/synthobs`; the plugin and the
  script consume it. Scripts only do I/O and visualization (thin orchestrator).
- **Real I/O only.** Real HTTP, real numbers, deterministic.
- **Proof scaffolding where it pays.** Lean pins structural invariants; Python/C tests
  remain the authority for floating-point math, rendering, and live I/O.

## License

MIT. Project context: the FractiAI / El Gran Sol corpus.
