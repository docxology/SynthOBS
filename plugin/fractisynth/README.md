# FractiSynth — native OBS transducer plugin

A `libobs` plugin (C) providing three filters plus a generated console source. It
uses the pinned golden-ratio literal for layout/DSP paths and the separate `K_EGS`
literal for the gateway phase path:

| Filter id | Type | What it does |
| --- | --- | --- |
| `fractisynth_video` | video filter | Scales spatial bounds against φ → calibrated harmonic bounding box; SWO phase vector modulates shader displacement. Full lifecycle: `create/destroy/update/get_properties/get_defaults/video_render/get_width/get_height`. |
| `fractisynth_audio` | audio filter | φ-scaled recursive soft limiter (knee at `1/φ`); never hard-clips, NaN/Inf-safe. Full lifecycle + `filter_audio`. |
| `fractisynth_inspector` | video filter | Zoom Inspector loupe with fixed-region/follow-mouse modes, φ-grid, crosshair, and region annotation. |
| `fractisynth_console` | generated video source | Interactive seven-feed synthetic console with Telemetry HUD, Solar Graph, layer rail, and provenance strip. |

## Solar Wavefield Oscillator (SWO)

A single process-global, mutex-guarded calibration struct
(`active_f107_flux`, `monitored_sunspots`, `system_phase_vector`, `is_calibrated`).
`synchronize_swo_calibration()` sets `phase = (flux / spots) · φ` and **fails closed**:
non-positive flux or spots leaves the last verified vector untouched (Hold State).
Both filters read the live vector via `swo_phase_vector()`.

## Telemetry thread

A background `libcurl` thread polls live NOAA SWPC space weather every 60 s:

- F10.7 flux — <https://services.swpc.noaa.gov/json/f107_cm_flux.json>
- Active regions — <https://services.swpc.noaa.gov/json/solar_regions.json>
- Solar wind — <https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json>
- GOES X-ray — <https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json>
- Planetary Kp — <https://services.swpc.noaa.gov/json/planetary_k_index_1m.json>

On any curl error, non-200, or parse failure it holds the last verified vector.
Release builds require libcurl so live telemetry cannot silently enter an
uncalibrated native path.

This C core is the native OBS implementation of selected contracts from the tested
Python engine in [`../../src/synthobs`](../../src/synthobs); the φ literal, the SWO
formula, and the fail-closed rule are pinned by `synthobs.constants.PHI_C_LITERAL`
and checked by static/behavioral tests.

## Build

**macOS (verified path) — links against your installed OBS.app:**

```bash
./build.sh --install   # build + ad-hoc sign + install into the OBS plugins dir
```

**Cross-platform (CMake) — needs the OBS plugin SDK / libobs dev headers + libcurl:**

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release -DOBS_ROOT=/path/to/OBS.app/Contents
cmake --build build
```

Drop the build output into your OBS `plugins/` (or `obs-plugins/64bit/`) directory,
or build in-tree under `obs-studio/plugins/fractisynth/`. Full guide + verification:
[`../../docs/build-and-install.md`](../../docs/build-and-install.md).

> Status: **compile-verified and loaded live in OBS 32.1.2** (macOS arm64). The module
> appears in OBS's `Loaded Modules` list, the libcurl thread locks a live NOAA SWPC
> vector, and OBS unloads/quits cleanly. `SYNTHOBS-CBUILD-1` is **closed**.
