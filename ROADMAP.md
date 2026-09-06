# SynthOBS Roadmap — the Awareness-Streamer Overlay

> Vision (principal, 2026-06-11): turn SynthOBS from "a source + a dock" into a
> **live, trippy, informative overlay layer that can go on anything** — a
> "frame within the frame" for awareness streamers — that can *zoom into the
> stream like a packet sniffer*, swap **alternate synthetic feeds on demand**
> (synthetic streams, not just a filter), and place **clickable on-screen
> targets / menu destinations**.

Status legend: ✅ shipped · 🚧 in progress · 📋 planned

## Phase A — Trippier + more informative visuals  ✅
- ✅ Live EGS Gateway console (grid, lock ring, φ-spiral, fringes, hex, core)
- ✅ Themes (Observatory / Laboratory / Expedition) + element toggles + intensity
- ✅ **Synthetic Feed modes** — multiple generative visualizations selectable on
  the console source (Wavefield / Hex Tunnel / Interference Field / Spectral
  Rings / Spiral Drift), each driven by live telemetry. ("synthetic streams on
  demand" + the trippy factor.)
- ✅ Chromatic shimmer + optional hue-cycle, telemetry-reactive glow/motion.
- ✅ **Telemetry HUD feed** (CPU-rendered): validated metadata rows + live
  waveform sparklines + a steganographic provenance strip (LSB-embedded,
  C↔Python-verifiable) + on-screen signature. Self-documenting on a stream.
- ✅ **Audio-reactive visuals** (live-proven 2026-06-18): the φ soft-limiter exports
  post-limiter RMS, peak, and reactivity to the console shader, Telemetry HUD, and dock.
  The bottom audio meter is now a dark opaque track + bright φ-ring fill (high contrast,
  unconfounded by the animated feed), and the global envelope releases to silence after a
  200 ms hold (`AUDIO_ENVELOPE_HOLD_NS`) so it no longer sticks lit when a source stops.
  `scripts/obs_scenario_probe.py --verify-audio` scores a controlled silent-vs-tone
  capture at `mean_abs_delta ≈ 49` (threshold 8): the silent meter band is uniform dark,
  the 440 Hz tone lights the left ~40% (= live `AUDIO REACT 0.401`); HUD shows
  `AUDIO RMS 0.248 / REACT 0.401`.

## Phase B — A more configurable dock  ✅
- ✅ In-dock clickable display-mode cycle (moc-free mousePressEvent): Full · Compact · Gauge-only.
- ✅ Dock freeze: Hold/Live toggle freezes the displayed snapshot without mutating telemetry state.
- ✅ Further dock polish: Ring / Bar / Needle gauge styles and 0 / 1 / 2 decimal precision cycling.
- ✅ Dock theme follows the active console source theme, defaulting to Observatory.

## Phase C — Overlay inspector: "frame within the frame" / packet-sniffer  ✅
- ✅ A **Zoom Inspector** video filter: magnify a configurable sub-region of the
  source into an inset loupe, with the φ-grid + crosshair + per-region readout —
  zoom into the stream like a packet sniffer inspecting a flow.
- ✅ Fixed-region or follow-mouse modes with pixel/region telemetry annotation.

## Phase D — On-demand synthetic feed layers  ✅(core)
- ✅ The console source IS a synthetic feed; the feed selector (Phase A) makes it
  multi-stream, switchable live (incl. by click — Phase E).
- ✅ Python source-of-truth dashboard helper (`dashboard_plan`) and `/dashboard
  plan|build --name=<scene>` command. Outside OBS it returns a deterministic dry-run;
  inside OBS it creates the planned synthetic feed layers and registers next/previous
  layer hotkeys.

## Phase E — Interactive on-screen targets / menu destinations  ✅(core)
- ✅ Console source is **interactive** (OBS_SOURCE_INTERACTION + mouse_click): a
  clickable 7-cell feed-tab strip painted across the top and registers the native
  OBS interaction handler; transported click evidence remains scoped to
  `SYNTHOBS-OBS-INTERACTION`.
- ✅ Target actions defined in `src/synthobs/interaction.py` and mirrored natively:
  feed switch, layer toggle rail, and transient marker drop.

## Cross-cutting
- Keep the Python engine the tested source of truth; mirror new math there.
- Every new shader: LOCAL float3 palette (OBS doesn't init global static const).
- Every native change: rebuild + crash-gate (`.ips` count + OBS-stays-alive) +
  websocket scene-shot verification (never trust the load log alone).

## Phase F — Realtime solar-data graphs + multi-source dashboard  ✅(core)
- ✅ Parse the FULL NOAA RTSW wind series (real 1-min cadence) → wind speed /
  density / temperature time-series store.
- ✅ **Solar Graph feed** (feed 6) with a metric selector: a big realtime graph of
  the chosen real metric (current value + min/max + sample count). Drop several
  sources set to different metrics → a multi-panel awareness dashboard, each with
  different real verified ongoing data.
- ✅ Telemetry HUD waveforms now plot the real NOAA series (wind/density), not held values.
- ✅ More metrics: GOES X-ray flux (log-transformed) and planetary Kp index.
- ✅ Time-axis labels: -2H for plasma, -6H for X-ray, dynamic minute horizon for Kp, all ending at NOW.

## Phase G — Live-functional verification + fail-closed hardening  ✅ (2026-06-12)
- ✅ **Live compositor verification for the documented scenario path.** Drove a real
  OBS 32.1.2 process over obs-websocket, fitted the `fractisynth_console` source to
  the base canvas, captured the compositor render, Telemetry HUD, and controlled-tone
  audio state, and verified the LSB provenance strip. The versioned six-gate manifest
  records these exact surfaces. The interaction gate is deliberately engine-level;
  it does not claim that an Interact-window click was transported. Per-feed/filter
  screenshots and platform-specific crash-report/liveness checks remain separate
  acceptance work. Probe: `scripts/obs_scenario_probe.py`.
- ✅ **Fail-closed boundary hardening (cross-vendor-audited).** A `<= 0.0` guard
  silently accepts `NaN`/`Inf` (NaN comparisons are always False; `json.loads` accepts
  the `NaN`/`Infinity` literals). Fixed the four boundary leaks the green suite missed:
  telemetry parsers (flux/speed/density), the NaN click-coordinate path
  (`interaction.resolve_target_action`), the obspython `/calibrate` adapter (now honors
  the engine's fail-closed bool instead of formatting a `None` vector), and the C HUD
  provenance block (now gated on `swo_calibrated && gateway_locked` to match Python's
  `flux>0` precondition — prints `PROVENANCE -- ACQUIRING` pre-lock).
- ✅ **Inspector shader hardening:** `lw = 2.0 / max(uv_size.x, 1.0)` (no +Inf flood on
  a 0-width target) and the loupe inset clamped to the frame on wide aspects.
- ✅ **Fail-closed fuzz harness** (`tests/test_fail_closed_fuzz.py`): one extensible
  battery sweeps every external-ingestion boundary with `NaN`/`±Inf`; adding a boundary
  is one `Boundary(...)` entry. The current suite is 1217 passing / 94.44%.

## Phase H — Formal + provenance verification scaffold  ✅
- ✅ Lean invariant scaffold — `lean/SynthOBS/Invariants.lean` builds with Lake and
  proves the console shape, shared common ids, disjoint unique ids, safety controls,
  literal pins, SWO fail-closed acceptance, and provenance readiness predicates.
- ✅ Provenance-verify tool (live-proven 2026-06-18) — `scripts/verify_provenance_strip.py`
  extracts and verifies the LSB-embedded HUD signature from RGB/RGBA PNG captures, with real
  PNG round-trip tests. **Kill-gate closed:** the LSB strip survives live OBS
  compositing/websocket rescale on a real captured Telemetry HUD frame — `--verify-provenance`
  reports `provenance_lsb.status == "pass"` with the signature decoded from the live capture
  matching the canonical 24-byte telemetry digest. The HUD also draws a high-contrast 32-bit
  visible signature strip from the same digest prefix (`PROVENANCE … LSB+VISIBLE`) as a
  survivable fallback.

## Phase I — Live verifier harness + operator proof  ✅ (cross-platform CI deferred)
- ✅ Pure live-verification oracle — `src/synthobs/verification.py` pins manifest gate
  statuses and the shader-aligned audio-meter ROI (`uv.y > 0.955`) so live captures can
  be scored without broad full-frame guesses.
- ✅ Scenario harness — `scripts/obs_scenario_probe.py` connects to obs-websocket v5,
  creates/selects a verification scene, adds a `fractisynth_console` source, captures
  `audio_silent.png`, `audio_tone.png`, `telemetry_hud.png`, and writes
  `manifest.json` with explicit pass/fail/skip gates.
- ✅ Scene fit-to-canvas helper — the obspython dashboard builder now reads OBS base
  canvas dimensions when available and falls back to 1920×1080 only when OBS does not
  expose video settings; pure transform tests cover 720p, 1080p, and ultrawide canvas
  math.
- ✅ Audio-reactivity live proof (closed 2026-06-18) — `obs_scenario_probe.py --verify-audio`
  reports `audio_reactivity.status == "pass"` (`mean_abs_delta ≈ 49`, threshold 8) from a
  controlled silent-vs-tone capture. Required three fixes found by driving real OBS: the probe
  passed a *relative* `local_file` OBS could not resolve (audio never played → now absolute +
  `is_local_file`); the installed plugin was stale (rebuilt — the audio-meter/uniform code was
  missing); and the global envelope stuck lit after a source stopped (added the 200 ms release
  hold so the silent baseline is truthful).
- ✅ Provenance survival proof (closed 2026-06-18) — `obs_scenario_probe.py --verify-provenance`
  reports `provenance_lsb.status == "pass"`; the signature decodes from the live HUD capture and
  matches the canonical telemetry digest. The manifest still records any failure and the
  render-target/visible-strip fallback path remains available.
- 📋 Cross-platform live verification — scoped as `SYNTHOBS-OBS-CI` and
  `SYNTHOBS-LIVE-MATRIX` in [`TODO.md`](TODO.md); the scenario harness is OS-agnostic,
  but no cross-platform CI claim is made yet.

## Phase J — Parser parity, authenticity, and clean packaging ✅ (2026-07-17)
- ✅ Standalone dependency-free C RTSW parser header with executable parity tests against
  the Python parser over current, shuffled, inactive, stale, future, and malformed rows.
- ✅ Opt-in HMAC-SHA-256 provenance payload/verifier mode with negative controls for missing,
  empty, wrong, and recomputed keys; secrets never enter payloads, manifests, or source.
- ✅ Reproducible wheel smoke gate and workflow: build, install with no index/dependencies,
  import in isolated mode, run the measured suite, and regenerate figures.
