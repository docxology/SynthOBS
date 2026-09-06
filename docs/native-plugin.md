# The Native libobs Plugin

[`plugin/fractisynth/`](../plugin/fractisynth) is a real OBS Studio plugin written in C
against `libobs`. It is the production transducer: an OBS-bound implementation of
the tested Python contracts, **verified to load and run live in OBS 32.1.2**. This
page documents its structure, the three filters, console source, telemetry thread, and lifecycle.
The Python source-of-truth baseline is 1226 tests at 94.53% coverage; native acceptance
is reported separately through the live OBS gates below.

Source: [`plugin/fractisynth/src/fractisynth.c`](../plugin/fractisynth/src/fractisynth.c)
(≈2100 lines). Effects: `data/fractisynth.effect` and
`data/fractisynth_console.effect`. Build: `CMakeLists.txt` + `build.sh`.

## What it registers

`obs_module_load()` registers three filters **and a generated input source**, then starts
the telemetry thread. When built against a matching Qt (see below) `obs_module_post_load()`
also adds a frontend dock.

| id | Type | Role |
| --- | --- | --- |
| `fractisynth_video` | `OBS_SOURCE_TYPE_FILTER` (video) | φ-scaled spatial calibration + SWO-driven shader displacement |
| `fractisynth_audio` | `OBS_SOURCE_TYPE_FILTER` (audio) | φ-knee soft limiter (the same curve as `dsp.phi_soft_limit_sample`) |
| `fractisynth_inspector` | `OBS_SOURCE_TYPE_FILTER` (video) | the **Zoom Inspector** loupe — magnifies a sub-region with φ-grid + crosshair (see below) |
| `fractisynth_console` | `OBS_SOURCE_TYPE_INPUT` (video, custom-draw) | the addable, draggable **φ Wavefield Console** — procedurally renders the live gateway state |
| `fractisynth_dock` | frontend dock (optional Qt build) | a live gateway-gauge pane in the OBS window chrome |

The **console source** (`fcv_*` callbacks) draws a full-screen quad through its own
procedural shader `fractisynth_console.effect` (no input image — `gs_draw_sprite(NULL,
…)`), feeding it the live `swo_phase` / `lock_strength` / `wind_phase` / `egs_key`
uniforms plus `audio_rms` / `audio_peak` / `audio_reactivity` via mutex-guarded
snapshots. It is what makes SynthOBS
appear in the Sources "+" menu. Its interaction handler mirrors
`synthobs.interaction.resolve_target_action`: the top strip has seven feed cells, the
left rail toggles layer visibility bits, and the remaining canvas drops a transient
marker that fades without altering telemetry state. The **dock** is a moc-free,
QPainter Qt `QWidget`
([build-and-install.md](build-and-install.md#the-optional-frontend-dock)) reading the same
state through the C accessor `fractisynth_get_state()`. It now also reads the active
console theme through `fractisynth_get_console_theme()`, cycles Ring / Bar / Needle
gauge styles, and cycles 0 / 1 / 2 decimal precision without mutating telemetry state.

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

The same loop measures the **post-limiter** envelope:

- `audio_rms` — root mean square of the limited samples;
- `audio_peak` — peak magnitude after limiting, never above the ceiling;
- `audio_reactivity` — φ-scaled RMS/threshold clamped to `[0, 1]`.

The values are stored under `g_audio_mutex`, exported through `fractisynth_get_state()`,
drawn on the Telemetry HUD as `AUDIO RMS` / `AUDIO REACT`, shown in the Qt dock, and
bound into `fractisynth_console.effect` so the procedural feeds visibly pulse with
stream audio. The console's bottom audio meter is drawn as a **dark opaque track + a
bright φ-ring fill** whose width tracks `max(reactivity, rms)` (high contrast, readable
over any animated feed). Empty or malformed audio buffers store a zeroed, inactive
envelope; in addition each store stamps `updated_ns` and reads older than
`AUDIO_ENVELOPE_HOLD_NS` (200 ms) are treated as silence — so when a source stops
feeding the filter (OBS never delivers a final silence buffer) the meter **releases to
zero** instead of sticking lit.

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
  `if (!isfinite(current_flux) || current_flux <= 0.0f || active_spots <= 0)` → hold.
  Also rejects non-finite vectors.
- `swo_phase_vector()` — locked read of the vector alone.
- `swo_read(&v)` — locked read of the vector **and** `is_calibrated` together, so the
  render path can enforce the fail-closed rule atomically.

## The telemetry thread (hardened)

A background libcurl thread polls the NOAA SWPC flux, active-region, solar-wind plasma,
GOES X-ray, and Kp endpoints every 60 s and locks the oscillator plus the Solar Graph
series store. Release builds require libcurl, so the module cannot silently ship with
live telemetry disabled. See [telemetry.md](telemetry.md) for the feeds and the
fail-closed contract.

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

![Rendered FractiSynth load, runtime, and unload lifecycle. The five states show source registration, curl/mutex initialization, concurrent video/audio/inspector rendering plus telemetry operation, bounded stop/join, and cleanup. The annotation distinguishes four registered OBS source surfaces—three filters plus the console source—from the optional Qt dock, so the figure does not count a frontend dock as an OBS source registration.](../output/figures/plugin_lifecycle.png){#fig:docs-plugin-lifecycle width=92%}

## Console feeds and targets

Inside OBS the console source exposes seven feeds:

| Feed id | Name | Renderer |
| ---: | --- | --- |
| 0 | Wavefield | shader |
| 1 | Hex Tunnel | shader |
| 2 | Interference | shader |
| 3 | Spectral Rings | shader |
| 4 | Spiral Drift | shader |
| 5 | Telemetry HUD | CPU renderer with metadata, waveforms, provenance, and marker overlay |
| 6 | Solar Graph | CPU renderer for wind speed, density, temperature, GOES X-ray flux, and Kp |

The OBS property key `show_tabs` is preserved for saved-scene compatibility, but its
label is now **Show Clickable Targets** because it controls the seven feed cells, the
layer-toggle rail, and marker-drop affordances.

The **Zoom Inspector** filter supports fixed-region and follow-mouse modes. In follow
mode, OBS interaction mouse events drive the inspected normalized region; until a mouse
event arrives, the filter falls back to `region_x` / `region_y`. Its optional annotation
strip renders the current mode, normalized UV, source pixel coordinate, and zoom through
the same deterministic bitmap text path as the Telemetry HUD.

## Relationship to the Python engine

The C plugin is not a second source of truth. The φ literal, the SWO formula
(`φ · flux/spots`), the fail-closed rule, and the soft-limiter curve are the declared
contracts shared with [`src/synthobs`](../src/synthobs), and static/behavioral tests
check those boundaries. When intended behavior is unclear, the Python engine and its
1226-test suite are authoritative; the C plugin supplies the native OBS execution.

The Telemetry HUD provenance strip can be checked from a captured PNG:

```bash
uv run python scripts/verify_provenance_strip.py \
  manuscript/assets/obs/obs_telemetry_hud.png --json --expect-signature 8b1f58c1
```

The verifier uses the same length prefix, blue-channel LSB extraction, checksum, and
record validation as `src/synthobs/provenance.py`. `--hmac-key-env ENVVAR` additionally
requires the opt-in HMAC-SHA-256 payload mode and reads the secret only from the operator
environment. It is tested on real RGB/RGBA PNG
round-trips, and live OBS scene-compositor survival is now an **automated gate**:
`scripts/obs_scenario_probe.py --verify-provenance` drives real OBS over obs-websocket,
captures the Telemetry HUD, and passes only when the LSB signature decodes from the live
capture and matches the canonical 24-byte telemetry digest (verified against OBS 32.1.2,
2026-07-17). The HUD also draws a redundant 32-cell visible signature strip from the same
digest prefix, giving the scenario harness a survivable fallback signal if row-0 LSBs are
destroyed.

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
  recursion (or any bad callback) can crash OBS at *scene load*, milliseconds after
  the module-load line. The current six-gate scenario probe does not claim to count
  platform crash reports or prove process liveness; on macOS, a separate operator
  check can compare `~/Library/Logs/DiagnosticReports/OBS*.ips` before/after and
  observe OBS through scene load. Never treat the load log alone as survival evidence.
- **Window screenshots are unreliable** (z-order, Spaces, screen-recording permission).
  Use **obs-websocket** `GetSourceScreenshot` on the **scene** (the real compositor) to
  get the rendered pixels independent of window state. Note: `GetSourceScreenshot` of a
  `CUSTOM_DRAW` *source directly* returns black — a measurement artifact — so screenshot
  the **scene** that contains it, and validate the method with a known `color_source`.

`scripts/obs_scenario_probe.py` automates the versioned scenario path. Against real OBS
32.1.2 it now passes all six required gates — connection, dashboard fit-to-canvas,
engine-level interaction model,
render content, **audio reactivity** (`--verify-audio`: a controlled silent-vs-tone capture scores
`mean_abs_delta ≈ 49` against a threshold of 8 — the silent meter band is uniform dark
and a 440 Hz tone lights the left ~40%, matching live `AUDIO REACT 0.401`), and
**provenance survival** (`--verify-provenance`, above). The interaction result verifies
the engine resolver's feed/layer/marker geometry; it is not a claim about click transport
through an OBS Interact window. Closing the audio gate required
three fixes found only by driving live OBS: the probe's controlled tone needed an
**absolute** `local_file` (`is_local_file=true`) because OBS resolves relative paths
against its own working directory; the bottom meter needed the dark-track/φ-ring-fill
contrast; and the audio envelope needed the 200 ms staleness release so the silent
baseline is truthful.
