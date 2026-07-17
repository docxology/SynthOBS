# Formal Invariants

SynthOBS now carries a small Lean 4 project under [`../lean`](../lean). It is not
the runtime engine and it does not replace the Python/C test surface. It is a
buildable proof scaffold for contracts that are stable, structural, and worth
pinning outside prose.

## Scope

`lean/SynthOBS/Invariants.lean` proves:

- exactly three modes exist;
- exactly three common button ids exist;
- each mode has exactly four unique ids and seven total buttons;
- each mode's first three button ids are the shared common ids;
- unique ids do not collide with common ids or with another mode's unique ids;
- each mode has its safety button;
- the C/Python literal pins for `PHI` and `EGS_GATEWAY_KEY` stay explicit;
- the SWO acceptance predicate rejects non-finite flux, non-positive flux, or
  non-positive active-region counts;
- the provenance gate is true only when SWO calibration, gateway lock, positive
  flux, and positive solar wind are all present.

## Build

```bash
cd lean
lake build
```

The default Python suite also runs this build when `lake` is available and rejects
`sorry` or custom `axiom` placeholders in the scaffold. The project has no mathlib
dependency, so a cold build is small and deterministic.

## Boundary

Floating-point runtime behavior remains tested in Python and mirrored in C. The Lean
scaffold intentionally formalizes structural and Boolean gate contracts rather than
pretending to prove native OBS rendering, libcurl I/O, or IEEE-754 shader behavior.
