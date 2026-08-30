# AGENTS.md — `SynthOBS/plugin/fractisynth/data`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

OBS plugin data shipped alongside the native module: three HLSL-style
`.effect` shaders loaded by libobs at filter/source creation —
`fractisynth.effect` (phi-scaled video filter displacement),
`fractisynth_console.effect` (the console source, consuming the
post-limiter RMS/peak/reactivity uniforms), and `fractisynth_inspector.effect`
(Zoom Inspector loupe with phi-grid and crosshair) — plus `locale/`
(en-US.ini) for the properties UI strings. Shader uniform names are part of
the contract `fractisynth.c` sets per-frame; renaming one breaks rendering
at runtime, not compile time.

## Layout (verified by direct listing, 2026-08-29)

```
locale/, fractisynth.effect, fractisynth_console.effect, fractisynth_inspector.effect
```

## Gotchas

- The data dir must be installed alongside the binary (build.sh handles
  this); a plugin binary without these effects fails to render.
- Never `git add` anything under `projects/ongoing/`.
