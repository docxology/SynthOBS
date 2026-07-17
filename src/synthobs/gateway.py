"""The El Gran Sol (EGS) Gateway — solar-wind → modeled phase score.

A faithful, fail-closed port of the FractiAI *Microsoft Silica EGS Gateway* core
(``egs_gateway.py``). The gateway is the real-time translator between the Sun's
energetic state and the FractiSynth phase plane: it injects the live solar-wind
speed as a phase bias on the virtual 1030 nm reader, weighted by the EGS Fractal
Constant (the gateway key ``K_EGS = φ·λ_reader/λ_Hα``), and reports how strongly
the modeled system score for the current admitted wind value.

Where the :mod:`synthobs.swo` oscillator locks the *amplitude* plane from F10.7
flux and active-region count, the gateway locks the *phase* plane from solar wind.
Both fail closed: a non-physical input never produces a lock.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import (
    EGS_GATEWAY_KEY,
    LAMBDA_READER_NM,
    REFERENCE_SOLAR_WIND_KMS,
)

__all__ = ["GatewayLock", "egs_fractal_constant", "gateway_filter"]

_TWO_PI = 2.0 * math.pi


def egs_fractal_constant() -> float:
    """Return the EGS Fractal Constant / gateway key ``K_EGS`` (≈ 2.539427).

    Exposed as a function matching the FractiAI gateway vocabulary; the value itself is
    :data:`synthobs.constants.EGS_GATEWAY_KEY`.
    """
    return EGS_GATEWAY_KEY


@dataclass(frozen=True)
class GatewayLock:
    """The gateway state derived from one solar-wind reading.

    ``phase_bias_rad`` — the wind-driven phase bias on the reader, wrapped to
    ``[0, 2π)``. ``lock_strength`` — ``|cos(phase_bias)|`` in ``[0, 1]``: 1.0 is a
    perfect lock, 0.0 is fully out of phase. ``effective_shift_nm`` — first-order
    dispersive wavelength shift (nm) used for lock diagnostics.
    """

    solar_wind_kms: float
    phase_bias_rad: float
    lock_strength: float
    effective_shift_nm: float
    reader_wavelength_nm: float = LAMBDA_READER_NM


def gateway_filter(
    solar_wind_kms: float,
    *,
    reader_wavelength_nm: float = LAMBDA_READER_NM,
) -> GatewayLock:
    """Apply live solar wind as a phase bias on the 1030 nm reader (fail-closed).

    ``phase_bias = (2π · wind/REF · K_EGS) mod 2π`` and
    ``lock_strength = |cos(phase_bias)|``. Raises :class:`ValueError` on a
    non-positive **or non-finite** wind speed — the gateway never locks on a
    stale/zeroed/garbage indicator, mirroring the SWO Hold State (callers catch
    and hold the last good lock). Failing closed here, not only in the caller,
    keeps this public API honest for any consumer.
    """
    if isinstance(solar_wind_kms, bool) or isinstance(reader_wavelength_nm, bool):
        raise ValueError("gateway inputs must be real, finite numbers")
    try:
        valid_wind = math.isfinite(solar_wind_kms) and solar_wind_kms > 0.0
        valid_reader = math.isfinite(reader_wavelength_nm) and reader_wavelength_nm > 0.0
    except (TypeError, ValueError):
        valid_wind = valid_reader = False
    if not valid_wind:
        raise ValueError(f"solar_wind_kms must be positive and finite, got {solar_wind_kms}")
    if not valid_reader:
        raise ValueError(
            f"reader_wavelength_nm must be positive and finite, got {reader_wavelength_nm}"
        )

    norm = solar_wind_kms / REFERENCE_SOLAR_WIND_KMS
    phase_bias = (_TWO_PI * norm * EGS_GATEWAY_KEY) % _TWO_PI
    lock_strength = abs(math.cos(phase_bias))
    effective_shift = reader_wavelength_nm * (EGS_GATEWAY_KEY * 1e-4) * math.sin(phase_bias)

    return GatewayLock(
        solar_wind_kms=solar_wind_kms,
        phase_bias_rad=phase_bias,
        lock_strength=lock_strength,
        effective_shift_nm=effective_shift,
        reader_wavelength_nm=reader_wavelength_nm,
    )
