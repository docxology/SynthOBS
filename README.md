# SynthOBS & FractiSynth (v1.618)

> A golden-ratio broadcast console and native `libobs` transducer, phase-locked to
> the living solar wavefield.

SynthOBS turns OBS Studio from a static traffic cop into a living **Omniversal
Observatory, Laboratory, and Expedition Ship**. Everything — layout, font scaling,
audio compression, scene transitions — is scaled natively by **El Gran Sol's Fractal
Constant** ($\varphi = 1.618\ldots$, the golden ratio) and tuned in real time by a
**Solar Wavefield Oscillator** that consumes live NOAA space-weather telemetry.

Two layers, one constant:

- **SynthOBS** — the Vessel Console: a recursive golden-ratio layout matrix
  (primary output = $1/\varphi \approx 61.8\%$ of canvas) + a 3-mode, 7-button
  console + a persistent command line. Shipped as an `obspython` script.
- **FractiSynth** — the Transducer Core: a native C `libobs` plugin with a
  $\varphi$-scaling video filter and a $\varphi$-soft-limiter audio filter, both
  driven by the shared SWO vector and a background `libcurl` telemetry thread.

A **tested Python engine** (`src/synthobs`) is the verified source of truth; the C
plugin and the obspython script mirror it. The φ literal, the SWO formula, and the
fail-closed rule are pinned identical across all three.

## Layout

```
src/synthobs/        tested engine (constants, layout, telemetry, swo, dsp, console, commands, engine)
plugin/fractisynth/  native libobs C plugin (CMake + src/fractisynth.c + locale)
plugin/synthobs/     obspython console script (synthobs_console.py)
scripts/             thin orchestrators (generate_figures.py)
manuscript/          Technical Design Blueprint (brand voice)
tests/               zero-mock suite, ≥90% coverage on src/
ISA.md               Ideal State Artifact — system of record
```

## Test

```bash
# From the template root (the project is symlinked into projects/working/SynthOBS)
uv run pytest projects/working/SynthOBS/tests/ --cov=synthobs --cov-report=term-missing
```

848 tests, **94.85%** coverage, no mocks (HTTP exercised via `pytest-httpserver`,
real numeric examples, fixed seeds).

## Regenerate figures

```bash
uv run python projects/working/SynthOBS/scripts/generate_figures.py
# → output/figures/{goldilocks_layout,golden_spiral,swo_calibration,phi_soft_limiter}.png
```

## Build the native plugin (FractiSynth)

```bash
cd plugin/fractisynth
cmake -B build -DCMAKE_BUILD_TYPE=Release   # requires libobs dev headers + libcurl
cmake --build build
```

Drop the built module into your OBS `plugins/` (or `obs-plugins/64bit/`) directory.
Without `libcurl` the SWO runs on its default vector and logs a warning.

## Install the SynthOBS console

In OBS: **Tools → Scripts → +** and select `plugin/synthobs/synthobs_console.py`.
The script exposes the global command line:

```text
/mode --observatory | --lab | --ship
/transducer bind source_cam_01 --ratio=1.618034
/swo calibrate --flux=130 --spots=3 --target=AR4465
```

## Design principles

- **Fail closed.** Invalid, stale, zeroed, or absent telemetry → Hold State, never a
  guessed average. Enforced in the telemetry client, the SWO, the command parser,
  and the libcurl thread.
- **Single source of truth.** All math lives in `src/synthobs`; the plugin and the
  script consume it. Scripts only do I/O and visualization (thin orchestrator).
- **No mocks.** Real HTTP, real numbers, deterministic.

## License

MIT. Project context: the FractiAI / El Gran Sol corpus.
