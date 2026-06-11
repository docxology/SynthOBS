"""The Solar Wavefield Oscillator (SWO) calibration core.

The SWO calibrates the software matrix exclusively from current space telemetry and
emits a single phase-locked harmonic variable — the ``system_phase_vector`` — used
by both the SynthOBS interface layers and the FractiSynth core filters. This is a
faithful Python mirror of the blueprint's C ``synchronize_swo_calibration`` routine
(see ``plugin/fractisynth/src/fractisynth.c``), with identical fail-closed behaviour:

    system_phase_vector = (current_flux / active_spots) · φ

When active regions like AR4465/AR4464 shift or flare, the changing values alter the
phase vector in real time. When telemetry is invalid (``flux <= 0`` or ``spots <= 0``)
the oscillator refuses to recalibrate and **holds** its last verified vector — it
never substitutes an average or a zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import PHI
from .gateway import GatewayLock, gateway_filter

__all__ = ["SolarWavefieldOscillator", "phase_vector"]


def phase_vector(flux: float, spots: int) -> float:
    """The pure calibration map ``(flux / spots) · φ`` (ISC-19, ISC-23).

    Caller must guarantee ``flux > 0`` and ``spots > 0``; this is the inner kernel
    used once inputs are validated.
    """
    return (flux / float(spots)) * PHI


@dataclass
class SolarWavefieldOscillator:
    """Stateful calibrator. Starts un-calibrated; holds last good vector on failure.

    Fields mirror the C ``SolarWavefieldOscillator`` struct one-to-one:
    ``active_f107_flux``, ``monitored_sunspots``, ``system_phase_vector``,
    ``is_calibrated``.
    """

    active_f107_flux: float = 0.0
    monitored_sunspots: int = 0
    system_phase_vector: float | None = None
    is_calibrated: bool = False

    # --- EGS gateway (phase) plane: locked from live solar wind ----------- #
    # The amplitude plane (above) locks from flux/spots; the gateway phase plane
    # locks from solar wind. Both fail closed and hold independently.
    gateway: GatewayLock | None = None

    def lock_gateway(self, solar_wind_kms: float) -> bool:
        """Lock the EGS gateway phase plane from a live solar-wind reading, or HOLD.

        Returns ``True`` and updates :attr:`gateway` (phase bias + lock strength)
        on a positive wind speed; returns ``False`` and holds the last lock on a
        non-positive/non-finite reading. Independent of amplitude calibration —
        the gateway can hold while the oscillator re-locks, and vice-versa.
        """
        if not math.isfinite(solar_wind_kms) or solar_wind_kms <= 0.0:
            return False
        self.gateway = gateway_filter(solar_wind_kms)
        return True

    @property
    def lock_strength(self) -> float:
        """Gateway lock strength ``|cos(phase_bias)|`` in ``[0,1]``; 0.0 if no lock."""
        return self.gateway.lock_strength if self.gateway is not None else 0.0

    @property
    def wind_phase(self) -> float:
        """Gateway phase bias (radians); 0.0 if the gateway has never locked."""
        return self.gateway.phase_bias_rad if self.gateway is not None else 0.0

    def calibrate(self, current_flux: float, active_spots: int) -> bool:
        """Lock the live telemetry into the system phase vector, or HOLD.

        Returns ``True`` and updates the vector on valid input; returns ``False``
        and leaves the last good vector untouched (Hold State) when
        ``current_flux <= 0`` or ``active_spots <= 0``, or if the result is not
        finite (ISC-19..24). Never raises, never divides by zero, never emits NaN.
        """
        # ENFORCEMENT: block any stale, default, or zeroed indicator (fail closed).
        if current_flux <= 0.0 or active_spots <= 0:
            self.is_calibrated = False
            return False

        vector = phase_vector(current_flux, active_spots)
        if not math.isfinite(vector):  # defensive: never publish NaN/Inf
            self.is_calibrated = False
            return False

        self.active_f107_flux = current_flux
        self.monitored_sunspots = active_spots
        self.system_phase_vector = vector
        self.is_calibrated = True
        return True

    def hold_vector(self) -> float | None:
        """The vector currently driving the system — the last verified value, or
        ``None`` if the oscillator has never successfully calibrated (ISC-25)."""
        return self.system_phase_vector
