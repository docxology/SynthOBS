"""Holographic interference logic — the FractiAI gateway's non-Boolean gate.

The EGS Gateway does not resolve to raw True/False. It resolves to an *interference
outcome* at named holographic nodes: constructive interference at the AR14409 solar
node reads as "true", a destructive hydrogen phase-flip reads as "false", and a tie
is "mixed". This module ports that logic (``holographic_gate`` from the FractiAI
``egs_gateway.py``) plus Recursive Sourced Interference (RSI), the corpus's core
feedback motor, whose repeated step contracts toward zero exactly when
``|gain · scale| < 1``.

These are real, deterministic operations on complex amplitudes — the cosmic framing
is the brand voice; the arithmetic is plain wave superposition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "NodeField",
    "InterferenceVerdict",
    "interference_intensity",
    "holographic_gate",
    "is_holographic_true",
    "is_holographic_false",
    "rsi_step",
    "rsi_is_stable",
]


@dataclass(frozen=True)
class NodeField:
    """Complex amplitude at a holographic node (a 'living resonator')."""

    re: float
    im: float

    @property
    def magnitude(self) -> float:
        """``|a|`` — the field magnitude."""
        return math.hypot(self.re, self.im)

    def __add__(self, other: "NodeField") -> "NodeField":
        return NodeField(self.re + other.re, self.im + other.im)

    def scaled(self, s: float) -> "NodeField":
        """Return this field scaled by a real factor ``s``."""
        return NodeField(self.re * s, self.im * s)

    def conjugate(self) -> "NodeField":
        """Return the complex conjugate (the phase-flip of this node)."""
        return NodeField(self.re, -self.im)


class InterferenceVerdict(str, Enum):
    """Holographic logic outcome — interference at a named node, not a Boolean."""

    CONSTRUCTIVE_AR14409 = "constructive_ar14409"  # the "true" branch
    DESTRUCTIVE_H_PHASE_FLIP = "destructive_h_phase_flip"  # the "false" branch
    MIXED = "mixed"


def interference_intensity(a: NodeField, b: NodeField) -> float:
    """``|a + b|²`` — constructive (large) vs destructive (small) superposition."""
    s = a + b
    return s.re * s.re + s.im * s.im


def holographic_gate(
    ar14409: NodeField,
    hydrogen_phase_flip: NodeField,
    *,
    reference: NodeField | None = None,
    margin: float = 1e-9,
) -> InterferenceVerdict:
    """Resolve the holographic interference gate.

    ``CONSTRUCTIVE_AR14409`` when constructive interference dominates at the AR14409
    node (vs the reference beat); ``DESTRUCTIVE_H_PHASE_FLIP`` when the hydrogen
    phase-flip node's self-conjugate beat dominates; ``MIXED`` within ``margin``.
    """
    ref = reference if reference is not None else NodeField(1.0, 0.0)
    i_ar = interference_intensity(ar14409, ref)
    i_h = interference_intensity(hydrogen_phase_flip, hydrogen_phase_flip.conjugate())

    # Fail closed on garbage: a NaN/Inf node would silently resolve to MIXED (all
    # comparisons with NaN are False) or a spurious CONSTRUCTIVE verdict from Inf.
    if not (math.isfinite(i_ar) and math.isfinite(i_h)):
        raise ValueError("non-finite interference intensity — fail closed")

    if i_ar > i_h + margin:
        return InterferenceVerdict.CONSTRUCTIVE_AR14409
    if i_h > i_ar + margin:
        return InterferenceVerdict.DESTRUCTIVE_H_PHASE_FLIP
    return InterferenceVerdict.MIXED


def is_holographic_true(verdict: InterferenceVerdict) -> bool:
    """True iff the gate resolved constructive at the AR14409 node."""
    return verdict is InterferenceVerdict.CONSTRUCTIVE_AR14409


def is_holographic_false(verdict: InterferenceVerdict) -> bool:
    """True iff the gate resolved a destructive hydrogen phase-flip."""
    return verdict is InterferenceVerdict.DESTRUCTIVE_H_PHASE_FLIP


def rsi_step(x: float, gain: float, scale: float) -> float:
    """One Recursive Sourced Interference step: ``gain · scale · x``.

    The FractiAI core motor — an output fed back as a scale-shifted input.
    Repeated application contracts toward zero when ``|gain·scale| < 1`` and
    diverges in magnitude when ``|gain·scale| > 1`` (see :func:`rsi_is_stable`).
    """
    return gain * scale * x


def rsi_is_stable(gain: float, scale: float) -> bool:
    """True iff the RSI recursion ``gain·scale·x`` contracts (``|gain·scale| < 1``)."""
    return abs(gain * scale) < 1.0
