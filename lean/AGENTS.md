# AGENTS.md — `SynthOBS/lean`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

The Lean 4 invariant scaffold for SynthOBS/FractiSynth: a Lake project
(package `synthobs-invariants`, version `1.618.0`) that machine-checks the
structural contracts the Python/C engine must honor — console shape,
fail-closed acceptance, and literal pinning. It is proof scaffolding only:
the executable engine remains Python/C (`../src/synthobs`), and the Lean
layer pins what should not depend on floating-point runtime details.

## Build

Toolchain is pinned in `lean-toolchain` (`leanprover/lean4:v4.28.0`); the
library target is declared in `lakefile.lean` (`lean_lib SynthOBS`), with
`SynthOBS.lean` as the single root import. Standard build:

```bash
cd lean && lake build
```

(unverified here — `lake build` was not run during the doc pass per lane
rules; static inspection only.) `lean-manifest.json`/`lake-manifest.json`
pins the dependency set. `tests/test_lean_invariants.py` additionally
rejects `sorry` / custom `axiom` placeholders and runs `lake build` when a
Lean toolchain is available.

## Layout (verified by direct listing, 2026-08-29)

```
SynthOBS/, SynthOBS.lean, lake-manifest.json, lakefile.lean, lean-toolchain
```

## Gotchas

- Do NOT run `lake build` casually in the slow sidecar checkout: it may
  fetch toolchain/Mathlib artifacts over the network. The behavioral parity
  tests (`tests/test_lean_invariants.py`) cover the invariant text without a
  full toolchain when Lake is absent.
- Never `git add` anything under `projects/ongoing/`.
