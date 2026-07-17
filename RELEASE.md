# SynthOBS & FractiSynth — public v1 release contract

## Status

Version `1.618.0` is the public v1 release. The canonical source is
[`github.com/docxology/SynthOBS`](https://github.com/docxology/SynthOBS). On
2026-07-17 the remote was flipped from private to public, tag `v1.618.0` was
pushed, and the [GitHub release](https://github.com/docxology/SynthOBS/releases/tag/v1.618.0)
was published with the regenerated PDF/HTML and built package attached. A
hardcoded OBS WebSocket default-password default (present in earlier commits'
`scripts/obs_scenario_probe.py` / `scripts/obs_ws_probe.py`) was scrubbed from
the entire git history via `git filter-repo` and force-pushed before the
visibility flip; the working-tree fix (empty-string default, requires
`OBS_WEBSOCKET_PASSWORD` or `--password`) landed in the same commit that opened
this release. The archival deposit is minted: DOI
[`10.5281/zenodo.21418688`](https://doi.org/10.5281/zenodo.21418688). The
repository is also mirrored on Software Heritage:
[`swh:1:snp:282b236c662b3caf77d823f175b4d3af35e568e2`](https://archive.softwareheritage.org/swh:1:snp:282b236c662b3caf77d823f175b4d3af35e568e2/).

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
citation resolves to `manuscript/references.bib`. Figures must exist first — the
audit and `test_docs_contracts.py` both check that manuscript claims resolve to
real files under `output/figures/`:

```bash
uv run python scripts/generate_figures.py
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
uv run python scripts/generate_figures.py
uv run python -m pytest tests --cov=synthobs --cov-fail-under=90
uv run python scripts/audit_scholarship.py
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

**Public v1 is affirmative.** All gates above are satisfied: the repository is
public, `v1.618.0` is tagged and released with the regenerated PDF/HTML and
built package attached, the clean-clone preflight passes (1217 tests,
96.09% coverage), and DOI `10.5281/zenodo.21418688` archives the exact tagged
source and artifacts. Remaining scope (`SYNTHOBS-OBS-CI`,
`SYNTHOBS-OBS-INTERACTION`, `SYNTHOBS-LIVE-MATRIX`, `SYNTHOBS-FILTER-VISUALS`)
is tracked forward work in [`TODO.md`](TODO.md), not a blocker to this release.
