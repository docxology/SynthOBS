"""The SynthOBS Modality Control Decks — 3 modes, an irreducible minimum of 7
console buttons each: exactly 3 common (the operational overlap with standard OBS)
and 4 unique layered-synthesis/tracking capabilities.

Encoded verbatim from the blueprint's three modality matrices (§4):
  - Observatory  — Inbound Alignment Matrix (discovery, capture, sync)
  - Laboratory   — Processing & Synthesis Engine (signal modification, harmonization)
  - Expedition   — Outbound Transmission Deck (encoding, delivery, broadcast)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["Mode", "Button", "Console", "COMMON_BUTTONS"]


class Mode(str, Enum):
    """The three operational decks."""

    OBSERVATORY = "observatory"
    LABORATORY = "laboratory"
    EXPEDITION = "expedition"


@dataclass(frozen=True)
class Button:
    """One hardwired console button."""

    id: str
    label: str
    kind: str  # "common" | "unique"
    description: str
    is_safety: bool = False  # reset / emergency / purge-class control


# The three common buttons — identical id/label/kind across every mode. They bridge
# established OBS capability: Crew Collaboration, Local Recording, Live Broadcasting.
COMMON_BUTTONS: tuple[Button, ...] = (
    Button("CREW_COLLAB_LINK", "Crew Collab Link", "common", "Inbound remote ingestion portal for external crew/observatory streams."),
    Button("RECORD_WAVE_PASS", "Record Wave Pass", "common", "Commit raw/synthesized wavefield data to local disk (φ-optimized sectors)."),
    Button("LAUNCH_STREAM", "Launch Stream", "common", "Establish the outbound handshake and broadcast the active viewport."),
)


_MODE_UNIQUE: dict[Mode, tuple[Button, ...]] = {
    Mode.OBSERVATORY: (
        Button("SWO_SYNC", "SWO Sync", "unique", "Force immediate clock calibration against current sunspot radio flux (e.g. AR4465)."),
        Button("CAP_DEV_ALIGN", "Capture Device Align", "unique", "Cycle/test inbound capture hardware; align raw frames into harmonic bounding boxes."),
        Button("HOLO_GRID_ENGAGE", "Holo Grid Engage", "unique", "Overlay a golden-ratio alignment grid to guide spatial camera composition."),
        Button("OBS_DUMP", "OBS Dump", "unique", "Purge all raw inbound buffer queues and temp frames to clear signal latency.", is_safety=True),
    ),
    Mode.LABORATORY: (
        Button("EGS_SCALE_LOCK", "EGS Scale Lock", "unique", "Enforce the EGS fractal constant across all gain stages and frame-crop variables."),
        Button("TRANS_VIDEO_FLUID", "Transduce Video Fluid", "unique", "Convert static pixel blocks into a fluid, responsive wavefield texture."),
        Button("HARMONIC_COMP", "Harmonic Compressor", "unique", "Route audio through a recursive 1/φ soft-limiting compressor curve."),
        Button("LAB_RESET_ZERO", "Lab Reset Zero", "unique", "Snap all DSP values back to the baseline Goldilocks calibration standard.", is_safety=True),
    ),
    Mode.EXPEDITION: (
        Button("TRANS_WIPE_SEQUENCE", "Transition Wipe Sequence", "unique", "Scene cut via a fractal geometric wipe along an active φ spiral trajectory."),
        Button("BITRATE_THROTTLE", "Bitrate Throttle", "unique", "Scale outbound encoding bitrate live to match network throughput without dropping frames."),
        Button("HULL_INTEG_CHECK", "Hull Integrity Check", "unique", "Real-time diagnostic scan of the transmission: frame drops and latency as 'hull integrity'."),
        Button("EMERGENCY_ABORT", "Emergency Abort", "unique", "Drop the outbound stream, clear ports, set the canvas to an obsidian safe-state.", is_safety=True),
    ),
}


class Console:
    """The SynthOBS console: the global split of modes, buttons, and the persistent
    command line mounted at the base of the interface."""

    COMMAND_LINE_PROMPT = "> "

    def modes(self) -> tuple[Mode, ...]:
        return tuple(Mode)

    def common_buttons(self) -> tuple[Button, ...]:
        return COMMON_BUTTONS

    def unique_buttons(self, mode: Mode) -> tuple[Button, ...]:
        return _MODE_UNIQUE[Mode(mode)]

    def buttons(self, mode: Mode) -> tuple[Button, ...]:
        """All 7 hardwired buttons for ``mode`` — 3 common then 4 unique."""
        return COMMON_BUTTONS + self.unique_buttons(mode)

    def button_ids(self, mode: Mode) -> tuple[str, ...]:
        return tuple(b.id for b in self.buttons(mode))

    def all_button_ids(self) -> list[str]:
        """Every button id across all modes (with the 3 common ids repeated)."""
        ids: list[str] = []
        for m in self.modes():
            ids.extend(self.button_ids(m))
        return ids

    def distinct_button_ids(self) -> set[str]:
        return set(self.all_button_ids())

    def safety_button(self, mode: Mode) -> Button:
        """The reset/emergency/purge-class safety button for ``mode`` (ISC-40)."""
        for b in self.unique_buttons(mode):
            if b.is_safety:
                return b
        raise KeyError(f"no safety button defined for mode {mode!r}")

    def validate(self) -> None:
        """Assert every structural console invariant (raises on violation)."""
        assert len(self.modes()) == 3, "exactly 3 modes required"
        assert len(COMMON_BUTTONS) == 3, "exactly 3 common buttons required"
        common_ids = {b.id for b in COMMON_BUTTONS}
        unique_id_sets = []
        for m in self.modes():
            uniq = self.unique_buttons(m)
            assert len(uniq) == 4, f"mode {m} must have 4 unique buttons"
            assert len(self.buttons(m)) == 7, f"mode {m} must have 7 buttons"
            ids = {b.id for b in uniq}
            assert ids.isdisjoint(common_ids), f"mode {m} unique ids collide with common"
            unique_id_sets.append(ids)
            self.safety_button(m)  # raises if missing
        # unique ids disjoint across modes
        for i in range(len(unique_id_sets)):
            for j in range(i + 1, len(unique_id_sets)):
                assert unique_id_sets[i].isdisjoint(unique_id_sets[j]), "unique ids overlap across modes"
