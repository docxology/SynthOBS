# SynthOBS — docs/ Agent Guide

## Layout

Topic-scoped technical references for the SynthOBS/FractiSynth console and
native plugin: `architecture.md`, `engine.md`, `golden-ratio.md`,
`command-grammar.md`, `telemetry.md`, `native-plugin.md`, `egs-gateway.md`,
`interference.md`, `formal-invariants.md`, `usage.md`, `build-and-install.md`,
`testing.md`, `scholarship.md` (+ `scholarship_sources.json`), `README.md`.

## Conventions observed

- Root `README.md` is the user entry point (quickstart, regenerate-figures,
  package smoke gate); `docs/` holds the deeper per-subsystem references.
- Figures referenced from docs live under `output/figures/` and are
  **generated artifacts** (regenerate with
  `uv run python scripts/generate_figures.py`; `output/` is git-ignored).
  Doc links to them are valid after a local figure generation; do not treat
  their absence in a fresh checkout as broken doc structure.
- Scholarship claims are audited via `scripts/audit_scholarship.py`
  (see `docs/scholarship.md` and `scholarship_sources.json`).

## How docs here are maintained

- Keep per-topic files scoped; the manuscript (`manuscript/`) sources its
  content from these docs and the formal Lean layer (`lean/`).
- Commands must be copied from `README.md`/`pyproject.toml`, never invented.

## Notes for agents

- Never commit anything under `output/`.
- `manuscript/` is the publication bundle: see `manuscript/AGENTS.md`.
