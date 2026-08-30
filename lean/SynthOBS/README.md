# SynthOBS/

Lean 4 library source for the SynthOBS invariant scaffold. `Invariants.lean`
proves the structural contracts — console cardinality (3 modes x 7 buttons),
shared common buttons, disjoint mode-unique buttons, safety ids, pinned
phi/EGS literals, and fail-closed SWO/provenance acceptance predicates — with
no `sorry` and no custom axioms. See AGENTS.md for the theorem inventory and
build command (`cd lean && lake build`).

Part of the DataTools lane (local-only, never committed). Parent: `../README.md`.
