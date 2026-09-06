# Evaluation, Evidence, and Reproducibility {#sec:evaluation}

This chapter turns the SynthOBS blueprint into an inspectable research artifact.
The contribution is a bounded engineering system with four linked surfaces: a
dependency-free Python reference engine, a native OBS transducer, an obspython
operator bridge, and a live evidence protocol. The claim is not that a geometric
constant explains broadcasting in general. The design proposition is narrower and
testable: a single pinned constant, explicit fail-closed state transitions, and
versioned captures make a cross-language OBS instrument easier to reason about and
re-run.

That distinction follows the reproducibility literature's separation of rerunning a
computation from reproducing an empirical environment [@nasem2019]. It also follows
software-practice guidance to record dependencies, automate the path from source to
artifact, and preserve the data and procedures needed for inspection
[@wilson2014; @sandve2013; @wilkinson2016fair]. The provenance vocabulary is
contextualized with W3C PROV-O [@prov2013], while the figure generator follows the
scientific-visualization software lineage documented for Matplotlib
[@hunter2007matplotlib].

### Public distribution and affiliation

SynthOBS is authored under **FractiAI / Active Inference Institute**. The planned
public v1 distribution is the GitHub repository
[`docxology/SynthOBS`](https://github.com/docxology/SynthOBS), which is intended to
carry the complete source, native OBS module, obspython bridge, tests, installation
and usage documentation, manuscript sources, citation metadata, and versioned live
evidence. The repository-level release contract in [`RELEASE.md`](../RELEASE.md)
defines the clean-clone preflight and the remaining public-release gates.

## Contributions and system boundaries

The artifact makes five concrete contributions:

1. `src/synthobs/` defines the geometry, telemetry gates, DSP, console shape, and
   command grammar without OBS or third-party runtime imports.
2. `plugin/fractisynth/` implements the engine's declared contracts at the `libobs`
   video/audio boundary, with libcurl-backed live telemetry and bounded shutdown.
3. `plugin/synthobs/` exposes the same state transitions through an obspython
   console, including the four typed verbs `/mode`, `/transducer`, `/swo`, and
   `/dashboard`.
4. `scripts/generate_figures.py` derives deterministic visualizations from the
   tested engine and records each figure's source in
   [`output/figures/figure_manifest.json`](../output/figures/figure_manifest.json).
5. The live OBS bundle in [`assets/obs/`](assets/obs/) preserves real compositor,
   telemetry-HUD, and audio-reactivity captures with hashes and six gate results.

The boundary is intentional. Python tests establish mathematical and parser
behavior; static C probes establish native contract structure; a real OBS session establishes
that the installed binary loads, renders, reacts to controlled audio, and preserves
telemetry provenance. None of these evidence classes silently substitutes for the
others.

## Scholarship and evidence discipline

Scholarship is used here as an audit layer, not as decoration and not as a
substitute for a failing test. The manuscript follows a four-part claim protocol:
an external source establishes context when a claim depends on an interface,
standard, data product, or established method; a repository source of truth states
how SynthOBS implements the claim; an executable test or contract supplies a way to
falsify it; and a rendered artifact or live capture is added only when the claim
crosses the OBS boundary. This is the practical separation between reproducibility
and replicability described by the National Academies [@nasem2019], made concrete
through software-practice guidance [@wilson2014; @sandve2013] and FAIR stewardship
[@wilkinson2016fair].

The source ledger in [`docs/scholarship_sources.json`](../docs/scholarship_sources.json)
records that protocol for the material claims in this blueprint. Its source order
is deliberately conservative: primary OBS and NOAA documentation grounds interface
and data-product statements [@obsmodules; @obswebsocket; @noaaswpc; @noaaf107;
@noaasunspot; @noaartsw], standards ground provenance vocabulary [@prov2013], and
peer-reviewed or established technical sources provide method context for
visualization, DSP, architecture, and the history of the golden ratio
[@hunter2007matplotlib; @smith2007; @gamma1994; @livio2002golden]. Those citations
do not prove that this implementation works. The local engine, tests, manifests,
hashes, and captures do that within the declared boundary.

## A formal claim-to-evidence calculus

To keep the evidence language composable, let each material claim $c$ carry a
four-tuple

$$
E(c) = \bigl(S(c), R(c), T(c), A(c)\bigr),
$$ {#eq:evidence-tuple}

where $S(c)$ is the external source or standard, $R(c)$ is the repository source of
truth, $T(c)$ is the executable test or contract that can falsify the implementation,
and $A(c)$ is a rendered or live artifact when the claim crosses the OBS boundary.
For a purely internal deterministic claim, $A(c)$ may be empty. For a runtime claim,
the admissibility condition is

$$
\operatorname{admissible}(c) = S(c) \land R(c) \land T(c) \land A(c).
$$ {#eq:evidence-admissibility}

The conjunction is a documentation rule, not a claim that four independent sources
make a result true. It prevents evidence substitution: $S(c)$ can explain an API,
but cannot prove this binary loaded; $T(c)$ can exercise a parser, but cannot prove
that a live OBS frame contains the parser's state; and $A(c)$ can show a frame, but
cannot establish the rejection of malformed input. The machine-readable ledger
encodes the tuple in `sources`, `source_of_truth`, `tests`, and `artifacts`, making
the argument inspectable by both humans and automation.

This calculus also clarifies the relationship between scholarship and software
citation. The external literature establishes why versioned, attributable, accessible
software records matter [@smith2016softwarecitation]; the CFF metadata records the
current software identity [@cffschema]; the repository and manifest record what this
version actually did. The bibliography therefore supports the method of accounting,
while the local evidence remains responsible for the implementation claim.

| Claim class | External scholarship contributes | Repository evidence must contribute |
| --- | --- | --- |
| Interface contract | Meaning of the OBS module and websocket surfaces | Native artifact probes, live connection, and the manifest's gate record |
| External data provenance | Identity and semantics of the NOAA products and `libcurl` transport | Fail-closed parsers, freshness checks, and the recovered HUD record |
| Design proposition | Method context for φ geometry, DSP, architecture, and visualization | Equations, source modules, regression tests, and generated figure manifest |
| Run observation | Reproducibility and provenance vocabulary | Exact bytes, versions, timestamps, hashes, and six gate outcomes |

This division also prevents a common category error: a visually persuasive frame is
not evidence that malformed telemetry is rejected, and a citation to a standard is
not evidence that the native plugin loaded into the recorded OBS build.

## Materials and versions

| Material | Version or value | Role |
| --- | --- | --- |
| Python engine | package `1.618.0`, `src/synthobs/` | reference implementation |
| Author affiliation | FractiAI / Active Inference Institute | publication metadata and software provenance |
| Test collection | 1226 tests, 94.53% coverage | unit, parser, integration, static artifact, scholarship, public-release, and verification contracts |
| OBS Studio | 32.1.2 | live host and compositor |
| obs-websocket | 5.7.3 | scene/source control and screenshot capture; the protocol surface is documented by the OBS project [@obswebsocket] |
| OBS base canvas | 3200 × 2000 | source composition canvas |
| manuscript captures | 1280 × 720 | downsampled scene, HUD, and tone evidence |
| NOAA products | F10.7, active solar-region report, RTSW wind/plasma | live external inputs [@noaaf107; @noaasunspot; @noaartsw; @noaaswpc] |
| Native transfer | libcurl | bounded HTTP client [@libcurl] |

The evidence bundle was captured in run `20260717T153649Z` after rebuilding and
installing the native FractiSynth bundle against OBS 32.1.2. Its manifest is the
machine-readable record of the run: [`obs_manifest.json`](assets/obs/obs_manifest.json).
The exact PNG bytes, silent baseline, and controlled WAV are checked into the manuscript
asset directory, so the audio delta can be independently recomputed and the cover and
generated figure directory are derived from the same real OBS run.

## Live OBS protocol

The acceptance path uses a real OBS process and a real obs-websocket connection. The
probe creates or selects an isolated verification scene, fits the console source to
the base canvas, exercises the interaction model, captures compositor pixels, and
compares silent and controlled-tone audio states. The telemetry HUD is then inspected
for its embedded provenance record. This follows the documented OBS module boundary
rather than treating a standalone screenshot or a source-local render as proof
[@obsmodules; @obswebsocket].

### Gate results

All six required gates passed in the versioned run `20260717T153649Z`.

| Gate | Result | Exact evidence |
| --- | --- | --- |
| `connection` | pass | OBS identified; websocket `5.7.3`; OBS `32.1.2` |
| `dashboard_fit_to_canvas` | pass | `positionX=0.0`, `positionY=0.0`, `scaleX=2.5`, `scaleY=2.7777777777777777` |
| `interaction_model` | pass | engine resolver covers feed tabs, layer rail, and marker drop; OBS click transport is not claimed |
| `render_content` | pass | 1280 × 720; `non_black_fraction=1.0`; `dynamic_range=161.9278106689453`; `mean_channel_std=19.49281120300293` |
| `audio_reactivity` | pass | ROI `y=687`, height `33`; `mean_abs_delta=48.557402146464646`; `max_abs_delta=180`; threshold `8.0`; 42,240 pixels compared |
| `provenance_lsb` | pass | flux `140.0`; sunspots `6`; wind `367.8999938964844 km/s`; lock `0.5124873518943787`; phase bias `2.108875274658203 rad`; signature `8b1f58c1` |

### Formal acceptance definitions

The live gates are numerical predicates over captured bytes, not visual judgments.
For a capture of width $w$ and height $h$, let $I_0$ and $I_1$ denote the
silent and controlled-tone RGBA images, and define the shader-pinned bottom region

$$
R = \{(x,y) : 0 \le x < w,\; \lfloor 0.955h \rfloor \le y < h\}.
$$ {#eq:audio-meter-roi}

The audio oracle ignores alpha and computes the mean absolute RGB change

$$
D_R = \frac{1}{3\lvert R\rvert}
\sum_{(x,y)\in R}\sum_{c\in\{r,g,b\}}
\left\lvert I_1(x,y,c)-I_0(x,y,c)\right\rvert,
\qquad
M_R = \max_{(x,y)\in R,\,c\in\{r,g,b\}}
\left\lvert I_1(x,y,c)-I_0(x,y,c)\right\rvert.
$$ {#eq:audio-meter-delta}

The audio gate passes exactly when $D_R \ge 8.0$; $M_R$, the ROI dimensions,
and the input channel count remain diagnostic metrics. For the current 1280 × 720
capture, @eq:audio-meter-roi gives $R=(0,687,1280,33)$, so
$\lvert R\rvert=42{,}240$ pixels.

The render-content gate uses luminance

$$
Y = 0.2126R + 0.7152G + 0.0722B,
\qquad
q = \operatorname{mean}(Y>8),
\qquad
\Delta_Y = \max(Y)-\min(Y),
$$ {#eq:render-content-metrics}

and the mean of the per-channel spatial standard deviations $s$. It passes iff
$q\ge0.08$, $\Delta_Y\ge24$, and $s\ge3$. Thus the evidence establishes
non-degenerate compositor content without pretending that a single frame is a
performance distribution.

The provenance gate is byte-exact. Let $b$ be the 24-byte little-endian
`TelemetryRecord` containing flux, active-region count, wind speed, lock strength,
phase bias, and observation time. The default payload is

$$
p = b\;\Vert\;\operatorname{SHA256}(b)[0:4],
$$ {#eq:provenance-payload}

embedded in the blue-channel least-significant bits. Verification extracts $p$,
recomputes the four-byte digest prefix, and validates the decoded fields before
reporting the visible eight-hex-character prefix. Equation @eq:provenance-payload
detects accidental corruption or resampling; it is intentionally not a keyed
authenticity claim. The optional HMAC mode is a separate operator-controlled path
and is not used to inflate the current six-gate result.

Three machine-verifiable visual captures are shown in the implementation chapter:
the scene render (Figure @fig:obs-live-scene), telemetry HUD
(Figure @fig:obs-live-telemetry), and controlled audio tone
(Figure @fig:obs-live-audio). The silent baseline and controlled WAV are versioned
companion inputs rather than decorative figures. The scene render is also the cover
image. The user-supplied OBS window capture (Figure @fig:obs-operator-window) is a
separate operator-context artifact: it communicates host UI placement and
observability, but its visible numbers are not substituted for the manifest metrics
and it is not one of the six machine gates. The asset hashes and media metadata in
`obs_manifest.json` provide an additional byte-level check against accidental
replacement.

## Claim-to-evidence map

| Design claim | Source of truth | Automated test or contract | Live or rendered evidence |
| --- | --- | --- | --- |
| One φ across layers | `src/synthobs/constants.py`, `fractisynth.c` | Python/C literal parity and gateway-key tests | `parity_bridge.png`; native build |
| Exact golden tiling | `layout.py` | `tiles_exactly()` sweep and layout tests | `goldilocks_layout.png`, `golden_split.png` |
| φ-scaled DSP | `dsp.py` | limiter bounds, monotonicity, matrix, and envelope tests | `phi_soft_limiter.png`, `phi_matrix.png`; audio gate |
| Four-verb fail-closed grammar | `commands.py` | parser acceptance/rejection tests and docs contract | `command_parse_pipeline.png` |
| Telemetry never mints a default | `telemetry.py`, `swo.py` | malformed, stale, non-finite, and hold-state tests | `telemetry_pipeline.png`; provenance gate |
| Native lifecycle is bounded | `fractisynth.c` | static artifact probes and source-level lifecycle checks | `plugin_lifecycle.png`; no separate unload gate in the six-gate manifest |
| OBS compositor contains content | `obs_scenario_probe.py` | render-content gate, independent of source-local output | `obs_scene_render.png` |
| Audio state reaches the visual meter | `obs_scenario_probe.py` | silent-vs-tone ROI oracle | `obs_audio_tone.png` plus audio gate |

This map is deliberately heterogeneous. A passing unit test cannot certify an OBS
window loaded a binary, and a compelling screenshot cannot certify malformed telemetry
is rejected. The evidence classes converge at the system boundary but remain
independently named.

## Reproduction commands and artifact paths

From the project root, the deterministic engine and figure paths are:

```bash
./.venv/bin/python -m pytest tests --cov=synthobs \
  --cov-report=term-missing --cov-fail-under=90
./.venv/bin/python scripts/generate_figures.py
```

The first command must collect 1226 tests and report 94.53% coverage (and at least 90%). The
second command must read the versioned real OBS bundle, verify its hashes and six
passing gates, generate the analytical figures, copy the three live captures, and
write `output/figures/figure_manifest.json`. The operator-context screenshot is
intentionally excluded from that generated manifest because it is supplied context,
not an analytical figure or a promoted live-gate asset.

The live path requires an installed OBS process and a configured obs-websocket
credential; it is intentionally exercised only through the real OBS connection:

```bash
./.venv/bin/python scripts/obs_scenario_probe.py \
  --out output/live/$(date -u +%Y%m%dT%H%M%SZ) \
  --verify-audio --verify-provenance --require-live
```

The native build and standalone CMake path are documented in
[`docs/build-and-install.md`](../docs/build-and-install.md). The manuscript renderer
consumes `manuscript/config.yaml`; its cover points to
`assets/obs/obs_scene_render.png`, while figure references resolve to the generated
`output/figures/` directory.

## Validation boundaries and future engineering work

The current evidence establishes one real OBS run, not a statistical performance
distribution. It does not claim that every OBS release, operating system, audio
driver, or NOAA response shape will behave identically. The scoped follow-up work is
maintained in [`TODO.md`](../TODO.md), including cross-platform/headless acceptance,
transported interaction clicks, and per-feed/filter visual captures. Native C↔Python
parser parity, keyed provenance, and clean-environment wheel reproducibility are now
closed with executable evidence recorded in the roadmap.

These are engineering extensions, not retroactive qualifications of the current
run. The present artifact is reproducible to the extent stated above: deterministic
math and documentation can be rerun locally; the live evidence can be inspected byte
for byte; and re-establishing the external OBS/NOAA environment is identified as a
separate acceptance activity.
