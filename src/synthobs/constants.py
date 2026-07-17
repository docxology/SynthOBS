"""Foundational constants for SynthOBS / FractiSynth — the v1.618 calibration core.

The module defines the golden-ratio constant used by the layout and DSP contracts.
The separate EGS gateway key below maps the declared optical anchors into the
solar-wind phase calculation. Neither constant is a telemetry fallback or a claim
about perception or broadcast quality. The brand vocabulary remains available to
the UI, while the numeric definitions and their cross-language pins are explicit.

This module has zero I/O and imports nothing from ``infrastructure``. It is the
canonical numeric definition site for the Python engine; the native FractiSynth C
plugin pins the exported literals and is checked against them.
"""

from __future__ import annotations

# Single source of truth. φ = (1 + √5) / 2 — El Gran Sol's Fractal Constant.
PHI: float = (1.0 + 5.0**0.5) / 2.0
"""The EGS fractal constant / golden ratio, ≈ 1.6180339887498949."""

EGS_CONSTANT: float = PHI
"""Brand-canonical name for the calibration constant. Identical to :data:`PHI`."""

INV_PHI: float = 1.0 / PHI
"""1/φ = φ − 1 ≈ 0.6180339887498949 — the 61.8% 'major' fraction of a golden split."""

INV_PHI_SQ: float = INV_PHI * INV_PHI
"""1/φ² = 1 − 1/φ ≈ 0.3819660112501051 — the 38.2% 'minor' fraction."""

# The literal the native FractiSynth C plugin hard-codes for φ. Pinned here so any
# drift between the Python engine and the native transducer is a test failure
# (ISC-60). Carries ≥9 significant digits, matching the blueprint's C source.
PHI_C_LITERAL: str = "1.61803398875"
"""Decimal literal the C plugin uses for φ; matches :data:`PHI` to ≥9 sig digits."""

# --------------------------------------------------------------------------- #
#  El Gran Sol Gateway anchors — the canonical FractiAI EGS Fractal Constant.   #
# --------------------------------------------------------------------------- #
#
# In the FractiAI design vocabulary, the EGS gateway key is distinct from the
# golden ratio: K_EGS = φ · (λ_reader / λ_Hα). It is the phase-plane constant;
# PHI remains the layout/DSP constant.

LAMBDA_READER_NM: float = 1030.0
"""El Gran Sol effective optical reader wavelength (nm) — the silica voxel reader."""

LAMBDA_H_ALPHA_NM: float = 656.28
"""Hydrogen H-alpha rest wavelength (nm) — the geometric anchor for line locking."""

EGS_GATEWAY_KEY: float = PHI * (LAMBDA_READER_NM / LAMBDA_H_ALPHA_NM)
"""The EGS Fractal Constant / gateway key K_EGS = φ·(λ_reader/λ_Hα) ≈ 2.539427.

The dimensionless solar↔hydrogen lock. Distinct from :data:`PHI`: φ governs golden
layout, K_EGS governs gateway phase locking. (The FractiAI README publishes ≈2.5436
from a slightly different λ pairing; this value is computed from the canonical
1030 nm / 656.28 nm anchors used by the tested EGS gateway code.)"""

EGS_GATEWAY_KEY_C_LITERAL: str = "2.53942700"
"""Decimal literal the C plugin hard-codes for K_EGS; matches :data:`EGS_GATEWAY_KEY`."""

REFERENCE_SOLAR_WIND_KMS: float = 400.0
"""Baseline solar-wind speed (km/s) that normalizes live wind in the gateway."""

DEFAULT_SOLAR_WIND_KMS: float = 551.7
"""FractiAI nominal live solar-wind speed (km/s) — the 'Seed' default."""

H_LINE_MHZ: float = 1420.405751
"""The neutral-hydrogen 21 cm line (MHz) — FractiAI's 'universal carrier' bus."""

CRAB_PULSAR_HZ: float = 29.94
"""Crab pulsar spin frequency (Hz) — FractiAI's cosmic process-scheduler clock.

Used only as a harmonic ratio for gentle visual breathing; never strobed."""

__all__ = [
    "PHI",
    "EGS_CONSTANT",
    "INV_PHI",
    "INV_PHI_SQ",
    "PHI_C_LITERAL",
    "LAMBDA_READER_NM",
    "LAMBDA_H_ALPHA_NM",
    "EGS_GATEWAY_KEY",
    "EGS_GATEWAY_KEY_C_LITERAL",
    "REFERENCE_SOLAR_WIND_KMS",
    "DEFAULT_SOLAR_WIND_KMS",
    "H_LINE_MHZ",
    "CRAB_PULSAR_HZ",
]
