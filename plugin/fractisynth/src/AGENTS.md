# AGENTS.md — `SynthOBS/plugin/fractisynth/src`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

Native source of the FractiSynth OBS plugin. `fractisynth.c` implements the
`fractisynth_video` / `fractisynth_audio` / `fractisynth_inspector` filters
and the `fractisynth_console` generated source, plus the mutex-guarded
process-global SWO calibration struct and the background libcurl NOAA SWPC
thread (60 s poll, fail-closed Hold State). `fractisynth_dock.cpp` is the
Qt dock UI. Headers are self-contained: `rtsw_parser.h` (real-time solar-wind
JSON parser), `sha256.h` (provenance hashing), `text8x8.h` (bitmap font).
These are the native counterparts of `../../src/synthobs` contracts; the phi
and K_EGS literals here are pinned by `synthobs.constants.PHI_C_LITERAL` and
checked by `../../../tests/test_plugin_artifacts.py` and
`../../../tests/test_c_parity_behavioral.py`.

## Layout (verified by direct listing, 2026-08-29)

```
fractisynth.c, fractisynth_dock.cpp, rtsw_parser.h, sha256.h, text8x8.h
```

## Gotchas

- Keep the fail-closed telemetry rule: any curl/parse failure must leave the
  last verified SWO vector untouched.
- Never `git add` anything under `projects/ongoing/`.
