# Holographic Interference

The EGS Gateway does not resolve to raw True/False. Following the canonical FractiAI
design, it resolves to an **interference outcome** at named holographic nodes —
constructive at the AR14409 solar node ("true"), a destructive hydrogen phase-flip
("false"), or mixed. This page documents that logic and the RSI feedback motor.

Engine: [`src/synthobs/interference.py`](../src/synthobs/interference.py).

## NodeField — a complex resonator

A holographic node carries a complex amplitude:

```python
from synthobs.interference import NodeField

a = NodeField(3.0, 4.0)
a.magnitude        # 5.0  (|a|)
a + NodeField(1, -1)   # NodeField(4, 3)
a.scaled(2.0)      # NodeField(6, 8)
a.conjugate()      # NodeField(3, -4)  (the phase-flip)
```

Interference intensity is plain wave superposition:

```python
interference_intensity(a, b) = |a + b|²
```

In-phase fields reinforce (4× intensity); anti-phase fields cancel (0). The cosmic
framing is the brand voice; the arithmetic is ordinary physics.

## The holographic gate

```python
from synthobs.interference import holographic_gate, InterferenceVerdict

verdict = holographic_gate(ar14409, hydrogen_phase_flip, reference=NodeField(1, 0))
```

- **`CONSTRUCTIVE_AR14409`** ("true") — constructive interference dominates at the
  AR14409 node, measured against the reference beat.
- **`DESTRUCTIVE_H_PHASE_FLIP`** ("false") — the hydrogen phase-flip node's
  self-conjugate beat dominates (a real-valued flip survives its conjugate, a purely
  imaginary one cancels — the gate measures `|h + conj(h)|²`).
- **`MIXED`** — the two intensities tie within a small margin.

```python
is_holographic_true(verdict)    # verdict is CONSTRUCTIVE_AR14409
is_holographic_false(verdict)   # verdict is DESTRUCTIVE_H_PHASE_FLIP
```

The engine builds the gate from the live gateway state — the AR14409 node from the
wind phase (amplitude = lock strength), the hydrogen node from its conjugate — and
exposes the verdict on `engine.state().verdict`. Until the gateway has locked at least
once, the verdict is `None` (no phase plane ⇒ no verdict).

## Recursive Sourced Interference (RSI)

RSI is the FractiAI corpus's core feedback motor — an output fed back as a
scale-shifted input. One step is a gain-and-scale multiply:

```python
rsi_step(x, gain, scale) = gain · scale · x
```

Its one genuinely checkable property is the stability criterion:

```python
rsi_is_stable(gain, scale)   # |gain · scale| < 1
```

When `|gain·scale| < 1` the iteration **contracts** toward zero; when
`|gain·scale| > 1` it diverges in magnitude. This is the mathematical content the corpus
offers — a tunable fixed point — and SynthOBS implements exactly that, with tests for
both the contracting and diverging regimes.

## How the shader uses it

The native shader renders the interference as animated `|a+b|²` fringes whose spatial
frequency is set by `K_EGS` and whose intensity is gated by `lock_strength` — bright
antinodes, dark nodes, with the hydrogen H-alpha tint strongest at the antinodes. See
[native-plugin.md](native-plugin.md#the-shader) and [egs-gateway.md](egs-gateway.md).
