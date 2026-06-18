# Using FractiSynth in OBS

SynthOBS shows up in OBS Studio four ways, from most to least visible:

| Way it appears | What it is | Where in OBS |
| --- | --- | --- |
| **SynthOBS — φ Wavefield Console** | a generated **source** you add to a scene (draggable, resizable) | **Sources → + → SynthOBS — φ Wavefield Console** |
| **FractiSynth — φ Video / Harmonic** | two **filters** on any existing source | **Filters → +** |
| **SynthOBS Gateway** dock | a live gateway-gauge **dock** pane (optional Qt build) | **Docks → SynthOBS Gateway** |
| obspython console | a **Scripts** panel driving the tested engine | **Tools → Scripts** |

## 0. The φ Wavefield Console source (the addable, draggable pane)

Open **Sources → + → "SynthOBS — φ Wavefield Console"**. It drops a generated source onto
the canvas — drag and resize it like any other source. It procedurally paints the live
transducer state: the Goldilocks 61.8 / 38.2 grid, K_EGS-spaced holographic interference
fringes, a φ spiral, an optional honeycomb hex lattice, a **gateway lock ring** (filling
red → teal as the gateway phase-locks), and a centre core whose size tracks the SWO phase
vector. Until the gateway locks it renders dim/charcoal — fail-closed, like everything else.

### Console configuration (Properties)

Select the source and click **Properties** for a full config panel:

| Control | Effect |
| --- | --- |
| **Synthetic Feed** | which stream to render: *Wavefield Console*, *Hex Tunnel*, *Interference Field*, *Spectral Rings*, *Spiral Drift* (visual, telemetry-driven), *Telemetry HUD* (metadata + waveforms + provenance), *Solar Graph* (realtime NOAA time-series) |
| **Graph Metric** (Solar Graph) | which real metric to graph: *Solar Wind Speed*, *Density*, *Temperature*, *GOES X-ray Flux (log)*, *Planetary K-index (Kp)* — drop several Solar Graph sources set to different metrics for a multi-panel live dashboard |
| **Chromatic Shimmer** | radial RGB split (the trippy fringe), 0–1 |
| **Hue Cycle** | rotate the whole palette over time, 0–1 |
| **Operator Theme** | palette: *Observatory* (robin's-egg/marigold), *Laboratory* (cool blue), *Expedition* (solar marigold/ember) |
| **Overlay Intensity** | master strength of all overlays (0–1) |
| **Animation Speed** | motion rate (0–3); 0 freezes |
| **Interference Fringe Density** | spatial frequency of the holographic fringes (6–48) |
| **Show …** toggles | Gateway Lock Ring · Holographic Fringes · φ Spiral · Goldilocks Grid · Honeycomb Hex Lattice · Phase-Vector Core |
| **Show Clickable Targets** (`show_tabs`) | paint the seven-feed tab strip, layer-toggle rail, and marker-drop target affordances; saved scenes using the older `show_tabs` key keep working |
| **Console Width / Height** | render resolution (default 1280×720) |

When the **FractiSynth — φ Harmonic Limiter** is present on a live audio source, the
console source receives post-limiter `RMS`, `peak`, and `reactivity` values. The
procedural feeds pulse from that envelope, and the bottom edge draws a compact audio
meter — a dark track with a bright φ-ring fill whose width tracks the level. When the
audio source stops, the meter **releases to silence** after a 200 ms hold rather than
freezing at the last level. The Telemetry HUD / dock expose the same numbers
(`AUDIO RMS` / `AUDIO REACT`) for operator verification.

### Switching feeds, layers, and markers by clicking (interactive)

With **Show Clickable Targets** on, the console source is interactive: **right-click the
source → Interact** (or open an interactive projector), then click the canvas targets.
The top strip is split into seven feed cells — Wavefield, Hex, Interference, Spectral,
Spiral, Telemetry HUD, Solar Graph. The left rail below the strip toggles planned layer
visibility. The remaining canvas drops a transient marker at the clicked normalized
position; it fades visually and does not mutate telemetry state. OBS only delivers
clicks to a source through its Interact window/projector, not the plain preview.

### The Zoom Inspector filter — "frame within the frame"

Add **Filters → + → "FractiSynth — Zoom Inspector (loupe)"** to *any* source to magnify a
sub-region into an inset loupe — zoom into the stream like a packet sniffer. Properties:
**Inspector Target Mode** (*Fixed Region* or *Follow Mouse*), **Zoom** (1.5–16×),
**Inspect Region X/Y**, **Loupe Size**, **Loupe Corner**, and toggles for the
source-region box, the loupe's golden grid, its crosshair, and a pixel/region
annotation strip. Follow Mouse uses OBS interaction events when available and falls
back to the fixed region until a mouse position has been received. The loupe border
brightens with the live gateway lock.

## The SynthOBS Gateway dock (a live telemetry panel)

Enable it from **Docks → SynthOBS Gateway** (OBS docks start hidden; enable it once and OBS
remembers). It is a live panel in the OBS window chrome showing the **gateway lock-ring
gauge** plus a numeric readout: SWO phase vector, F10.7 flux, active sunspots, solar wind,
lock strength, phase bias θ, the **holographic interference verdict** (CONSTRUCTIVE /
DESTRUCTIVE / MIXED), and the gateway key K_EGS — all updating ~8×/s, fail-closed (shows
"— hold" until live telemetry locks). Its bottom controls have real buttons for
*Full*, *Compact*, *Gauge*, *Hold/Live*, gauge style (*Ring*, *Bar*, *Needle*), and
decimal precision (`0 dp`, `1 dp`, `2 dp`). Hold freezes the displayed snapshot while
the underlying telemetry thread continues to fail closed independently. The dock palette
follows the active console source theme and defaults to Observatory before any source
has reported a theme.

The dock is a native Qt6 panel and must be built against the **same Qt minor version OBS
runs** (6.8.x). `build.sh` auto-uses a bundled obs-deps Qt 6.8 (dropped into
`.obs-sdk/qt-6.8`) when present, and version-gates the build so a mismatched Qt is skipped
rather than breaking the plugin. See
[build-and-install.md](build-and-install.md#the-optional-frontend-dock).

## 1. The native filters

After building and installing the plugin ([build-and-install.md](build-and-install.md))
and restarting OBS:

1. Select a source (camera, capture, media) in a scene.
2. **Filters → +** and add either:
   - **FractiSynth — φ Video Calibration** — establishes the φ-scaled harmonic bounding
     box and renders the live EGS Gateway state onto the source. Seven knobs:
     **Displacement Gain** (0–4), **φ-Spiral Density** (4–32 arms), **Holographic
     Interference** (0–1, EGS fringes), **Hydrogen H-α Resonance Tint** (0–1),
     **Honeycomb Hex Lattice** (0–1), and **HOLO_GRID Overlay** (0–1). All gateway-driven
     layers fade with the live lock strength, so an offline stream stays clean.
   - **FractiSynth — φ Harmonic Limiter** — a φ-knee soft limiter on the source audio.
     Knob: **Soft Limiter Ceiling** (0.05–1.0). It never hard-clips, and its
     post-limiter envelope drives the console's audio-reactive shader uniforms.

The filters read the shared oscillator automatically. Until the telemetry thread locks a
real reading, the video filter contributes **zero** displacement (fail-closed) — so an
unconfigured or offline install renders a clean pass-through, never garbage.

## 2. The obspython console script

[`plugin/synthobs/synthobs_console.py`](../plugin/synthobs/synthobs_console.py) is a
standard OBS Python script that drives the **real tested engine**. Load it via
**Tools → Scripts → +** and select the file. (OBS must have Python configured under
**Tools → Scripts → Python Settings**.)

The script exposes a single command field that runs the [command grammar](command-grammar.md)
through `apply_command(line)`:

```
/mode --observatory
/mode --lab
/mode --ship
/transducer bind source_cam_01 --ratio=1.618034
/swo calibrate --flux=130 --spots=3 --target=AR4465
/dashboard plan --name=Awareness
/dashboard build --name=Awareness
```

Each line is parsed, run through the engine, and echoed back as a status string — or as
an `ERROR …` string on a bad command (never a crash):

```python
apply_command("/mode --observatory")
# → "mode → observatory"
apply_command("/swo calibrate --flux=130 --spots=3")
# → "... phase_vector=..."
apply_command("/warp --core")
# → "ERROR: unknown command verb: '/warp' ..."
```

`/dashboard plan --name=Awareness` returns a deterministic seven-layer plan: a full
Wavefield background, a Telemetry HUD, and Solar Graph layers for wind speed, density,
temperature, X-ray flux, and Kp. `/dashboard build --name=Awareness` returns the same
dry-run summary outside OBS; inside OBS it creates the `fractisynth_console` sources,
sets feed/metric values, positions them from normalized bounds, and registers
next/previous layer hotkeys.

### Why it's safe to run outside OBS too

The script guards `import obspython` (the module only exists inside OBS), so it stays
importable — and unit-testable — on a normal Python interpreter. Its `_IN_OBS` flag is
`False` outside OBS, the engine-driving functions (`apply_command`,
`viewport_for_canvas`) work anywhere, and the OBS-only callbacks (`script_load`,
`script_properties`, scene sync) are no-ops without OBS. This is why the bridge can be
covered by the test suite with no mocks.

## The three operator modes

Both surfaces share three modes, each with 7 console buttons (3 common + 4 unique) and a
dedicated **EMERGENCY_ABORT** safety button:

| Mode | Flag | Register |
| --- | --- | --- |
| Observatory | `--observatory` | wide-field monitoring |
| Laboratory | `--lab` / `--laboratory` | close analysis |
| Expedition | `--ship` / `--expedition` | field / broadcast |

See [engine.md](engine.md#console--operator-modes-and-the-button-grid) for the button
console API and [command-grammar.md](command-grammar.md) for the full grammar.

## Typical session

1. Install the plugin and restart OBS ([build-and-install.md](build-and-install.md)).
2. Add the **φ Video Calibration** filter to your main camera and the **φ Harmonic
   Limiter** to your mic.
3. (Optional) Load the console script and `/mode --ship` for a broadcast layout.
4. Leave it running — the telemetry thread re-locks the oscillator from live NOAA SWPC
   every 60 seconds, and the filters track it. On any telemetry dropout the system holds
   the last verified vector rather than lurching.
