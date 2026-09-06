# Verified OBS evidence bundle

These captures are the versioned manuscript assets promoted from the live OBS
acceptance run `20260717T153649Z`, after rebuilding and installing the native
FractiSynth bundle against OBS 32.1.2. They are not synthetic illustrations.

| Asset | Capture | SHA-256 |
| --- | --- | --- |
| `obs_scene_render.png` | 1280 × 720 compositor render and manuscript cover | `6ba6019ec491b2e99804e4f6dccb40eee41a5a5ff23786b296891ad9fb315887` |
| `obs_telemetry_hud.png` | 1280 × 720 telemetry HUD with verified LSB strip | `5f2c21c2632eac29453370377e2bbda225ae0d42194799d2900e940de6beb82f` |
| `obs_audio_tone.png` | 1280 × 720 controlled-tone audio-reactivity capture | `9f5234adaa3323cd35f2dca3cb179ddd60641380c4c312bf2a72988250672842` |
| `obs_audio_silent.png` | 1280 × 720 silent baseline paired with the tone capture | `2525025ac904a0b950d38a8f851a3c73e1b724332360dd53090d80d152df7a66` |
| `controlled_tone.wav` | 48 kHz, mono, 16-bit, 2 s, 440 Hz controlled input | `4942835581a82ba0a4fe604050495933c992325b528c984ca361fa5cb705f729` |
| `obs_operator_window.png` | 1604 × 1858 operator-context OBS Studio window capture (user-supplied; contextual, not an automated gate) | `5c5c3289422844169f065f104dae19eee4e54a3f867a40efdd0906debd137a5d` |

The complete gate and provenance record is [`obs_manifest.json`](obs_manifest.json).
The promotion was performed by `scripts/promote_obs_evidence.py`, which validates
all gates before copying bytes and recomputing hashes, dimensions, and WAV metadata.
The run used OBS 32.1.2, obs-websocket 5.7.3, a 3200 × 2000 base canvas, and
all six required gates passed: connection, dashboard fit, engine-level interaction
model, render content, audio reactivity, and telemetry provenance. The interaction
gate intentionally does not claim that an OBS Interact-window click was transported;
that remains a separate live acceptance task.

The operator-context screenshot is user-supplied and intentionally not part of the
six-gate machine manifest. It shows host UI context and is not used to establish
render, audio, telemetry, or provenance metrics.
