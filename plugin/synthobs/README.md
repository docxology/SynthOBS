# synthobs/

The obspython console bridge for OBS. `synthobs_console.py` is loaded in OBS
via **Tools → Scripts → +**; it imports the tested engine (`src/synthobs`) —
including `apply_command` for the `/mode`, `/transducer`, `/swo`,
`/dashboard` grammar — rather than duplicating console logic, and exposes
deterministic dashboard plan/build dry-runs outside OBS. Install/usage
details: `../../docs/usage.md` and `../../docs/command-grammar.md`.

Part of the DataTools lane (local-only, never committed). Parent: `../README.md`.
