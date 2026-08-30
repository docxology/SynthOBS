# workflows/

`verify.yml` — the SynthOBS CI workflow ("SynthOBS verification"). Two jobs:
engine (figures, full pytest suite with 90% coverage gate, package build +
smoke) and native-parser (C/Python behavioral parity via
`tests/test_c_parity_behavioral.py`). Runs on push, PR, and manual dispatch.

Part of the DataTools lane (local-only, never committed). Parent: `../README.md`.
