# AGENTS.md — `SynthOBS/.github/workflows`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

The single CI workflow of the public SynthOBS repo: `verify.yml` ("SynthOBS
verification"; triggers: push, pull_request, workflow_dispatch). Job 1
**engine** (`ubuntu-latest`, `astral-sh/setup-uv@v5`): `uv sync --extra dev`
→ `python scripts/generate_figures.py` → `pytest tests --cov=synthobs
--cov-fail-under=90` → `uv build` → `python scripts/package_smoke.py`.
Job 2 **native-parser** ("Native parser behavioral parity"): `uv sync
--extra dev` → `pytest tests/test_c_parity_behavioral.py -q` — the C/Python
parser parity gate, kept separate so a libobs-free runner can still validate
it.

## Layout (verified by direct listing, 2026-08-29)

```
verify.yml
```

## Gotchas

- Any new required gate belongs in this one workflow; there is no second
  workflow to drift against.
- Never `git add` anything under `projects/ongoing/`.
