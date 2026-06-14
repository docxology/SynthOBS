"""Console model (ISC-33..41) and command grammar (ISC-42..48) tests."""

from __future__ import annotations

import pytest
from synthobs.commands import (
    BindCommand,
    CalibrateCommand,
    CommandError,
    ModeCommand,
    parse,
)
from synthobs.console import COMMON_BUTTONS, Console, Mode


@pytest.fixture
def console() -> Console:
    return Console()


# --- console structure ---------------------------------------------------
def test_three_modes(console: Console) -> None:  # ISC-33
    assert set(console.modes()) == {Mode.OBSERVATORY, Mode.LABORATORY, Mode.EXPEDITION}
    assert len(console.modes()) == 3


@pytest.mark.parametrize("mode", list(Mode))
def test_seven_buttons(console: Console, mode: Mode) -> None:  # ISC-34
    assert len(console.buttons(mode)) == 7


@pytest.mark.parametrize("mode", list(Mode))
def test_three_common_four_unique(console: Console, mode: Mode) -> None:  # ISC-35, ISC-36
    btns = console.buttons(mode)
    assert sum(1 for b in btns if b.kind == "common") == 3
    assert sum(1 for b in btns if b.kind == "unique") == 4


def test_common_identical_across_modes(console: Console) -> None:  # ISC-37
    expected = {"CREW_COLLAB_LINK", "RECORD_WAVE_PASS", "LAUNCH_STREAM"}
    assert {b.id for b in COMMON_BUTTONS} == expected
    for mode in console.modes():
        common = {b.id for b in console.buttons(mode) if b.kind == "common"}
        assert common == expected


def test_unique_disjoint_across_modes(console: Console) -> None:  # ISC-38
    uniq = [set(b.id for b in console.unique_buttons(m)) for m in console.modes()]
    assert uniq[0].isdisjoint(uniq[1])
    assert uniq[0].isdisjoint(uniq[2])
    assert uniq[1].isdisjoint(uniq[2])


def test_every_button_well_formed(console: Console) -> None:  # ISC-39
    for mode in console.modes():
        for b in console.buttons(mode):
            assert b.id and b.label and b.description
            assert b.kind in {"common", "unique"}


@pytest.mark.parametrize("mode", list(Mode))
def test_safety_button_present(console: Console, mode: Mode) -> None:  # ISC-40
    b = console.safety_button(mode)
    assert b.is_safety is True


def test_id_counts(console: Console) -> None:  # ISC-41
    assert len(console.all_button_ids()) == 21
    assert len(console.distinct_button_ids()) == 15  # 3 common shared + 12 unique


def test_validate_passes(console: Console) -> None:
    console.validate()  # raises on any structural violation


def test_common_buttons_accessor(console: Console) -> None:
    assert console.common_buttons() == COMMON_BUTTONS


# --- command grammar -----------------------------------------------------
@pytest.mark.parametrize(
    "line,mode",
    [
        ("/mode --observatory", Mode.OBSERVATORY),
        ("/mode --lab", Mode.LABORATORY),
        ("/mode --laboratory", Mode.LABORATORY),
        ("/mode --ship", Mode.EXPEDITION),
        ("/mode --expedition", Mode.EXPEDITION),
        ("/mode observatory", Mode.OBSERVATORY),
    ],
)
def test_parse_mode(line: str, mode: Mode) -> None:  # ISC-42, ISC-43
    cmd = parse(line)
    assert isinstance(cmd, ModeCommand)
    assert cmd.target == mode


def test_parse_transducer_bind() -> None:  # ISC-44
    cmd = parse("/transducer bind source_cam_01 --ratio=1.618034")
    assert isinstance(cmd, BindCommand)
    assert cmd.source == "source_cam_01"
    assert cmd.ratio == pytest.approx(1.618034)


def test_parse_swo_calibrate() -> None:  # ISC-45, ISC-48
    cmd = parse("/swo calibrate --flux=130 --spots=3 --target=AR4465")
    assert isinstance(cmd, CalibrateCommand)
    assert cmd.flux == 130.0 and isinstance(cmd.flux, float)
    assert cmd.spots == 3 and isinstance(cmd.spots, int)
    assert cmd.target == "AR4465"


def test_swo_calibrate_optional_target() -> None:
    cmd = parse("/swo calibrate --flux=99.5 --spots=2")
    assert isinstance(cmd, CalibrateCommand)
    assert cmd.target is None


@pytest.mark.parametrize(
    "line",
    [
        "/unknown --foo",
        "/MODE --observatory",  # case sensitive verb
        "",
        "   ",
    ],
)
def test_unknown_or_empty_fails_closed(line: str) -> None:  # ISC-46
    with pytest.raises(CommandError):
        parse(line)


@pytest.mark.parametrize(
    "line",
    [
        "/swo calibrate --flux=-1 --spots=3",  # ISC-47
        "/swo calibrate --flux=130 --spots=0",
        "/swo calibrate --flux=abc --spots=3",
        "/swo calibrate --spots=3",  # missing flux
        "/mode",  # missing target
        "/transducer bind cam_01",  # missing ratio
        "/transducer bind --ratio=1.6",  # missing source
        "/transducer wiggle",  # bad subcommand
        "/transducer bind cam --ratio=0",  # non-positive ratio
        "/transducer bind cam --ratio=NaN",  # non-finite ratio
        "/transducer bind cam --ratio=Infinity",  # non-finite ratio
        "/swo calibrate --flux=NaN --spots=3",  # non-finite flux
        "/swo calibrate --flux=Infinity --spots=3",  # non-finite flux
    ],
)
def test_invalid_args_fail_closed(line: str) -> None:  # ISC-46, ISC-47
    with pytest.raises(CommandError):
        parse(line)


def test_unparseable_quotes_fail_closed() -> None:
    with pytest.raises(CommandError, match="unparseable"):
        parse('/mode "unterminated')


def test_transducer_ratio_must_be_numeric() -> None:
    with pytest.raises(CommandError, match="ratio must be a float"):
        parse("/transducer bind cam --ratio=not-a-number")


# --- obspython adapter fail-closed regression (SYNTHOBS-CONSOLE-1) ------------
def _load_console_module():
    """Import the plugin's obspython adapter by path (it lives outside the package)."""
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "plugin" / "synthobs" / "synthobs_console.py"
    spec = importlib.util.spec_from_file_location("synthobs_console_under_test", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_console_calibrate_happy_path_reports_vector() -> None:
    mod = _load_console_module()
    out = mod.apply_command("/swo calibrate --flux=130 --spots=3")
    assert out.startswith("SWO calibrated: phase_vector=")


def test_console_calibrate_overflow_fails_closed_not_crash() -> None:
    # A finite-but-extreme flux passes the grammar parser, but flux*phi overflows to
    # inf, so the SWO refuses it (update→False, phase_vector→None). The adapter must
    # honor that bool and return a held message, NOT crash formatting None as :.4f.
    mod = _load_console_module()
    out = mod.apply_command("/swo calibrate --flux=1.5e308 --spots=1")
    assert "held" in out.lower()
    assert "refused" in out.lower()
