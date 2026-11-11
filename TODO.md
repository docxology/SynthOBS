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
| `SYNTHOBS-PACKAGE-REPRO` | `scripts/package_smoke.py` installs the `uv build` wheel with `--no-index --no-deps` into a fresh isolated environment; the workflow runs the 1226-test/94.53%-coverage gate, figure generation, and package smoke. |

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

## Workflowz review — 2026-11-10

- [ ] **SYNTHOBS-CANVAS-FALLBACK** — P1 — Make canvas-size fallback safe outside OBS and observable when used. Evidence: `plugin/synthobs/synthobs_console.py:185-192` calls `obs.obs_get_video_info(info)` and logs through `obs` even though `obs` is explicitly `None` outside OBS; the fallback then returns `_DEFAULT_CANVAS`. Outcome: a non-OBS caller receives the documented default without a secondary `AttributeError`, while an OBS query failure still returns the default and emits one warning. Acceptance probe from repo root: `uv run python -c "import importlib.util, pathlib; p=pathlib.Path('plugin/synthobs/synthobs_console.py'); s=importlib.util.spec_from_file_location('synthobs_console_probe', p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m._canvas_size())"` (use the actual canvas helper name if it differs from `_canvas_size`); it must print the default dimensions and exit 0 without OBS installed. Dependencies/constraints: preserve the real OBS query when available, keep the default constant unchanged, and do not add an OBS stub to production code.

- [ ] **SYNTHOBS-AUDIO-RESTART-GATE** — P1 — Do not treat an unexecuted audio restart as a successful audio capture. Evidence: `scripts/obs_scenario_probe.py:406-415` catches `ObsScenarioError` around `OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART`, executes `pass`, then sleeps and captures `audio_tone` unconditionally. Outcome: a failed restart produces an explicit failed/skipped audio gate (or a deliberate, documented pre-restart capture), never a manifest that implies the tone was restarted and measured. Acceptance probe from repo root: run the existing scenario-probe test suite with a controlled fake client whose restart request raises `ObsScenarioError`, then assert the observable result is a nonzero/failed audio gate and no successful `audio_tone` capture is recorded; a successful fake restart must still record the capture. Dependencies/constraints: retain real websocket behavior and the existing settle/capture path for successful restarts; distinguish an intentional unsupported-media skip from a silent failure in the manifest.

- [ ] **SYNTHOBS-TODO-CONTRACT-MAINTENANCE** — P2 — Keep the canonical-backlog documentation test from rejecting legitimate backlog changes. Evidence: `tests/test_docs_contracts.py:70-90` hard-codes active and completed ID tuples and asserts their presence in fixed TODO sections, while `TODO.md:3-7` defines TODO.md as the single actionable backlog. Outcome: adding, completing, or removing a scoped item requires only the intended TODO/documentation update, while the test still verifies the backlog links and required section structure. Acceptance probe from repo root: make a temporary, otherwise valid TODO edit that adds a uniquely marked active item and run `uv run python -m pytest tests/test_docs_contracts.py -q`; the test must pass without editing the test’s ID list, and removing a required backlog link/section must still fail. Dependencies/constraints: preserve the existing canonical-link checks and the four current backlog items; do not weaken the test into a source-text assertion about implementation details.
