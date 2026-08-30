# AGENTS.md — `SynthOBS/lean/SynthOBS`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

The Lean 4 source of the `SynthOBS` invariant library (package
`synthobs-invariants`, imported via `../SynthOBS.lean`). The single module
`Invariants.lean` (namespace `SynthOBS`, imports `Std`) formalizes, with
`native_decide`/`rfl` proofs and **no `sorry` or custom axioms**:

- **Console shape.** `Mode` = {observatory, laboratory, expedition};
  `commonIds` = 3 shared buttons; `uniqueIds` = 4 per mode; theorems pin
  `mode_count = 3`, `button_count = 7`, identical `commonIds` prefix across
  modes, the safety id present in every mode, and pairwise disjointness of
  mode-unique ids and of unique-vs-common ids.
- **Literal pinning.** `phiLiteral = "1.61803398875"` and
  `egsGatewayKeyLiteral = "2.53942700"` — the same literals the C plugin and
  Python constants pin (see `../docs/formal-invariants.md`).
- **Fail-closed acceptance.** `acceptsSwoInput` rejects non-finite/non-positive
  flux and non-positive spots; `provenanceReady` requires SWO calibration AND
  gateway lock AND positive flux AND positive wind.

These mirror the Python contracts in `src/synthobs/console.py`, `swo.py`,
and `provenance.py`; the executable engine stays Python/C by design.

## Layout (verified by direct listing, 2026-08-29)

```
Invariants.lean
```

## Gotchas

- Keep this module dependency-light (`Std` only, no Mathlib) so `lake build`
  stays cheap and the repo-side `test_lean_invariants.py` textual checks keep
  matching the source.
- Never `git add` anything under `projects/ongoing/`.
