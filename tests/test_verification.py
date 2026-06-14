"""Pure live-verification oracle tests."""

from __future__ import annotations

import pytest

from synthobs.verification import (
    GateResult,
    audio_meter_roi,
    score_audio_meter_delta,
    score_roi_delta,
)


def _rgba(width: int, height: int, color: tuple[int, int, int, int]) -> bytearray:
    return bytearray(color * (width * height))


def _paint(
    image: bytearray,
    width: int,
    channels: int,
    roi: tuple[int, int, int, int],
    color: tuple[int, int, int, int],
) -> None:
    x0, y0, rw, rh = roi
    for y in range(y0, y0 + rh):
        for x in range(x0, x0 + rw):
            base = (y * width + x) * channels
            image[base : base + channels] = bytes(color[:channels])


def test_audio_meter_roi_matches_shader_bottom_band() -> None:
    assert audio_meter_roi(1280, 720) == (0, 687, 1280, 33)
    assert audio_meter_roi(1, 1) == (0, 0, 1, 1)


def test_audio_meter_delta_identical_images_fails() -> None:
    img = bytes(_rgba(64, 64, (20, 20, 20, 255)))

    delta = score_audio_meter_delta(img, img, 64, 64, threshold=1.0)

    assert delta.passed is False
    assert delta.mean_abs_delta == 0.0
    assert delta.max_abs_delta == 0


def test_audio_meter_delta_passes_for_controlled_meter_change() -> None:
    width, height = 64, 64
    before = _rgba(width, height, (20, 20, 20, 255))
    after = bytearray(before)
    _paint(after, width, 4, audio_meter_roi(width, height), (90, 190, 180, 255))

    delta = score_audio_meter_delta(bytes(before), bytes(after), width, height, threshold=8.0)

    assert delta.passed is True
    assert delta.compared_pixels == width * (height - int(height * 0.955))
    assert delta.mean_abs_delta > 8.0


def test_audio_meter_delta_ignores_off_roi_noise() -> None:
    width, height = 64, 64
    before = _rgba(width, height, (20, 20, 20, 255))
    after = bytearray(before)
    _paint(after, width, 4, (0, 0, width, 20), (255, 255, 255, 255))

    delta = score_audio_meter_delta(bytes(before), bytes(after), width, height, threshold=1.0)

    assert delta.passed is False
    assert delta.mean_abs_delta == 0.0


def test_roi_delta_rejects_bad_buffers_and_roi() -> None:
    img = bytes(_rgba(8, 8, (0, 0, 0, 255)))
    with pytest.raises(ValueError, match="expected"):
        score_roi_delta(img[:-1], img, 8, 8, roi=(0, 0, 8, 8), threshold=1.0)
    with pytest.raises(ValueError, match="outside"):
        score_roi_delta(img, img, 8, 8, roi=(7, 7, 2, 2), threshold=1.0)
    with pytest.raises(ValueError, match="threshold"):
        score_roi_delta(img, img, 8, 8, roi=(0, 0, 8, 8), threshold=float("nan"))


def test_gate_result_manifest_shape_and_skip_semantics() -> None:
    passed = GateResult.passed("captured", mean_abs_delta=12.5)
    skipped = GateResult.skipped("OBS websocket unavailable", url="ws://localhost:4455")

    assert passed.to_dict() == {
        "status": "pass",
        "reason": "captured",
        "metrics": {"mean_abs_delta": 12.5},
    }
    assert skipped.to_dict()["status"] == "skip"


def test_gate_result_fails_closed_on_ambiguous_status() -> None:
    with pytest.raises(ValueError, match="gate status"):
        GateResult("maybe", "not a contract")
    with pytest.raises(ValueError, match="reason"):
        GateResult.skipped(" ")
