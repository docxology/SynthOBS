# AGENTS.md — `SynthOBS/plugin/fractisynth/data/locale`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

OBS plugin localization: `en-US.ini` maps the lookup keys used by
`fractisynth.c`'s property/display strings to user-visible names. Add new
locales as sibling `<lang>.ini` files with identical keys; the C code falls
back to the key itself when a string is missing.

## Layout (verified by direct listing, 2026-08-29)

```
en-US.ini
```

## Gotchas

- Key names in the .ini must match the `obs_module_get_string` lookups in
  `../src/fractisynth.c`; a renamed key silently falls back to the raw key
  in the OBS UI.
- Never `git add` anything under `projects/ongoing/`.
