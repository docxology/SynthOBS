# AGENTS: `scripts/` — Thin Orchestrator Contract

## Contract

- `scripts/` contains **thin orchestrators only**: argparse, path bootstrap, logging,
  and a single delegated call into `src/synthobs/` entrypoints (plus the I/O those
  entrypoints need: file reads/writes, matplotlib, live OBS sockets).
- Business, data, plot, and analysis logic lives in `src/synthobs/`, where it is
  importable and tested by `tests/`. Do not add engine math, parsers, or validators
  to a script — move them into the engine and delegate.
- The engine is **stdlib-only** (`pyproject.toml` `dependencies = []`); a doc-contract
  test AST-scans `src/synthobs/` for third-party imports. numpy/matplotlib belong to
  scripts only (the `figures` extra). Pure engine modules perform no I/O — callers
  wire files in (see `src/synthobs/scholarship.py`).
- `scripts/__init__.py` makes this directory a package; pytest's `pythonpath = [".", "src"]`
  lets tests import `scripts.<module>` and `synthobs` directly.
- Path bootstrap: each script inserts `<repo>/src` into `sys.path` before importing
  `synthobs` (the established pattern here — no shared helper module).

## Inventory

| Script | Delegates to | Notes |
| --- | --- | --- |
| `generate_figures.py` | `synthobs` engine + matplotlib | `FIGURE_FILES`/`CONTEXTUAL_ASSETS`/`FIGURE_SOURCES` are pinned by `tests/test_docs_contracts.py`; regenerating figures changes hashed manifests |
| `audit_scholarship.py` | `synthobs.scholarship.validate_scholarship_ledger` | reads `docs/scholarship_sources.json` + `docs/manuscript/references.bib`; exit 1 on any validation error (fail-closed) |
| `verify_provenance_strip.py` | `synthobs.provenance` | `verify_png`/`record_summary` are imported by tests |
| `promote_obs_evidence.py` | self-contained promotion gate | no engine import: implements the fail-closed hash/PNG/WAV checks inline and rewrites the `synthobs.live_scenario.v2` manifest; target defaults to `docs/manuscript/assets/obs/` |
| `obs_scenario_probe.py` | `synthobs.verification`, `synthobs.provenance`, `synthobs.interaction`, `scripts.verify_provenance_strip` | interactive live-OBS instrument, not a unit-tested module; its pure helpers (`_image_content_gate`, `_png_to_rgba_bytes`) ARE tested |
| `obs_ws_probe.py` | self-contained obs-websocket v5 client | interactive live-OBS instrument; `websocket-client` is a dev extra imported in a `try/except` so import never crashes without it |
| `package_smoke.py` | `venv`/`subprocess` | requires a built wheel (`uv build`); runs the engine with `-I` (isolated) to prove zero runtime deps |

## Gotchas

- `MPLBACKEND=Agg` is set via `os.environ.setdefault` **before** importing matplotlib —
  keep that ordering in any script that renders.
- The live-OBS scripts (`obs_scenario_probe.py`, `obs_ws_probe.py`) need OBS running
  with obs-websocket enabled; the password comes from `OBS_WEBSOCKET_PASSWORD` or
  `--password`, never from a committed file.
- Promoted evidence lands in `docs/manuscript/assets/obs/` (the manuscript bundle
  lives under `docs/`); the doc-contract tests hash every asset there.
- The scholarship ledger's `source_of_truth`/`tests`/`artifacts` paths are
  existence-checked by `audit_scholarship.py` — moving a file means updating the
  ledger in the same change.
- Keep `scripts/README.md`'s inventory table in sync with this directory; the
  doc-contract tests pin figure counts and manifests, not this table, so drift here
  is silent.
