# SynthOBS Architectural Specification (The Interface) {#sec:architecture}

SynthOBS replaces the manual canvas configuration of standard broadcasting software
with a single golden-ratio layout engine. Scenes and sources are no longer dragged
into place by hand; they self-assemble as operational decks on an exploration
vessel, every boundary derived from the EGS fractal constant $\varphi$ rather than
from arbitrary pixel coordinates.

## The Global Split Architecture

The interface establishes a clear division of operational responsibilities:

- **The Modality Control Decks.** Each of the three modes exposes an *irreducible
  minimum of 7 console buttons*. Exactly three are common infrastructure that bridge
  legacy capabilities — the operational overlap with standard OBS: the Crew Collab
  Link (remote crew ingestion), the Record Wave Pass (local recording to
  $\varphi$-optimized disk sectors), and Launch Stream (live broadcasting). The
  remaining four are entirely unique layered-synthesis and tracking capabilities,
  one of which is always the mode's fail-closed safety control.
- **The Omnipresent Command Line.** Mounted globally at the very base of the
  SynthOBS interface, a persistent terminal line remains open and in active focus.
  At any moment the operator can bypass the visible buttons entirely to input
  scripting, multi-variable macros, or manual routing overrides.

## The Goldilocks UX Framework

The user interface self-assembles dynamically using a recursive golden-ratio layout
matrix. The active mode's control deck balances its screen footprint automatically
against the live stream canvas. Every partition descends from a single governing
law — the **golden split** — which carves any span into a major and a minor part in
the proportion of the EGS fractal constant $\varphi \approx 1.61803398875$:

$$
\mathrm{major} = \operatorname{round}\!\left(\frac{\text{total}}{\varphi}\right),
\qquad
\mathrm{minor} = \text{total} - \mathrm{major}
$$ {#eq:golden-split}

Applied to the canvas, @eq:golden-split fixes the two operational decks:

- **Primary Output Canvas ($V_p$):** allocates the major share — exactly
  $1/\varphi \approx 61.8\%$ of available screen space — to the primary object of
  attention and active stream output:

  $$
  V_p = \frac{1}{\varphi} \approx 0.618
  $$ {#eq:primary-fraction}

- **Control & Telemetry Deck ($V_a$):** the complementary minor share houses the 7
  hardwired console buttons and the real-time SWO tracking graphs:

  $$
  V_a = 1 - \frac{1}{\varphi} = \frac{1}{\varphi^{2}} \approx 0.382
  $$ {#eq:telemetry-fraction}

The identity $V_a = 1/\varphi^{2}$ in @eq:telemetry-fraction is the self-similar
signature of $\varphi$ — the minor share of one split is the major share of the
next, so the layout nests fractally to any depth without ever introducing a new
constant.

![The Goldilocks Layout Matrix self-assembled for a 1920×1080 canvas. The primary output deck occupies the major golden column ($\approx 61.8\%$ of canvas area, robin's-egg blue); the right column is split vertically into the console deck (4 unique + 3 common buttons) and the SWO telemetry strip (marigold). The three decks tile the canvas exactly with no overlap or lost pixels — a property enforced by the tested `assemble_viewport()` engine function.](../output/figures/goldilocks_layout.png){#fig:layout width=85%}

The split is integer-exact and fails closed against rounding loss. Because the
minor part in @eq:golden-split is defined as the residual $\text{total} - \mathrm{major}$
rather than independently rounded, the partition always satisfies

$$
\mathrm{major} + \mathrm{minor} = \text{total}
$$ {#eq:lossless-tiling}

with no lost pixels — the rounding remainder of @eq:golden-split is absorbed
entirely by the minor part. The viewport assembled by the tested
`assemble_viewport()` engine function applies @eq:golden-split twice — once
horizontally, once vertically on the right column — so the three decks tile the
canvas exactly per @eq:lossless-tiling:

```text
┌──────────────────────────────┬───────────────────┐
│                              │  CONSOLE DECK     │
│                              │  (major height,   │
│      PRIMARY OUTPUT CANVAS   │   ≈61.8%)         │
│      Vₚ = major width        │   3 common +      │
│      ≈61.8% (robin's-egg)    │   4 unique btns   │
│                              ├───────────────────┤
│                              │  SWO TELEMETRY    │
│                              │  (minor height,   │
│                              │   ≈38.2%, marigold)│
└──────────────────────────────┴───────────────────┘
   golden_split(width) ─┘        └─ golden_split(height)
```

The lossless property of @eq:lossless-tiling is verified across a swept range of
integer canvas dimensions in the project test suite (`tiles_exactly()` confirms the
three regions partition the canvas with zero overlap and zero gap).

## Visual Styling Vectors (Golden Age, Mid-Century Philosophy)

- **Aesthetic Directive:** clean mid-century modern design principles combined with
  a classic Golden Age layout — understated structural framing, functional symmetry,
  and scannable visual balance.
- **Chrome Properties:** warm organic charcoal, linen, and matte bone textures that
  ground the interface, eliminating high-gloss glare and emphasizing structural
  weight.
- **Accent Signifiers:** robin's-egg blue and muted turquoise for phase-locked
  operational status indicators; rich marigold orange for real-time telemetry
  markers and modulated active vectors.
