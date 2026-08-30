# AGENTS.md — `SynthOBS/plugin/synthobs`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

The obspython console bridge: one script, `synthobs_console.py`, loaded in
OBS via Tools → Scripts. It imports the engine (`src/synthobs`) and drives
it with `apply_command`; imports are guarded so the script degrades
gracefully outside OBS. The native FractiSynth plugin
(`../fractisynth/`) is a separate artifact — this bridge never re-implements
console behavior, it reuses the Python source of truth.

## Layout (verified by direct listing, 2026-08-29)

```
synthobs_console.py
```

## Gotchas

- Keep any new capability in `src/synthobs` and re-export it here; adding
  console logic to this script breaks the single-source-of-truth invariant
  guarded by the test suite.
- Never `git add` anything under `projects/ongoing/`.
