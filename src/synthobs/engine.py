"""The SynthEngine — the unified wavefield that binds telemetry, the SWO, the
Goldilocks layout, the FractiSynth DSP, and the modality console into one
phase-locked system.

Data flow (blueprint §6, §2.2)::

    live telemetry → SWO calibration → system_phase_vector
                                          ├── layout / font / transition scaling
                                          └── audio LF modulation + video displacement

When telemetry is unavailable the engine enters a smooth **Hold State**, frozen to
the last verified vector until a live connection is re-established. It refuses to
modulate before the first successful calibration unless explicitly placed in demo
mode.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .console import Console, Mode
from .dsp import AudioEnvelope, audio_envelope, phi_soft_limit, video_calibrated_dims
from .interference import (
    InterferenceVerdict,
    NodeField,
    holographic_gate,
)
from .layout import Viewport, assemble_viewport
from .swo import SolarWavefieldOscillator
from .telemetry import SolarTelemetry, SolarWind, TelemetryUnavailable

__all__ = ["SynthEngine", "EngineState"]


@dataclass
class EngineState:
    """Snapshot of the engine's calibration health (amplitude + gateway planes)."""

    mode: Mode
    is_calibrated: bool
    phase_vector: float | None
    holding: bool  # True when running on a held (stale-connection) vector
    last_source: str | None
    lock_strength: float = 0.0  # EGS gateway lock |cos(phase_bias)| ∈ [0,1]
    wind_phase: float = 0.0  # gateway phase bias (radians)
    verdict: InterferenceVerdict | None = None  # holographic interference outcome


class SynthEngine:
    """The vessel console core. One instance drives one broadcast environment."""

    def __init__(self, *, mode: Mode = Mode.OBSERVATORY, demo_mode: bool = False) -> None:
        self._mode = Mode(mode)
        self._demo = demo_mode
        self._swo = SolarWavefieldOscillator()
        self._console = Console()
        self._console.validate()
        self._last_source: str | None = None
        self._holding = False

    # ----- mode control -------------------------------------------------
    @property
    def mode(self) -> Mode:
        return self._mode

    def switch_mode(self, mode: Mode) -> Mode:
        """Switch to one of the three valid decks (ISC-53)."""
        self._mode = Mode(mode)  # Mode(...) rejects anything outside the enum
        return self._mode

    @property
    def console(self) -> Console:
        return self._console

    # ----- calibration --------------------------------------------------
    def update(self, telemetry: SolarTelemetry | None) -> bool:
        """Ingest a telemetry reading and recalibrate the SWO (ISC-49, ISC-50).

        On a valid reading, calibrates and clears Hold State. On ``None`` (the
        caller caught :class:`TelemetryUnavailable`) the engine HOLDS its last good
        vector and reports ``holding=True``. Returns the calibration success bool.
        """
        if telemetry is None:
            # Connectivity drop / invalid telemetry → smooth Hold State.
            self._holding = self._swo.is_calibrated or self._swo.system_phase_vector is not None
            return False
        ok = self._swo.calibrate(telemetry.flux, telemetry.sunspots)
        if ok:
            self._last_source = telemetry.source
            self._holding = False
        else:
            self._holding = self._swo.system_phase_vector is not None
        return ok

    def update_from_fetch(self, fetch) -> bool:  # pragma: no cover - thin wrapper
        """Convenience: call a zero-arg telemetry fetcher and update, catching
        :class:`TelemetryUnavailable` into the Hold State."""
        try:
            telemetry = fetch()
        except TelemetryUnavailable:
            return self.update(None)
        return self.update(telemetry)

    # ----- EGS gateway (phase plane) ------------------------------------
    def update_gateway(self, wind: SolarWind | None) -> bool:
        """Lock the EGS gateway phase plane from a live solar-wind reading, or HOLD.

        ``None`` (the caller caught :class:`TelemetryUnavailable`) holds the last
        gateway lock. Returns the gateway lock success bool. Independent of the
        amplitude (flux/spots) calibration — a wind dropout never disturbs the SWO
        vector, and a flux dropout never disturbs the gateway lock.
        """
        if wind is None:
            return False
        return self._swo.lock_gateway(wind.speed_kms)

    @property
    def lock_strength(self) -> float:
        """EGS gateway lock strength ``|cos(phase_bias)|`` ∈ [0,1]; 0.0 if unlocked."""
        return self._swo.lock_strength

    @property
    def wind_phase(self) -> float:
        """EGS gateway phase bias (radians); 0.0 if the gateway has never locked."""
        return self._swo.wind_phase

    def holographic_verdict(self) -> InterferenceVerdict | None:
        """Resolve the holographic interference gate from the current lock state.

        Builds the AR14409 node from the gateway phase (amplitude = lock strength)
        and the hydrogen phase-flip node from the conjugate phase, then runs
        :func:`synthobs.interference.holographic_gate`. Returns ``None`` until the
        gateway has locked at least once (no phase plane ⇒ no verdict).
        """
        if self._swo.gateway is None:
            return None
        phase = self._swo.wind_phase
        amp = max(self._swo.lock_strength, 1e-6)
        ar = NodeField(amp * math.cos(phase), amp * math.sin(phase))
        h_flip = NodeField(amp * math.cos(-phase), amp * math.sin(-phase))
        return holographic_gate(ar, h_flip)

    @property
    def phase_vector(self) -> float | None:
        return self._swo.system_phase_vector

    def state(self) -> EngineState:
        return EngineState(
            mode=self._mode,
            is_calibrated=self._swo.is_calibrated,
            phase_vector=self._swo.system_phase_vector,
            holding=self._holding,
            last_source=self._last_source,
            lock_strength=self._swo.lock_strength,
            wind_phase=self._swo.wind_phase,
            verdict=self.holographic_verdict(),
        )

    def _require_vector(self) -> float:
        vec = self._swo.system_phase_vector
        if vec is None:
            if self._demo:
                return 1.0  # demo mode: a neutral unity vector
            raise TelemetryUnavailable(
                "engine refuses to modulate before first successful calibration (ISC-54)"
            )
        return vec

    # ----- layout & DSP -------------------------------------------------
    def layout(self, width: int, height: int) -> Viewport:
        """Self-assemble the Goldilocks viewport (primary 61.8% / console 38.2%)."""
        return assemble_viewport(width, height)

    def modulate_video(self, width: int, height: int) -> tuple[int, int]:
        """Calibrated video bounding box, gated on a live/held vector (ISC-52, ISC-54)."""
        self._require_vector()
        return video_calibrated_dims(width, height)

    def modulate_audio(self, samples, threshold: float = 1.0) -> list[float]:
        """φ soft-limit an audio buffer, gated on a live/held vector (ISC-52, ISC-54)."""
        self._require_vector()
        return phi_soft_limit(samples, threshold)

    def measure_audio(self, samples, threshold: float = 1.0) -> AudioEnvelope:
        """Post-limiter audio envelope, gated on a live/held vector."""
        self._require_vector()
        return audio_envelope(samples, threshold)
