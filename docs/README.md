# SynthOBS / FractiSynth — Documentation

> **v1.618** — a golden-ratio OBS broadcast console and native transducer,
> phase-locked to live solar telemetry. One constant, **φ = 1.6180339887…**,
> governs every layout, every gain stage, and every shader displacement.

SynthOBS is built in three layers around a single irreducible constant. A tested
Python **engine** is the source of truth; a native **libobs C plugin** mirrors it
inside OBS Studio; an **obspython** console script bridges the two. This directory
is the complete, standalone documentation for all three.

## Documentation map

| Page | Read it when you want to… |
| --- | --- |
| [architecture.md](architecture.md) | Understand the three layers and why φ lives in exactly one place per layer |
| [golden-ratio.md](golden-ratio.md) | Follow the φ mathematics — the Goldilocks split, the soft limiter, the scale matrix |
| [egs-gateway.md](egs-gateway.md) | The canonical FractiAI EGS Gateway: the gateway key K_EGS, solar-wind phase lock, lock strength |
| [interference.md](interference.md) | Holographic interference logic (constructive AR14409 / destructive H-phase-flip) and RSI |
| [engine.md](engine.md) | Use the Python engine: full API reference for all `src/synthobs` modules, including interaction targets, dashboard plans, provenance, and live-gate verification |
| [telemetry.md](telemetry.md) | Fail-closed SWO + the live NOAA SWPC flux/sunspot/solar-wind feeds |
| [command-grammar.md](command-grammar.md) | Drive the system from the terminal: `/mode`, `/transducer bind`, `/swo calibrate`, `/dashboard plan/build` |
| [native-plugin.md](native-plugin.md) | Understand the C plugin: the two OBS filters, the telemetry thread, the lifecycle |
| [build-and-install.md](build-and-install.md) | Build, sign, and install the plugin into OBS — with the verified load evidence |
| [usage.md](usage.md) | Actually use FractiSynth inside OBS: add the filters, run the console script |
| [formal-invariants.md](formal-invariants.md) | Build the Lean 4 invariant scaffold for console shape and fail-closed gates |
| [testing.md](testing.md) | Understand the 1161-test, no-mocks, 98.51%-coverage suite and how to run it |

## The 60-second tour

1. **The constant.** `src/synthobs/constants.py` defines `PHI = (1 + √5) / 2` exactly
   once. The C plugin pins the same value as `#define EGS_PHI 1.61803398875f`; a test
   (`ISC-60`) fails if the two ever drift.
2. **Layout.** Any rectangle is cut 61.8 / 38.2 by `golden_split` — integer-exact,
   the two parts always summing back to the whole. Recursive subdivision and a golden
   spiral fall out of the same constant. See [golden-ratio.md](golden-ratio.md).
3. **Telemetry.** A `SolarWavefieldOscillator` derives a phase vector
   `φ · (flux / spots)` from live NOAA space-weather data, and **fails closed** — bad
   or stale data never modulates anything; the last verified vector is held. See
   [telemetry.md](telemetry.md).
4. **Transduction.** That phase vector drives a φ-calibrated video bounding box, a
   φ-knee audio soft limiter, and a post-limiter RMS/peak/reactivity envelope — in
   pure Python for testing, and natively in OBS via the C plugin. See
   [native-plugin.md](native-plugin.md).
5. **Control.** Three operator modes (Observatory / Laboratory / Expedition), a button
   console, seven clickable feed targets, layer toggles, marker drops, and a terminal grammar — all fail-closed. See
   [command-grammar.md](command-grammar.md).

## Status

| Aspect | State |
| --- | --- |
| Python engine | **Source of truth.** 1161 tests, 98.51 % coverage, no mocks. |
| Native C plugin | **Loads live in OBS 32.1.2.** Built, ad-hoc signed, installed; libcurl telemetry thread hits live NOAA SWPC. Seven feed targets, the layer rail, marker drops, X-ray/Kp graphing, graph axes, inspector modes, audio-reactive shader uniforms, and dock controls are statically pinned. See [build-and-install.md](build-and-install.md). |
| obspython console | Imports guarded; drives the real engine via `apply_command`, including deterministic dashboard plan/build dry-runs outside OBS. |
| Lean scaffold | `lean/SynthOBS/Invariants.lean` builds with Lake and rejects `sorry` / custom `axiom` placeholders in the default suite when Lake is available. |
| Manuscript | 8-section brand-voice manuscript, 5 engine-generated figures, 23-page PDF. |

This is a **local-only research project**. It is intentionally not committed to the
public template repository.
