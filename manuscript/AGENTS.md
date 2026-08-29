# SynthOBS Manuscript — Agent Guide

## Layout

| Path | Purpose |
|---|---|
| `config.yaml` | Paper metadata (parses cleanly; yaml.safe_load verified 2026-08-29) |
| `preamble.md` | Shared preamble |
| `references.bib` | BibTeX bibliography |
| `00_abstract.md`–`08_evaluation_reproducibility.md` | Ordered section sources (incl. `06a_*`, `06b_*` sub-sections) |
| `99_references.md` | References section |
| `assets/` | Manuscript assets |

## Conventions

- Figure links target `../output/figures/*` — generated artifacts
  (`uv run python scripts/generate_figures.py`); the figure manifest is
  `output/figures/figure_manifest.json` (16 entries: 13 analytical + 3 promoted
  live captures, per root `README.md`). Links resolve only after local generation.
- `04_fractisynth.md` contains Mermaid diagrams with `{{...}}` node labels —
  these are Mermaid syntax, not unresolved template tokens (verified against
  the renderer conventions).
- Citations resolve against `references.bib` via Pandoc.
- Formal claims ground in the Lean layer (`lean/`) — see
  `docs/formal-invariants.md`.

## Maintenance

Section order is stable (numeric prefixes, `06a`/`06b` inserted between 06 and
07). Do not renumber; add new sub-sections with letter suffixes.
