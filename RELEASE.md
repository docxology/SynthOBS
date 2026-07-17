# SynthOBS & FractiSynth — public v1 release contract

## Status

Version `1.618.0` is a publication candidate, not yet a public release. The
canonical target is [`github.com/docxology/SynthOBS`](https://github.com/docxology/SynthOBS).
On 2026-07-17 the remote was verified as private, and this local publication
sidecar contains uncommitted release changes. Do not label the artifact public v1
until the intended source is committed, pushed, publicly cloneable, and tagged.

The author affiliation is **FractiAI / Active Inference Institute**. The repository
is intended to be the canonical public source for the Python engine, native OBS
module, obspython bridge, tests, documentation, manuscript, and evidence metadata.

## Release contents

The public repository must include, in one inspectable source tree:

- `src/synthobs/` — the dependency-free Python source of truth;
- `plugin/fractisynth/` — the native C `libobs` module and macOS build/install path;
- `plugin/synthobs/` — the obspython console bridge;
- `tests/`, `scripts/`, and `lean/` — executable verification and reproduction paths;
- `README.md`, `docs/`, `TODO.md`, `ROADMAP.md`, `CITATION.cff`, and the manuscript;
- `manuscript/assets/obs/` — the hashed, versioned live OBS evidence bundle.

`output/` is regeneratable and ignored by source control. The final PDF and HTML
should be regenerated from the committed tree and attached to the GitHub release.

## Scholarly release metadata

The public release must preserve the software's identity as well as its executable
behavior. Before tagging, run the scholarship audit and confirm that every manuscript
citation resolves to `manuscript/references.bib`:

```bash
uv run python scripts/audit_scholarship.py
uv run python -m pytest tests/test_docs_contracts.py -q
```

`CITATION.cff` is the machine-readable citation surface for the candidate. At the
public-tag step, set its `date-released`, add the exact release URL, and add the
versioned archival DOI if a repository such as Zenodo is used. Do not insert a
placeholder DOI. The exact tag, commit, platform, OBS version, input products, and
evidence-manifest hash belong in the release notes so a reader can identify the
software object behind a reported run.

## Clean-clone preflight

Run this from a fresh public checkout:

```bash
git clone https://github.com/docxology/SynthOBS.git
cd SynthOBS
uv sync --extra dev
uv run python -m pytest tests --cov=synthobs --cov-fail-under=90
uv run python scripts/audit_scholarship.py
uv run python scripts/generate_figures.py
uv build
uv run python scripts/package_smoke.py
```

The expected current baseline is **1217 passing tests** and **96.09% coverage**
on `src/synthobs`. Figure generation must validate the versioned live evidence
manifest before writing the analytical and live-capture figures.

## macOS OBS installation and use

The verified native path targets OBS Studio `32.1.2` on macOS and requires Xcode
Command Line Tools, `git`, `clang`, and `libcurl`; the optional dock additionally
requires a Qt `6.8.x` build matching OBS. From the public checkout:

```bash
cd plugin/fractisynth
./build.sh --install
```

Restart OBS, confirm the FractiSynth module loads, then add the
**SynthOBS — φ Wavefield Console** source or a FractiSynth video/audio filter.
For the obspython bridge, open **Tools → Scripts**, add
`plugin/synthobs/synthobs_console.py`, and use the documented command grammar.
The complete build details are in [`docs/build-and-install.md`](docs/build-and-install.md)
and the in-OBS workflow is in [`docs/usage.md`](docs/usage.md).

## Public artifact verification

Before tagging, the release owner must verify:

- the working tree is clean and contains every intended source, test, doc, and evidence asset;
- `v1.618.0` points to the reviewed commit and the GitHub repository is publicly cloneable;
- the clean-clone preflight above passes without local source-path assumptions;
- the regenerated PDF and HTML are attached to the release and link back to the repository;
- the live evidence manifest records its exact OBS/macOS boundary and does not imply a cross-platform claim.

The current live run proves the documented OBS `32.1.2`/macOS path, including module
load, compositor content, audio reactivity, provenance extraction, and engine-level
interaction resolution. Actual OBS click transport, headless OBS CI, cross-platform
coverage, and per-filter/per-feed visual captures remain scoped in [`TODO.md`](TODO.md).

## Release decision

The candidate is technically reproducible locally, but it is **not yet full public
v1** while the remote remains private and the source changes are uncommitted. The
public-v1 decision becomes affirmative after the owner completes the repository
visibility, commit/tag, clean-clone, and release-artifact gates above.
