# `tests/` — the zero-mock suite

**1136 tests, 98.37 % coverage** on `src/synthobs` (≥ 90 % gate). No mocks anywhere —
HTTP is exercised with `pytest-httpserver`, numerics with real concrete inputs (including
`±1e9`, `±inf`, `nan`), files with real temp files, and the C plugin / Lean scaffold by
reading and building the real artifacts.

Per-file counts, the ISC map, and the no-mocks patterns: [`../docs/testing.md`](../docs/testing.md).

## Run

```bash
# from the template root (project is symlinked into projects/working/SynthOBS)
uv run pytest projects/working/SynthOBS/tests/ --cov=synthobs --cov-fail-under=90

# from this project, against src/
PYTHONPATH="$PWD/src" python -m pytest tests/ -q
```

## What each file covers

| File | Covers |
| --- | --- |
| `test_constants_and_layout.py` | φ constants single-source + Goldilocks split, subdivision, spiral, viewport tiling |
| `test_telemetry.py` | fail-closed NOAA F10.7 / solar-wind / non-finite parsing |
| `test_swo_and_dsp.py` | oscillator phase + Hold State; φ soft limiter, post-limiter envelope, calibrated dims |
| `test_console_and_commands.py` | 3 modes × 7 buttons + `/mode`,`/transducer`,`/swo`,`/dashboard` fail-closed parsing |
| `test_engine.py` | calibrate / hold, layout, pre-calibration modulation refusal |
| `test_gateway_and_interference.py` | `K_EGS`, `lock_strength`, holographic verdict, live solar-wind feed |
| `test_solar_series.py` | NOAA plasma, GOES X-ray, and Kp time-series parsers |
| `test_history.py` | bounded telemetry history, eviction, normalization |
| `test_provenance.py` | record packing, SHA checksum, LSB/visible signature, tamper evidence |
| `test_provenance_verify_tool.py` | real PNG provenance-strip verification + CLI mismatch rejection |
| `test_interaction_and_layers.py` | feed targets, layer rail, marker drop, dashboard plans |
| `test_plugin_artifacts.py` | native C/source static structure, audio uniforms + envelope release hold, φ/K_EGS pins |
| `test_fail_closed_fuzz.py` | adversarial NaN/±Inf battery across every ingestion boundary |
| `test_docs_contracts.py` | markdown links resolve, figure manifest, stale-baseline guards |
| `test_lean_invariants.py` | Lean scaffold has no `sorry`/custom `axiom`; `lake build` passes when available |
| `test_obs_scenario_probe.py` | live scenario manifest schema, skip semantics, `--require-live` exit |
| `test_verification.py` | audio-meter ROI oracle, live-gate result validation, fail-closed `ValueError` guards |

`conftest.py` holds shared fixtures. The documentation contracts in
`test_docs_contracts.py` are why this README's numbers (and every status doc) cannot
silently go stale.
