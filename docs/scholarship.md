# Scholarship, provenance, and citation policy

SynthOBS is a research software artifact as well as an OBS plugin. This page makes
the scholarship boundary explicit: external sources establish the meaning and
provenance of interfaces, data products, standards, and methods; the repository's
code, tests, manifests, and captures establish what this implementation actually
does. A citation is context, not a substitute for an executable verification.

The machine-readable source and claim ledger lives in
[`docs/scholarship_sources.json`](scholarship_sources.json). Validate it with:

```bash
./.venv/bin/python scripts/audit_scholarship.py
```

The current deterministic verification baseline is **1217 tests with 94.44% source
coverage**, generated from the checked-in test run; the six live OBS gates are reported
independently in the versioned manifest.

## Source hierarchy

The project uses the strongest available source for each claim class:

| Claim class | Preferred evidence | SynthOBS example |
| --- | --- | --- |
| Interface contract | Maintainer documentation or protocol source | [OBS Module API](https://docs.obsproject.com/reference-modules) and [obs-websocket](https://github.com/obsproject/obs-websocket) define the host boundary; tests and a live manifest establish this implementation's behavior. |
| External data provenance | The producing institution's product catalogue or feed | [NOAA SWPC real-time products](https://services.swpc.noaa.gov/json/rtsw/) and the [F10.7 product](https://services.swpc.noaa.gov/json/f107_cm_flux.json) identify the telemetry inputs. |
| Reproducible research practice | Standards, consensus reports, and peer-reviewed methods | The manuscript cites the [National Academies report](https://doi.org/10.17226/25303), [Best Practices for Scientific Computing](https://doi.org/10.1371/journal.pbio.1001745), [Ten Simple Rules](https://doi.org/10.1371/journal.pcbi.1003285), and the [FAIR principles](https://doi.org/10.1038/sdata.2016.18). |
| Software identity and credit | Peer-reviewed software-citation principles plus machine-readable metadata | [FORCE11's Software Citation Principles](https://force11.org/info/software-citation-principles-published-2016/) define importance, credit, unique identification, persistence, accessibility, and specificity; [`CITATION.cff`](../CITATION.cff) carries the current version, author, affiliation, repository, license, and supporting references. |
| Provenance interchange | Normative provenance standards | The evidence bundle is project-specific, while [W3C PROV-O](https://www.w3.org/TR/prov-o/) supplies the vocabulary and provenance-design context. |
| Visualization and DSP foundations | Peer-reviewed software papers or established technical texts | The generated figures cite [Matplotlib](https://doi.org/10.1109/MCSE.2007.55); the limiter cites [Smith's digital audio text](https://ccrma.stanford.edu/~jos/filters/). |
| Design context | Historical or pedagogical sources | [Livio's history of the golden ratio](https://www.penguinrandomhouse.com/books/102878/the-golden-ratio-by-mario-livio/) supplies context; it does not empirically validate the FractiSynth design. |

Every URL in the ledger was fetched and content-checked during the 2026-07-17
scholarship pass. The BibTeX records used by the manuscript are in
[`manuscript/references.bib`](../manuscript/references.bib); repository-level reuse
metadata is in [`CITATION.cff`](../CITATION.cff).

## Software citation and version identity

SynthOBS is both a runnable instrument and a scholarly software object. The
repository URL identifies the continuing project; a version, commit, and release
archive identify the particular object used for a result. This follows the six
software-citation principles of importance, credit and attribution, unique
identification, persistence, accessibility, and specificity ([Smith et al., 2016](https://force11.org/info/software-citation-principles-published-2016/)).
The CFF file is the machine-readable citation surface for the candidate release and
follows the [CFF schema guidance](https://github.com/citation-file-format/citation-file-format/blob/main/schema-guide.md).

For the current candidate, use the following citation until a public tag and archive
record exist:

```text
Friedman, Daniel Ari. SynthOBS & FractiSynth v1.618.0. FractiAI /
Active Inference Institute. https://github.com/docxology/SynthOBS
```

After public release, cite the exact `v1.618.0` tag and, when minted, its archival
DOI. The DOI is intentionally not invented in this sidecar: the release owner must
mint or register it after the public commit exists, then add it to `CITATION.cff`,
the README citation block, and the release notes. A GitHub URL is useful for active
development, but it is not a substitute for a versioned archive when a persistent
scholarly record is required.

When citing a result produced with SynthOBS, record the software version or commit,
OBS and obs-websocket versions, platform, relevant input-product URLs, and the
manifest or capture hashes. Cite NOAA, OBS, and other dependencies for the facts they
establish; cite SynthOBS for the implementation and run protocol.

## Claim-to-evidence protocol

Each material claim should identify four things:

1. the external source, when the claim depends on a fact outside the repository;
2. the local source of truth that implements or records the claim;
3. the automated test or contract that can falsify it; and
4. the rendered artifact or live capture, when the claim crosses the OBS boundary.

The ledger separates deterministic evidence from run observations. For example,
the Python parser tests can establish fail-closed behavior over fixed payloads, but
only the versioned live manifest can establish that one installed OBS binary
rendered a non-black scene and preserved the telemetry strip. This separation is
the same reason the evaluation chapter reports the six live gates independently
from the 1217-test deterministic suite.

## Scope and limits

The references do not claim that φ is a universal broadcasting law, that NOAA
telemetry is a causal driver of visual meaning, or that one OBS run generalizes to
all platforms. Those are outside the evidence boundary. The documented design
propositions are narrower: a pinned cross-language constant, fail-closed state
transitions, explicit telemetry provenance, and versioned captures make this
particular instrument easier to inspect and rerun.

The default provenance strip is an unkeyed integrity mechanism: it detects accidental
corruption and capture mismatch but does not authenticate an adversary. An opt-in
HMAC-SHA-256 verifier accepts a secret from the operator environment without placing
that key in the payload, manifest, or source tree. The machine-readable ledger preserves
the distinction between the two modes.

## Reuse

If you build on SynthOBS, cite the repository through [`CITATION.cff`](../CITATION.cff)
and cite the external source appropriate to the claim you reuse. For a new live
run, retain the OBS version, obs-websocket version, input product URLs, capture
hashes, gate results, and command lines alongside the screenshots.
