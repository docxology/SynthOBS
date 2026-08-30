# plugin/

The two OBS integration layers: `synthobs/` (the obspython console script
that imports the tested Python engine) and `fractisynth/` (the native C
libobs transducer plugin with its own shaders and locale data). The Python
engine is the source of truth; the C plugin mirrors selected contracts and is
checked against it. See each subfolder's AGENTS.md.

Part of the DataTools lane (local-only, never committed). Parent: `../README.md`.
