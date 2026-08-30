# src/

Native C/C++ source of the FractiSynth plugin: `fractisynth.c` (the libobs
core — video/audio/inspector filters + the generated console source, SWO
calibration struct, and the libcurl telemetry thread), `fractisynth_dock.cpp`
(the Qt dock controls), plus local headers: `rtsw_parser.h` (NOAA rtsw
feed parser), `sha256.h` (provenance hashing), `text8x8.h` (8x8 bitmap font
for HUD rendering).

Part of the DataTools lane (local-only, never committed). Parent: `../README.md`.
