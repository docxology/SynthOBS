# SynthOBS TODO — scoped future work

This is the single actionable backlog for SynthOBS. Completed work belongs in
[`ROADMAP.md`](ROADMAP.md) and historical decisions remain in [`ISA.md`](ISA.md);
new follow-up work should be added here before it appears in another status page.
Each item has a bounded completion test so “planned” does not become an unmeasured
claim.

## Priority order

| ID | Priority | Scope | Done when |
| --- | --- | --- | --- |
| `SYNTHOBS-OBS-CI` | P0 | Add a reproducible headless/containerized OBS acceptance target for the six-gate scenario. | CI runs the real binary, websocket path, compositor content, audio ROI, and provenance checks on a pinned environment; unavailable environments are explicit skips. |
| `SYNTHOBS-OBS-INTERACTION` | P1 | Exercise actual OBS Interact/projector click transport, not only the pure resolver. | A live manifest records a transported click for feed, layer, and marker targets with before/after state evidence. |
| `SYNTHOBS-LIVE-MATRIX` | P2 | Repeat live acceptance across supported OBS, OS, Qt, and audio-driver combinations. | One versioned manifest exists per supported environment, with build identity and explicit gate results. |
| `SYNTHOBS-FILTER-VISUALS` | P2 | Capture per-feed and per-filter visual evidence, including the zoom inspector and native dock controls. | Each documented visual claim has a versioned capture or is removed from the status prose. |

## Recently completed

| ID | Evidence |
| --- | --- |
| `SYNTHOBS-PUBLIC-V1` | `docxology/SynthOBS` is public (`gh repo view` → `"isPrivate": false`); tag `v1.618.0` and its non-draft release exist and attach the regenerated PDF/HTML (`gh release view v1.618.0` → 4 assets); local `main` (`02eef27`) matches `origin/main` exactly (`git rev-list --left-right --count main...origin/main` → `0 0`); CI green on the release commit (`gh run list`). |
| `SYNTHOBS-ARCHIVE-DOI` | Concept DOI `10.5281/zenodo.21418687` resolves live to version deposit `21418901` (`state: submitted`, `publication_date: 2026-07-17`), whose metadata matches the repo version/author/ORCID/license and links back to the exact `v1.618.0` tag via `related_identifiers`; `CITATION.cff` and `README.md` carry the same DOI. |
| `SYNTHOBS-C-PARITY` | `plugin/fractisynth/src/rtsw_parser.h` is a standalone dependency-free parser; `tests/test_c_parity_behavioral.py` compiles and executes it against current, shuffled, inactive, stale, future, and malformed RTSW rows. |
| `SYNTHOBS-PROV-HMAC` | `build_authenticated_payload` and `verify_authenticated_payload` provide opt-in HMAC-SHA-256 authenticity; verifier tests cover missing, wrong, empty, and recomputed-key cases, and keys remain outside manifests/source. |
| `SYNTHOBS-PACKAGE-REPRO` | `scripts/package_smoke.py` installs the `uv build` wheel with `--no-index --no-deps` into a fresh isolated environment; the workflow runs the 1217-test/96.09%-coverage gate, figure generation, and package smoke. |

## Guardrails for every item

- Preserve the Python engine as the source of truth and keep I/O, OBS control, and
  rendering in thin orchestrators.
- Add the smallest executable negative control before claiming a verifier is stronger.
- Do not turn the live evidence bundle into a statistical or cross-platform claim.
- Keep the manuscript’s chosen FractiSynth / El Gran Sol voice; technical code and
  evidence metadata remain precise.

## Explicitly accepted boundaries

These are not TODO items: the current unkeyed provenance checksum is documented as
corruption-detecting rather than authenticating; the interaction gate is engine-level
until `SYNTHOBS-OBS-INTERACTION` is complete; and the native plugin’s live evidence is
for the documented OBS 32.1.2/macOS environment only.
