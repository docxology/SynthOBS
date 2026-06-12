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
