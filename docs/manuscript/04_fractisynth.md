# FractiSynth Engine Specification (The Processing Core) {#sec:fractisynth}

FractiSynth is compiled as a native, low-latency plugin module that hooks into the
core processing pipelines of `libobs`, using the host's documented module/plugin
surface [@obsmodules]. It exposes three filters — a video calibrator, an audio
harmonic limiter, and a Zoom Inspector — plus the interactive console source; all
consume the pinned constants and the accepted Solar Wavefield Oscillator vector at
the OBS boundary.

## Native Video Manipulation Pipeline

The plugin intercepts the video rendering loop at the texture level. Before frames
are handed off to the hardware encoder, FractiSynth forces spatial transformations
to scale directly against the EGS fractal constant $\varphi$, establishing the
*calibrated harmonic bounding box*:

$$
w_{\text{cal}} = \operatorname{round}\!\left( \frac{w_{\text{source}}}{\varphi} \right),
\qquad
h_{\text{cal}} = \operatorname{round}\!\left( \frac{h_{\text{source}}}{\varphi} \right),
\qquad w_{\text{cal}}, h_{\text{cal}} \ge 1 .
$$ {#eq:fractisynth-calibrated-box}

Equation @eq:fractisynth-calibrated-box scales each axis to $1/\varphi \approx 0.618$
of its source extent — the 61.8% golden fraction — clamped so a non-degenerate source
never collapses to zero extent. The live SWO `system_phase_vector` then modulates the
shader displacement amount, so the overlay breathes with current space weather. The
native filter implements the full `libobs` lifecycle — `create / destroy / update /
get_properties / get_defaults / video_render / get_width / get_height` — and its
calibration is the tested Python `video_calibrated_dims()` taken as the source of truth.

## Native Audio Harmonic Balancing

Audio sample frames passing through the internal DSP matrix are intercepted via the
`filter_audio` callback. Instead of harsh linear peak limiting that clips
frequencies, the buffers are compressed along a smooth recursive curve scaled by
$\varphi$. Below a knee at $1/\varphi$ of the ceiling the signal passes through
untouched; above it, the excess is soft-compressed so the output asymptotically
approaches — but never exceeds — the ceiling:

$$
y(x) =
\begin{cases}
x, & \lvert x \rvert \le \tau/\varphi \\
\operatorname{sign}(x)\left[\dfrac{\tau}{\varphi} + h\,\tanh\!\left(\dfrac{\lvert x \rvert - \tau/\varphi}{h\,\varphi}\right)\right], & \lvert x \rvert > \tau/\varphi
\end{cases}
$$ {#eq:fractisynth-phi-limiter}

where $\tau$ is the ceiling and $h = \tau(1 - 1/\varphi) = \tau/\varphi^{2}$ is the
headroom. The knee of @eq:fractisynth-phi-limiter sits at $\tau/\varphi$, so the
identity region spans exactly the golden $1/\varphi$ fraction of the ceiling; the
$\tanh$ branch is bounded by $h$, guaranteeing $\lvert y \rvert$ approaches but never
crosses $\tau$. This is a compact, explicitly specified transfer curve in the
tradition of digital audio signal-processing design [@smith2007]. The curve is
monotone, sign-preserving, and NaN/Inf-safe (@fig:limiter). These properties
describe the transfer function; they do not establish a perceptual improvement or
a preferred mastering outcome.

The limiter now also emits its own visual pulse: after the same post-limiter samples are
written back into OBS, the engine measures RMS, peak, and a $\varphi$-scaled reactivity
scalar. Those three values feed the Wavefield Console shader, the Telemetry HUD, and the
gateway dock, so the visual surface breathes from the acoustic envelope without ever
letting raw, non-finite audio poison the display.

![The FractiSynth $\varphi$ harmonic limiter (robin's-egg) versus naive hard clipping (dashed charcoal) for threshold $\tau=1$. Marigold guides mark the symmetric identity band $|x|\le 1/\varphi=0.618034$; outside that band the tested `phi_soft_limit()` curve remains monotone, sign-preserving, and bounded by $|y|\le\tau$ while approaching the ceiling smoothly. The statistics panel records the exact knee and the fail-closed handling of non-finite inputs.](../../output/figures/phi_soft_limiter.png){#fig:limiter width=74%}

![Homogeneous spatial transform matrix used by the calibrated video path. The two spatial axes are scaled by $1/\varphi=0.618034$, the homogeneous coordinate remains 1, and the worked 1920×1080 example rounds to 1187×667 pixels. Cell values and the color scale expose the diagonal-only transform implemented by `spatial_scale_matrix()`; the source footer identifies the companion `video_calibrated_dims()` calculation.](../../output/figures/phi_matrix.png){#fig:phi-matrix width=62%}

## Single Source of Truth

Two implementations carry the same calibration: the native C plugin
(`#define EGS_PHI 1.61803398875f`, `#define EGS_GATEWAY_KEY 2.53942700f`) and the
tested Python engine (`synthobs.constants.PHI`, `synthobs.constants.EGS_GATEWAY_KEY`).
Project tests pin both literals against their floating-point counterparts — $\varphi$
to at least nine significant digits and $K_{\text{EGS}}$ to better than $10^{-6}$ — so
the native transducer and the reference engine cannot drift apart silently.

```mermaid
flowchart TB
    SRC["Tested Python engine<br/>src/synthobs — source of truth"]
    SRC -->|"PHI = 1.6180339887…"| PHI{{"φ — golden LAYOUT constant"}}
    SRC -->|"EGS_GATEWAY_KEY = φ·(1030/656.28)<br/>≈ 2.539427"| KEGS{{"K_EGS — solar-wind PHASE lock"}}

    PHI --> V["video_calibrated_dims()<br/>round(dim · 1/φ), ≥ 1"]
    PHI --> A["phi_soft_limit()<br/>knee at τ/φ, tanh branch"]
    KEGS --> S["phase_vector() + gateway lock<br/>lock_strength = |cos(phase_bias)|"]

    V -.->|"implemented at OBS boundary"| CV["C: fractisynth_video"]
    A -.->|"implemented at OBS boundary"| CA["C: fractisynth_audio"]
    S -.->|"implemented at OBS boundary"| CS["C: SWO telemetry thread"]

    LIT["Plugin-artifact tests<br/>pin C literals ↔ Python constants"]
    LIT -.->|"≥9 sig-digit / 1e-6 gate"| CV
    LIT -.-> CA
    LIT -.-> CS
```
<!-- alt: Python-to-native parity map: the Python engine owns PHI, the EGS gateway key, and the tested kernels; C OBS filters and the telemetry thread implement those contracts, while artifact tests pin the shared literals. -->

The two paths converge by contract: the Python engine defines the video scaling of
@eq:fractisynth-calibrated-box, the audio knee of @eq:fractisynth-phi-limiter, and the
SWO phase vector; the native plugin implements the OBS-bound counterparts. Literal
pinning and behavioral checks make material divergence visible.
