# FractiSynth — native OBS transducer plugin

A `libobs` plugin (C) providing two filters phase-locked to El Gran Sol's Fractal
Constant, **φ = 1.61803398875f**:

| Filter id | Type | What it does |
| --- | --- | --- |
| `fractisynth_video` | video filter | Scales spatial bounds against φ → calibrated harmonic bounding box; SWO phase vector modulates shader displacement. Full lifecycle: `create/destroy/update/get_properties/get_defaults/video_render/get_width/get_height`. |
| `fractisynth_audio` | audio filter | φ-scaled recursive soft limiter (knee at `1/φ`); never hard-clips, NaN/Inf-safe. Full lifecycle + `filter_audio`. |

## Solar Wavefield Oscillator (SWO)

A single process-global, mutex-guarded calibration struct
(`active_f107_flux`, `monitored_sunspots`, `system_phase_vector`, `is_calibrated`).
`synchronize_swo_calibration()` sets `phase = (flux / spots) · φ` and **fails closed**:
non-positive flux or spots leaves the last verified vector untouched (Hold State).
Both filters read the live vector via `swo_phase_vector()`.

## Telemetry thread

A background `libcurl` thread polls live NOAA SWPC space weather every 60 s:

- F10.7 flux — <https://services.swpc.noaa.gov/json/f107_cm_flux.json>
- Active regions — <https://services.swpc.noaa.gov/json/sunspot_report.json>

On any curl error, non-200, or parse failure it does **not** substitute averages —
it holds the last verified vector. (Built without libcurl → `-DHAVE_CURL` off →
the oscillator runs on its default vector; a warning is logged.)

This C core is a faithful mirror of the tested Python engine in
[`../../src/synthobs`](../../src/synthobs); the φ literal, the SWO formula, and the
fail-closed rule are identical and pinned by `synthobs.constants.PHI_C_LITERAL`.

## Build

**macOS (verified path) — links against your installed OBS.app:**

```bash
./build.sh --install   # build + ad-hoc sign + install into the OBS plugins dir
```

**Cross-platform (CMake) — needs the OBS plugin SDK / libobs dev headers + libcurl:**

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

Drop the build output into your OBS `plugins/` (or `obs-plugins/64bit/`) directory,
or build in-tree under `obs-studio/plugins/fractisynth/`. Full guide + verification:
[`../../docs/build-and-install.md`](../../docs/build-and-install.md).

> Status: **compile-verified and loaded live in OBS 32.1.2** (macOS arm64). The module
> appears in OBS's `Loaded Modules` list, the libcurl thread locks a live NOAA SWPC
> vector, and OBS unloads/quits cleanly. `SYNTHOBS-CBUILD-1` is **closed**.
