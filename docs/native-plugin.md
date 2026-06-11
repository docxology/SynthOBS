# The Native libobs Plugin

[`plugin/fractisynth/`](../plugin/fractisynth) is a real OBS Studio plugin written in C
against `libobs`. It is the production transducer — a faithful native mirror of the
tested Python engine — and it is **verified to load and run live in OBS 32.1.2**. This
page documents its structure, the two filters, the telemetry thread, and the lifecycle.

Source: [`plugin/fractisynth/src/fractisynth.c`](../plugin/fractisynth/src/fractisynth.c)
(≈600 lines). Effect: `data/fractisynth.effect`. Build: `CMakeLists.txt` + `build.sh`.

## What it registers

`obs_module_load()` registers two filters **and a generated input source**, then starts
the telemetry thread. When built against a matching Qt (see below) `obs_module_post_load()`
also adds a frontend dock.

| id | Type | Role |
| --- | --- | --- |
| `fractisynth_video` | `OBS_SOURCE_TYPE_FILTER` (video) | φ-scaled spatial calibration + SWO-driven shader displacement |
| `fractisynth_audio` | `OBS_SOURCE_TYPE_FILTER` (audio) | φ-knee soft limiter (the same curve as `dsp.phi_soft_limit_sample`) |
| `fractisynth_console` | `OBS_SOURCE_TYPE_INPUT` (video, custom-draw) | the addable, draggable **φ Wavefield Console** — procedurally renders the live gateway state |
| `fractisynth_dock` | frontend dock (optional Qt build) | a live gateway-gauge pane in the OBS window chrome |

The **console source** (`fcv_*` callbacks) draws a full-screen quad through its own
procedural shader `fractisynth_console.effect` (no input image — `gs_draw_sprite(NULL,
…)`), feeding it the live `swo_phase` / `lock_strength` / `wind_phase` / `egs_key`
uniforms via the mutex-guarded `swo_read()` + `gateway_read()`. It is what makes SynthOBS
appear in the Sources "+" menu. The **dock** is a moc-free, text-free Qt `QWidget`
([build-and-install.md](build-and-install.md#the-optional-frontend-dock)) reading the same
state through the C accessor `fractisynth_get_state()`.

The φ literal is pinned: `#define EGS_PHI 1.61803398875f`, asserted equal to the Python
`PHI` to ≥9 significant digits by `test_plugin_artifacts.py` (ISC-60).

## The video filter (`fsv_*`)

Full OBS lifecycle: `create / destroy / update / get_defaults / get_properties /
video_tick / video_render / get_width / get_height`.

- **Calibration.** `fsv_video_render` computes an internal φ-harmonic box
  (`source_w / EGS_PHI`) for reference. The filter does **not** resize its source:
  `get_width`/`get_height` pass the target's base dimensions straight through via
  `obs_source_get_base_width(obs_filter_get_target())` — the **non-recursive** idiom.
  (Returning `obs_source_get_width(obs_filter_get_parent())` here re-enters the same
  callback and stack-overflows OBS at scene load — see the gotchas at the bottom.)
- **Shader.** It loads `fractisynth.effect` from the module data dir. If the effect is
  missing or fails to compile, the filter falls back to a clean pass-through (never a
  black frame).
- **SWO coupling (fail-closed).** Each frame reads the oscillator with `swo_read()`,
  which returns the phase vector **and** the calibration flag under one lock. If the
  oscillator has never locked, the contributed phase is **zero** — no displacement.
  This enforces "no calibration ⇒ no modulation" on the consumer side.
- **Knobs (7 OBS sliders).** `displacement_gain` (0–4), `spiral_density` (4–32 φ-spiral
  arms), `interference` (0–1 holographic fringe intensity), `hydrogen_tint` (0–1 H-alpha
  resonance red), `hex_opacity` (0–1 honeycomb lattice), `grid_opacity` (0–1 HOLO_GRID).

### The shader

`fractisynth.effect` composes six layers, every one gated by `lock_strength` so an
uncalibrated stream stays clean: (1) φ-spiral displacement, (2) holographic `|a+b|²`
interference fringes at spatial frequency ∝ `K_EGS` animated by the wind phase,
(3) hydrogen H-alpha (656.28 nm) resonance tint at the fringe antinodes, (4) a
honeycomb hex tri-axis lattice, (5) a gentle ~0.5 Hz "pulsar breathing" pulse (the
29.94 Hz Crab-pulsar clock divided down — never strobed), and (6) the golden HOLO_GRID.
Uniforms set per-frame from `fractisynth.c`: `egs_key`, `lock_strength`, `wind_phase`,
`hydrogen_tint`, `interference`, `hex_opacity`, `spiral_density` (plus the existing
`swo_phase`, `displacement`, `elapsed`, `grid_opacity`, `uv_size`).

## The audio filter (`fsa_*`)

Full lifecycle plus `filter_audio`. The hot path is `phi_soft_limit_sample()`, the
byte-for-byte analog of the Python limiter:

- knee at `threshold · (1/φ)`; identity below the knee;
- `tanh` compression above the knee; never hard-clips;
- NaN → 0, ±Inf → ±ceiling (the `isfinite` guard), so a pathological buffer can't
  produce garbage.

It iterates audio planes up to `MAX_AV_PLANES` with a null-guard per plane — the
standard, safe OBS audio-filter idiom.

## The Solar Wavefield Oscillator core

A single process-global struct guarded by a pthread mutex:

```c
typedef struct fractisynth_swo {
    float active_f107_flux;
    int   monitored_sunspots;
    float system_phase_vector;   /* φ · (flux / spots) */
    bool  is_calibrated;
} fractisynth_swo_t;
```

- `synchronize_swo_calibration()` — the writer. Fail-closed guard:
  `if (current_flux <= 0.0f || active_spots <= 0)` → hold. Also rejects non-finite
  vectors.
- `swo_phase_vector()` — locked read of the vector alone.
- `swo_read(&v)` — locked read of the vector **and** `is_calibrated` together, so the
  render path can enforce the fail-closed rule atomically.

## The telemetry thread (hardened)

A background libcurl thread polls the two NOAA SWPC endpoints every 60 s and locks the
oscillator. Built without libcurl (`-DHAVE_CURL` off), the oscillator simply runs on its
default vector and a warning is logged. See [telemetry.md](telemetry.md) for the feeds
and the fail-closed contract.

The thread is built to never hang OBS shutdown — these protections were added after an
adversarial (cross-vendor) review of the exact paths a live smoke-load cannot exercise:

| Hazard | Protection |
| --- | --- |
| `pthread_join` blocking on a stalled NOAA socket at unload | a libcurl `XFERINFOFUNCTION` abort callback cancels any in-flight transfer the instant the shutdown flag clears |
| Unbounded DNS / connect on a multithreaded host | `CURLOPT_NOSIGNAL=1` + `CURLOPT_CONNECTTIMEOUT=5` + `CURLOPT_TIMEOUT=10` |
| `curl_global_init` from a worker thread (not thread-safe) | moved to `obs_module_load` / `obs_module_unload`, once, on the load thread |
| Second blocking fetch during shutdown | the worker checks the shutdown flag between the two fetches and skips the second |
| Joining an indeterminate `pthread_t` if spawn failed | a `g_thread_started` flag gates the join; `pthread_create`'s return is checked |
| Torn cross-thread shutdown flag | `atomic_bool` with `atomic_load`/`atomic_store` |

In practice: a real OBS session loaded the module, locked a live vector, and **quit
cleanly** with no shutdown delay (see [build-and-install.md](build-and-install.md)).

## Lifecycle summary

```
obs_module_load()
  ├─ obs_register_source(&fractisynth_video_filter)
  ├─ obs_register_source(&fractisynth_audio_filter)
  ├─ curl_global_init(CURL_GLOBAL_DEFAULT)        // once, here (HAVE_CURL)
  └─ telemetry_thread_start()                     // spawns the libcurl poller

… runtime: filters read swo_read(); telemetry thread re-locks every 60 s …

obs_module_unload()
  ├─ telemetry_thread_stop()                      // signal + bounded join (abort cb)
  └─ curl_global_cleanup()                        // once, here (HAVE_CURL)
```

## Relationship to the Python engine

The C plugin is a *mirror*, not the source of truth. The φ literal, the SWO formula
(`φ · flux/spots`), the fail-closed rule, and the soft-limiter curve are identical to
[`src/synthobs`](../src/synthobs), and the pin between them is a **test** — drift is a
failure, not a silent divergence. When in doubt about intended behavior, the Python
engine and its 859-test suite are authoritative; the C plugin makes that behavior run
natively inside OBS.

## OBS effect-language gotchas (hard-won)

The OBS effect language is a restricted HLSL subset; three quirks each rendered a
shader broken-but-compiling during development:

1. **Global `static const float3 X = {..}` reads back as ZERO at runtime.** OBS does
   not initialise global shader constants, so a shader that builds its colours from
   global constants renders **pure black** (it still compiles). Construct palette
   colours as **local** `float3(...)` *inside* the pixel shader instead. (The console
   source — built entirely from constants — was pure black until this was fixed.)
2. **`static const float3 X = float3(..)` is a parse error** (`Expected '{'`). Global
   constant initialisers must use brace-init `= {a, b, c}` — but see (1): prefer locals.
3. **`#define M (a / b)` arithmetic macros are a parse error** (`Expected identifier`).
   Use a precomputed literal: `#define PULSAR_BREATH 0.499`.

## Verifying a source renders (don't trust window screenshots)

Two traps make plugin verification deceptive:

- **`[fractisynth] loaded` in the log does NOT mean OBS survived.** A `get_width`
  recursion (or any bad callback) crashes OBS at *scene load*, milliseconds after the
  module-load line. The acceptance gate counts OBS `.ips` crash reports
  (`~/Library/Logs/DiagnosticReports/OBS*.ips`) before/after and asserts OBS stays
  alive through scene load — never just the load log.
- **Window screenshots are unreliable** (z-order, Spaces, screen-recording permission).
  Use **obs-websocket** `GetSourceScreenshot` on the **scene** (the real compositor) to
  get the rendered pixels independent of window state. Note: `GetSourceScreenshot` of a
  `CUSTOM_DRAW` *source directly* returns black — a measurement artifact — so screenshot
  the **scene** that contains it, and validate the method with a known `color_source`.
