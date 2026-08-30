# AGENTS.md — `SynthOBS/.github`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

GitHub configuration for the **public SynthOBS distribution**
(`github.com/docxology/SynthOBS`): a single CI workflow,
`workflows/verify.yml` ("SynthOBS verification"), triggered on every push,
pull request, and manual dispatch. It has two jobs:

1. **engine** ("Engine, figures, and package", ubuntu) — `uv sync --extra
   dev`, then `scripts/generate_figures.py`, the full pytest suite with
   `--cov=synthobs --cov-fail-under=90`, `uv build`, and
   `scripts/package_smoke.py`.
2. **native-parser** ("Native parser behavioral parity", ubuntu) — runs
   `tests/test_c_parity_behavioral.py`, the Python-vs-native-parser parity
   gate that does not need libobs.

Note this file tree belongs to the standalone public repo, not the template's
root `.github/` — the 16-job template CI is documented in the template root,
not here.

## Layout (verified by direct listing, 2026-08-29)

```
workflows/
```

## Gotchas

- The coverage floor (90) in `verify.yml` and `pyproject.toml` must move
  together.
- Never `git add` anything under `projects/ongoing/`.
