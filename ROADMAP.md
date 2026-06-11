# SynthOBS Roadmap — the Awareness-Streamer Overlay

> Vision (principal, 2026-06-11): turn SynthOBS from "a source + a dock" into a
> **live, trippy, informative overlay layer that can go on anything** — a
> "frame within the frame" for awareness streamers — that can *zoom into the
> stream like a packet sniffer*, swap **alternate synthetic feeds on demand**
> (synthetic streams, not just a filter), and place **clickable on-screen
> targets / menu destinations**.

Status legend: ✅ shipped · 🚧 in progress · 📋 planned

## Phase A — Trippier + more informative visuals  ✅(core)
- ✅ Live EGS Gateway console (grid, lock ring, φ-spiral, fringes, hex, core)
- ✅ Themes (Observatory / Laboratory / Expedition) + element toggles + intensity
- ✅ **Synthetic Feed modes** — multiple generative visualizations selectable on
  the console source (Wavefield / Hex Tunnel / Interference Field / Spectral
  Rings / Spiral Drift), each driven by live telemetry. ("synthetic streams on
  demand" + the trippy factor.)
- ✅ Chromatic shimmer + optional hue-cycle, telemetry-reactive glow/motion.
- 📋 In-shader telemetry HUD (numeric flux/wind/lock burned into the overlay so
  the visual is self-documenting on a recorded stream).

## Phase B — A more configurable dock  📋
- 📋 In-dock clickable controls (moc-free mousePressEvent): compact/full mode,
  per-row visibility, gauge style, decimal precision, pause/freeze.
- 📋 Dock theme follows the source theme.

## Phase C — Overlay inspector: "frame within the frame" / packet-sniffer  ✅
- ✅ A **Zoom Inspector** video filter: magnify a configurable sub-region of the
  source into an inset loupe, with the φ-grid + crosshair + per-region readout —
  zoom into the stream like a packet sniffer inspecting a flow.
- 📋 Follow-mouse or fixed-region modes; pixel/region telemetry annotation.

## Phase D — On-demand synthetic feed layers  🚧→📋
- 🚧 The console source IS a synthetic feed; the feed selector (Phase A) makes it
  multi-stream.
- 📋 A scene-collection helper that drops several synthetic feeds as stacked
  layers with hotkeys to cross-fade between them on demand.

## Phase E — Interactive on-screen targets / menu destinations  📋
- 📋 Make the console source **interactive** (obs_source_info mouse_click /
  mouse_move / get_interaction): clickable hotspots / menu targets painted on
  the canvas that the operator can point-and-click to switch feed, toggle a
  layer, or fire an action.
- 📋 Define target actions (feed switch, layer toggle, marker drop).

## Cross-cutting
- Keep the Python engine the tested source of truth; mirror new math there.
- Every new shader: LOCAL float3 palette (OBS doesn't init global static const).
- Every native change: rebuild + crash-gate (`.ips` count + OBS-stays-alive) +
  websocket scene-shot verification (never trust the load log alone).
