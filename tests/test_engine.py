"""SynthEngine orchestration tests (ISC-49..54)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from synthobs.console import Mode
from synthobs.engine import SynthEngine
from synthobs.telemetry import SolarTelemetry, TelemetryUnavailable


def _telemetry(flux: float = 130.0, spots: int = 2, source: str = "test") -> SolarTelemetry:
    return SolarTelemetry(
        flux=flux,
        sunspots=spots,
        source=source,
        observed_at=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
    )


def test_update_calibrates() -> None:  # ISC-49
    eng = SynthEngine()
    assert eng.update(_telemetry()) is True
    assert eng.phase_vector is not None
    assert eng.state().is_calibrated


def test_update_unavailable_holds() -> None:  # ISC-50
    eng = SynthEngine()
    eng.update(_telemetry(flux=150.0, spots=3))
    held = eng.phase_vector
    assert eng.update(None) is False  # telemetry dropped
    assert eng.phase_vector == held  # Hold State
    assert eng.state().holding is True


def test_update_invalid_telemetry_holds_last_good_vector() -> None:
    eng = SynthEngine()
    eng.update(_telemetry(flux=150.0, spots=3))
    held = eng.phase_vector

    assert eng.update(_telemetry(flux=0.0, spots=3, source="invalid")) is False
    assert eng.phase_vector == held
    assert eng.state().holding is True


def test_layout_fractions() -> None:  # ISC-51
    eng = SynthEngine()
    vp = eng.layout(1920, 1080)
    assert vp.tiles_exactly()
    assert abs(vp.primary_fraction() - 0.618) < 0.002


def test_modulate_after_calibration() -> None:  # ISC-52
    eng = SynthEngine()
    eng.update(_telemetry())
    cw, ch = eng.modulate_video(1920, 1080)
    assert cw == 1187 and ch == 667  # round(1920/φ), round(1080/φ)
    out = eng.modulate_audio([0.0, 0.5, 2.0], threshold=1.0)
    assert all(abs(s) <= 1.0 for s in out)


def test_refuses_modulation_before_calibration() -> None:  # ISC-54
    eng = SynthEngine()
    with pytest.raises(TelemetryUnavailable):
        eng.modulate_video(1920, 1080)
    with pytest.raises(TelemetryUnavailable):
        eng.modulate_audio([0.1, 0.2])


def test_demo_mode_allows_modulation() -> None:  # ISC-54 (demo escape)
    eng = SynthEngine(demo_mode=True)
    cw, ch = eng.modulate_video(1000, 1000)
    assert cw == 618 and ch == 618


def test_mode_switching_constrained() -> None:  # ISC-53
    eng = SynthEngine(mode=Mode.OBSERVATORY)
    assert eng.mode == Mode.OBSERVATORY
    assert eng.switch_mode(Mode.LABORATORY) == Mode.LABORATORY
    assert eng.switch_mode("expedition") == Mode.EXPEDITION
    with pytest.raises(ValueError):
        eng.switch_mode("warp_core")  # not a valid deck


def test_update_from_fetch_holds_on_unavailable() -> None:
    eng = SynthEngine()
    eng.update(_telemetry())
    held = eng.phase_vector

    def failing_fetch():
        raise TelemetryUnavailable("connection dropped")

    assert eng.update_from_fetch(failing_fetch) is False
    assert eng.phase_vector == held

    def good_fetch():
        return _telemetry(flux=200.0, spots=4)

    assert eng.update_from_fetch(good_fetch) is True
    assert eng.phase_vector != held


def test_console_validated_on_construction() -> None:
    eng = SynthEngine()
    assert len(eng.console.buttons(Mode.OBSERVATORY)) == 7
