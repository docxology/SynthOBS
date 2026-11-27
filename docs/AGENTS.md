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
- Public guides describe generated figures in text and point to the
  [figure build](rendering.md#generate-and-check-the-evidence). The generated
  `output/figures/` directory belongs to the local build. Keep render-required
  image references in the manuscript.
- Scholarship claims are audited via `scripts/audit_scholarship.py`
  (see `docs/scholarship.md` and `scholarship_sources.json`).

## How docs here are maintained

- Keep per-topic files scoped; the manuscript (`docs/manuscript/`) sources its
  content from these docs and the formal Lean layer (`lean/`).
- Commands must be copied from `README.md`/`pyproject.toml`, never invented.

## Notes for agents

- Never commit anything under `output/`.
- The publication bundle lives at [`docs/manuscript/`](manuscript/AGENTS.md).
