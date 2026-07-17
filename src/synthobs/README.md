# `src/synthobs/` — the tested engine (source of truth)

This package is the **verified source of truth** for SynthOBS. It has zero OBS
dependency and zero network I/O outside `telemetry.py`, which is exactly what makes it
testable without OBS or network services. The native C plugin (`plugin/fractisynth/`)
implements the small native kernels at the OBS boundary and is checked against these
contracts; the obspython script (`plugin/synthobs/`) imports this engine rather than
duplicating its logic.

Full API reference: [`../../docs/engine.md`](../../docs/engine.md). Golden-ratio math:
[`../../docs/golden-ratio.md`](../../docs/golden-ratio.md). System map:
[`../../docs/architecture.md`](../../docs/architecture.md).

## The 15 modules

| Module | Responsibility |
| --- | --- |
| `constants.py` | Single definition of `PHI`, derived ratios, and EGS anchors (`EGS_GATEWAY_KEY`). Zero I/O. |
| `layout.py` | Goldilocks golden split (integer-exact), recursive subdivision, golden spiral, viewport assembly. |
| `telemetry.py` | Fail-closed NOAA SWPC client + parsing; raises `TelemetryUnavailable` on anything malformed. |
| `swo.py` | Solar Wavefield Oscillator — phase vector `φ·(flux/spots)`; **holds** the last good value on bad input. |
| `gateway.py` | El Gran Sol gateway — locks the phase plane from solar wind via `K_EGS`; `lock_strength = |cos(bias)|`. |
| `interference.py` | Holographic interference gate (non-Boolean) + Recursive Sourced Interference step. |
| `dsp.py` | φ-calibrated video dimensions, the spatial scale matrix, the φ-knee soft limiter. |
| `console.py` | The three operator modes and the 7-button console (3 common + 4 unique per mode). |
| `commands.py` | Terminal grammar parser (`parse`); fails closed (`CommandError`) on unknown verbs / bad values. |
| `interaction.py` | Seven feed-tab targets, layer-toggle rail geometry, marker-drop resolution. |
| `layers.py` | Deterministic OBS dashboard/layer plans for Wavefield, Telemetry HUD, and Solar Graph. |
| `history.py` | Bounded telemetry history ring buffer feeding the HUD waveform sparklines. |
| `provenance.py` | Telemetry-record packing, default checksum plus opt-in HMAC authenticity, LSB/visible-signature embedding, and fail-closed validation. |
| `engine.py` | `SynthEngine` — orchestrates calibration, layout, and modulation; refuses to modulate pre-calibration. |
| `verification.py` | Pure live-gate oracle: audio-meter ROI scoring (`uv.y > 0.955`) and `GateResult` pass/fail/skip. |

## Invariants (do not break)

- **One φ.** `PHI = (1+√5)/2` is defined once here; the C plugin pins
  `EGS_PHI 1.61803398875f`. A test asserts they agree to ≥9 significant digits.
- **Fail closed.** Telemetry / SWO / command parser reject invalid input by raising or
  returning `False` and holding the last good vector — never substitute a default.
- The public surface is whatever `__init__.py` `__all__` re-exports; `engine.md`
  documents the one exception (`is_monotone_non_decreasing`, `synthobs.dsp` only).
