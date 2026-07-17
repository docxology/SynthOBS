# AGENTS.md — SynthOBS / FractiSynth

Working rules for agents in this project. (LOCAL-ONLY sidecar project, symlinked
into the template at `projects/working/SynthOBS`; never committed to the public
template tree.)

## Architecture

- `src/synthobs/` is the **verified source of truth**. It imports nothing from
  `infrastructure.*` and has zero I/O outside `telemetry.py`. All golden-ratio
  geometry, SWO calibration, DSP, console model, and command grammar live here and
  are tested directly.
- `plugin/fractisynth/` is a native C `libobs` adapter with local kernels for the
  contracts that must execute inside OBS; its constants and selected behaviors are
  checked against the Python engine. `plugin/synthobs/` is an `obspython` bridge
  that imports the engine rather than maintaining a second command implementation.
- `scripts/` are thin orchestrators: import the engine, do I/O + matplotlib only.

## Invariants (do not break)

- **One φ.** `PHI = (1+√5)/2` is defined once in `constants.py`; the C plugin pins
  `EGS_PHI 1.61803398875f`. A test asserts they agree to ≥9 sig digits — keep it.
- **Fail closed.** Telemetry/SWO/command parser reject invalid input by raising or
  returning False + holding the last good vector — never substitute a default.
- **Console shape.** Exactly 3 modes × 7 buttons = 3 common + 4 unique; the 3 common
  ids are identical across modes; unique ids are disjoint. `Console.validate()` and
  `test_console_and_commands.py` enforce this — update both on any change.
- **Real I/O only.** HTTP via `pytest-httpserver`; real numbers; fixed seeds.
- **Coverage ≥ 90%** on `src/synthobs`.

## Commands

```bash
uv run pytest projects/working/SynthOBS/tests/ --cov=synthobs --cov-fail-under=90
uv run python projects/working/SynthOBS/scripts/generate_figures.py
```

## Manuscript voice

The manuscript intentionally preserves the FractiSynth / El Gran Sol **brand voice**
(visionary register) per the principal's choice — do not add epistemic caveats to
the prose. Code comments stay technically accurate (φ is the golden ratio).
