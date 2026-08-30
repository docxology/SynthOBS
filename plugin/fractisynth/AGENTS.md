# AGENTS.md — `SynthOBS/plugin/fractisynth`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

The native FractiSynth `libobs` plugin (v1.618): `src/` holds the C/C++
kernels (`fractisynth.c` — three filters + generated console source;
`fractisynth_dock.cpp` — Qt dock), `data/` holds the OBS `.effect` shaders
and `locale/` localization. Build via `./build.sh --install` (macOS verified
path) or CMake (`cmake -B build -DOBS_ROOT=...`); release builds require
libcurl. `README.md` documents the filters, the process-global SWO struct,
and the 60 s NOAA SWPC telemetry thread; build/load evidence lives in
`../../docs/build-and-install.md`. The C constants are checked against the
Python engine by `tests/test_plugin_artifacts.py` and the CI
`native-parser` parity job.

## Layout (verified by direct listing, 2026-08-29)

```
data/, src/, CMakeLists.txt, README.md, build.sh
```

## Gotchas

- Never substitute a default SWO vector on bad telemetry — the C side must
  fail closed exactly like `src/synthobs/swo.py`.
- `src/fractisynth.c` is a single-file C core by design; the headers
  (`rtsw_parser.h`, `sha256.h`, `text8x8.h`) are local, dependency-free.
- Never `git add` anything under `projects/ongoing/`.
