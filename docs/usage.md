# Using FractiSynth in OBS

SynthOBS shows up in OBS Studio four ways, from most to least visible:

| Way it appears | What it is | Where in OBS |
| --- | --- | --- |
| **SynthOBS — φ Wavefield Console** | a generated **source** you add to a scene (draggable, resizable) | **Sources → + → SynthOBS — φ Wavefield Console** |
| **FractiSynth — φ Video / Harmonic** | two **filters** on any existing source | **Filters → +** |
| **SynthOBS Gateway** dock | a live gateway-gauge **dock** pane (optional Qt build) | **Docks → SynthOBS Gateway** |
| obspython console | a **Scripts** panel driving the tested engine | **Tools → Scripts** |

## 0. The φ Wavefield Console source (the addable, draggable pane)

After installing the plugin and restarting OBS, open **Sources → + → "SynthOBS — φ
Wavefield Console"**. It drops a generated source onto the canvas — drag and resize it
like any other source. It procedurally paints the live transducer state: the Goldilocks
61.8 / 38.2 golden-ratio guides, K_EGS-spaced holographic interference fringes, a φ
spiral, a **gateway lock ring** (red → teal as the gateway phase-locks), the hydrogen
H-α resonance, and a centre dot whose size tracks the SWO phase vector. Size is
configurable (default 1280×720). Until the gateway locks it renders dim/charcoal —
fail-closed, like everything else.

## The SynthOBS Gateway dock (optional, Qt-matched build)

The plugin also ships a native frontend **dock** — a compact live gateway gauge that
sits in the OBS window chrome (under **Docks**), painting the lock ring, φ-spiral, and
solar-wind bar. It is **opt-in at build time**: because a dock must be compiled against
the *same* Qt minor version OBS runs (6.8.x), `build.sh` builds it **only** when
`QT_PREFIX` points at a matching Qt — otherwise it auto-skips so the rest of the plugin
always loads. See [build-and-install.md](build-and-install.md#the-optional-frontend-dock).

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
     Knob: **Soft Limiter Ceiling** (0.05–1.0). It never hard-clips.

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
