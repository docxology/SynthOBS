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
- 🚧 **Audio-reactive visuals**: the φ soft-limiter now exports post-limiter RMS,
  peak, and reactivity to the console shader, Telemetry HUD, and dock. Procedural
  feeds brighten/pulse from the live envelope and show a bottom audio meter; the
  remaining kill-gate is a live OBS screenshot/video capture with an audible source.

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
  clickable 7-cell feed-tab strip painted across the top switches the synthetic
  feed on click (via OBS's Interact window / interactive projector).
- ✅ Target actions defined in `src/synthobs/interaction.py` and mirrored natively:
  feed switch, layer toggle rail, and transient marker drop.

## Cross-cutting
- Keep the Python engine the tested source of truth; mirror new math there.
- Every new shader: LOCAL float3 palette (OBS doesn't init global static const).
- Every native change: rebuild + crash-gate (`.ips` count + OBS-stays-alive) +
  websocket scene-shot verification (never trust the load log alone).

## Phase F — Realtime solar-data graphs + multi-source dashboard  ✅(core)
- ✅ Parse the FULL NOAA plasma-2-hour series (real 1-min cadence) → wind speed /
  density / temperature time-series store.
- ✅ **Solar Graph feed** (feed 6) with a metric selector: a big realtime graph of
  the chosen real metric (current value + min/max + sample count). Drop several
  sources set to different metrics → a multi-panel awareness dashboard, each with
  different real verified ongoing data.
- ✅ Telemetry HUD waveforms now plot the real NOAA series (wind/density), not held values.
- ✅ More metrics: GOES X-ray flux (log-transformed) and planetary Kp index.
- ✅ Time-axis labels: -2H for plasma, -6H for X-ray, dynamic minute horizon for Kp, all ending at NOW.

## Phase G — Live-functional verification + fail-closed hardening  ✅ (2026-06-12)
- ✅ **Live in-scene verification (closes the long-standing SYNTHOBS-VISUAL-1 residual).**
  Drove a real OBS 32.1.2 process over obs-websocket and screenshotted every feed
  rendering with live NOAA data: Wavefield / Hex Tunnel / Interference / Spectral /
  Spiral, the Telemetry HUD (FLUX/WIND/LOCK/GATE/PROVENANCE), the Solar Graph (live
  Kp), and the `fractisynth_video` + `fractisynth_inspector` (loupe) filters on a real
  color source. Probe: `scripts/obs_ws_probe.py`. Gate: `.ips` crash-count + OBS-alive,
  not the load log alone.
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
  is one `Boundary(...)` entry. The current suite is 1132 passing / 96.95%.

## Phase H — Formal + provenance verification scaffold  🚧
- ✅ Lean invariant scaffold — `lean/SynthOBS/Invariants.lean` builds with Lake and
  proves the console shape, shared common ids, disjoint unique ids, safety controls,
  literal pins, SWO fail-closed acceptance, and provenance readiness predicates.
- 🚧 Provenance-verify tool — `scripts/verify_provenance_strip.py` extracts and
  verifies the LSB-embedded HUD signature from RGB/RGBA PNG captures, with real PNG
  round-trip tests. *Remaining kill-gate:* confirm the strip survives live OBS
  compositing/websocket rescale on a real captured Telemetry HUD frame. The HUD now
  also draws a high-contrast 32-bit visible signature strip from the same digest prefix;
  if row-0 LSBs do not survive, use render-target readback where available or the
  visible strip as the survivable capture fallback.

## Phase I — Live verifier harness + operator proof  🚧
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
- 🚧 Audio-reactivity live proof — run:
  `uv run python scripts/obs_scenario_probe.py --out output/live/<timestamp> --verify-audio`.
  The gate closes only when `manifest.json` reports `audio_reactivity.status == "pass"`
  from a controlled silent-vs-tone capture.
- 🚧 Provenance survival proof — run:
  `uv run python scripts/obs_scenario_probe.py --out output/live/<timestamp> --verify-provenance`.
  The gate closes only when `provenance_lsb.status == "pass"`; a failure must remain
  visible in the manifest and trigger the render-target/visible-strip fallback path.
- 📋 Cross-platform live verification — the scenario harness is OS-agnostic; wire it
  into Linux/Windows OBS CI smoke once a headless OBS target exists.
