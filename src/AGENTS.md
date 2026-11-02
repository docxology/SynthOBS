# AGENTS.md — `SynthOBS/src`

> Repo-wide policy for template projects is maintained in the template repository, not restated here.

## What this is

Home of the `synthobs` Python package — the **tested engine and verified
source of truth** for the whole project (see `synthobs/AGENTS.md` for the
per-module map). Layout follows the src-layout convention wired in
`pyproject.toml` (`pythonpath = [".", "src"]`, coverage `source =
["synthobs"]`, `fail_under = 90`). The engine is stdlib-only by design; the
`figures`/`dev` extras (numpy, matplotlib, pytest, pytest-httpserver) serve
the scripts and tests, not the engine.

## Verify

```bash
uv run pytest tests/ --cov=synthobs --cov-fail-under=90
uv build && uv run python scripts/package_smoke.py   # stdlib-only import check
```

## Layout (verified by direct listing, 2026-08-29)

```
synthobs/
```

## Gotchas

- Keep the package dependency-free: adding an import outside the stdlib to
  `src/synthobs` breaks the package-smoke gate and the "engine is the single
  source of truth" claim.
- Never `git add` anything under `projects/ongoing/`.
