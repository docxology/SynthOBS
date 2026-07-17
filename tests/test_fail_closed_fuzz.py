"""Fail-closed fuzz harness — the project's #1 principle, enforced as one battery.

SynthOBS's central design rule is *fail closed*: invalid, stale, zeroed, or
non-finite telemetry must never propagate as a verified value — the system holds
its last good vector or refuses outright. A 2026-06-12 cross-vendor audit found
that several boundary ingestion functions enforced this with a bare ``x <= 0.0``
guard, which silently accepts ``NaN``/``Inf`` (every comparison against NaN is
False, and ``json.loads`` accepts the ``NaN``/``Infinity`` literals by default).
Such holes are fixed as found; this harness exists so every external numeric
ingestion boundary *registered below* is swept by one adversarial battery and the
class of defect cannot silently return for a covered boundary. Coverage is only as
complete as ``BOUNDARIES`` — a 2026-06-22 cross-vendor audit found that the
``sunspots`` field of ``telemetry_from_payload`` (its ``int()`` conversion raised an
uncaught ``OverflowError`` on a JSON-legal ``Infinity``) and the ``parse_noaa_kp_index``
parser were both ingestion boundaries missing from this list; both are now registered.

Each boundary is registered with its fail-closed contract (``raises`` an allowed
exception, or returns a ``sentinel``). Adding a new external-ingestion function is
one ``Boundary(...)`` entry — that is the point: the contract is enumerable and
extensible, not scattered across ad-hoc per-function tests.

Every call uses real values and the real functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import pytest

from synthobs import commands, gateway, interaction, telemetry
from synthobs.commands import CommandError
from synthobs.interaction import TargetAction
from synthobs.provenance import ProvenanceError, TelemetryRecord
from synthobs.swo import SolarWavefieldOscillator
from synthobs.telemetry import TelemetryUnavailable

# The adversarial scalar battery. Every value here must be refused by every
# numeric boundary that ingests an external "should be a positive real" quantity.
NONFINITE: list[float] = [float("nan"), float("inf"), float("-inf")]


@dataclass
class Boundary:
    """One external-ingestion function and how it fails closed on a bad scalar."""

    name: str
    call: Callable[[float], Any]
    """Inject the bad scalar and invoke the boundary. May raise."""
    raises: tuple[type[BaseException], ...] = ()
    """Exception types that count as fail-closed (refusal)."""
    sentinel: Callable[[Any], bool] | None = None
    """Or: a predicate on the return value that is True iff it failed closed."""


# IMPORTANT: pass already-parsed Python objects, NOT JSON strings. `json.loads`
# only accepts the capitalized NaN/Infinity literals and rejects lowercase
# nan/inf — so building the payload with %r (which yields 'nan'/'inf') would make
# the parser refuse at the JSON-parse stage, NOT via the math.isfinite guard under
# test, and the row would pass even if the fix were reverted (green-by-construction).
# Handing the float object directly routes straight to the validation guard.
def _telemetry_payload(flux: float) -> Any:
    return {"flux": flux, "sunspots": 3, "time_tag": "2026-06-10T11:30:00Z"}


def _telemetry_sunspots(spots: float) -> Any:
    # The bad scalar lands in the SUNSPOTS field (flux fixed-valid). This is the
    # boundary the battery previously never fuzzed: int(float('inf')) raised an
    # uncaught OverflowError instead of failing closed (telemetry.py, fixed 2026-06-22).
    return {"flux": 130.4, "sunspots": spots, "time_tag": "2026-06-10T11:30:00Z"}


def _kp(kp: float) -> Any:
    return [{"time_tag": "2026-06-10T11:59:00", "estimated_kp": kp}]


def _f107(flux: float) -> Any:
    return [{"time_tag": "2026-06-10T00:00:00", "flux": flux}]


def _solarwind(speed: float) -> Any:
    return [
        {
            "time_tag": "2026-06-10T11:59:00Z",
            "active": True,
            "proton_density": 5.0,
            "proton_speed": speed,
            "proton_temperature": 1.0e5,
        },
    ]


def _plasma_series(density: float) -> Any:
    # Finite positive speed, but the bad scalar lands in density — the whole row
    # must be dropped, leaving no valid rows → fail closed (raises).
    return [{
        "time_tag": "2026-06-10T11:59:00Z",
        "active": True,
        "proton_density": density,
        "proton_speed": 420.0,
        "proton_temperature": 1.0e5,
    }]


def _xray_series(flux: float) -> Any:
    return [{"energy": "0.1-0.8nm", "flux": flux}]


def _calibrate(flux: float) -> bool:
    swo = SolarWavefieldOscillator()
    # A finite-but-extreme flux whose flux*phi overflows must also fail closed.
    return swo.calibrate(flux, 3)


def _provenance(flux: float) -> Any:
    return TelemetryRecord(
        flux=flux,
        sunspots=3,
        solar_wind_kms=400.0,
        lock_strength=0.5,
        phase_bias_rad=1.0,
        observed_unix=0,
    )


def _resolve(coord: float) -> Any:
    # Put the bad value in x; a NaN/Inf coordinate must fail closed to NONE.
    return interaction.resolve_target_action(coord, 10.0, 1000, 800, layer_count=3)


def _command_flux(flux: float) -> Any:
    return commands.parse(f"/swo calibrate --flux={flux} --spots=3")


def _command_ratio(ratio: float) -> Any:
    return commands.parse(f"/transducer bind cam --ratio={ratio}")


BOUNDARIES: list[Boundary] = [
    Boundary("telemetry_from_payload", lambda f: telemetry.telemetry_from_payload(_telemetry_payload(f)), raises=(TelemetryUnavailable,)),
    Boundary("telemetry_from_payload[sunspots]", lambda f: telemetry.telemetry_from_payload(_telemetry_sunspots(f)), raises=(TelemetryUnavailable,)),
    Boundary("parse_noaa_kp_index", lambda f: telemetry.parse_noaa_kp_index(_kp(f)), raises=(TelemetryUnavailable,)),
    Boundary("parse_noaa_f107_flux", lambda f: telemetry.parse_noaa_f107_flux(_f107(f)), raises=(TelemetryUnavailable,)),
    Boundary("parse_noaa_solar_wind", lambda f: telemetry.parse_noaa_solar_wind(_solarwind(f)), raises=(TelemetryUnavailable,)),
    Boundary("parse_noaa_plasma_series", lambda f: telemetry.parse_noaa_plasma_series(_plasma_series(f)), raises=(TelemetryUnavailable,)),
    Boundary("parse_noaa_xray_flux", lambda f: telemetry.parse_noaa_xray_flux(_xray_series(f)), raises=(TelemetryUnavailable,)),
    Boundary("gateway_filter", lambda f: gateway.gateway_filter(f), raises=(ValueError,)),
    Boundary("swo.calibrate", _calibrate, sentinel=lambda r: r is False),
    Boundary("provenance.TelemetryRecord", _provenance, raises=(ProvenanceError,)),
    Boundary("resolve_target_action", _resolve, sentinel=lambda r: r.action is TargetAction.NONE),
    Boundary("commands.parse /swo flux", _command_flux, raises=(CommandError,)),
    Boundary("commands.parse /transducer ratio", _command_ratio, raises=(CommandError,)),
]


def _assert_fails_closed(b: Boundary, bad: float) -> None:
    try:
        result = b.call(bad)
    except b.raises:
        return  # refused by raising — fail-closed
    except Exception as exc:  # noqa: BLE001 — any other exception is a leak, not a refusal
        pytest.fail(f"{b.name}({bad!r}) leaked {type(exc).__name__}: {exc} (expected {b.raises})")
    else:
        if b.sentinel is not None and b.sentinel(result):
            return  # returned the held/none/False sentinel — fail-closed
        pytest.fail(
            f"{b.name}({bad!r}) returned {result!r} — a non-finite/adversarial input "
            f"was accepted as VALID (fail-closed contract violated)"
        )


@pytest.mark.parametrize("boundary", BOUNDARIES, ids=lambda b: b.name)
@pytest.mark.parametrize("bad", NONFINITE, ids=lambda v: repr(v))
def test_boundary_fails_closed_on_nonfinite(boundary: Boundary, bad: float) -> None:
    _assert_fails_closed(boundary, bad)


def test_swo_overflow_vector_fails_closed() -> None:
    # A finite flux is legitimate at the ingestion boundaries (they validate
    # finiteness, not downstream products). Overflow only occurs where flux*phi is
    # computed: swo.calibrate with spots=1 → 1.5e308*phi = +Inf. The SWO must refuse
    # (the isfinite-on-vector guard), holding the last vector — this is the path the
    # obspython adapter's fail-closed bool depends on (SYNTHOBS-CONSOLE-1).
    swo = SolarWavefieldOscillator()
    assert swo.calibrate(1.5e308, 1) is False
    assert swo.system_phase_vector is None


def test_battery_is_actually_adversarial() -> None:
    # Guard against a vacuous battery: prove the happy path is NOT refused, so the
    # fail-closed assertions above are meaningful (negative control).
    assert telemetry.parse_noaa_f107_flux(_f107(130.4))[0] == pytest.approx(130.4)
    assert _calibrate(130.0) is True
    assert math.isfinite(gateway.gateway_filter(400.0).lock_strength)


def test_sunspots_and_kp_boundaries_have_positive_controls() -> None:
    # Positive controls for the two boundaries added 2026-06-22: each must ACCEPT
    # good input, so their fail-closed rows above are meaningful, not vacuously-raising.
    from datetime import datetime, timezone

    rec = telemetry.telemetry_from_payload(
        _telemetry_sunspots(7),
        now=datetime(2026, 6, 10, 11, 30, 5, tzinfo=timezone.utc),
    )
    assert rec.sunspots == 7
    assert telemetry.parse_noaa_kp_index(_kp(2.0)) == [2.0]


def test_sunspots_infinity_is_load_bearing() -> None:
    # Anti-regression for the OverflowError leak (2026-06-22): int(float('inf'))
    # raises OverflowError, which was NOT in telemetry.py's caught tuple, so an
    # Infinity sunspots crashed ingestion instead of failing closed into Hold State.
    # The inf/-inf cases are the load-bearing ones for THIS fix (int(nan) already
    # raised ValueError pre-fix); nan is kept to assert the broader fail-closed contract.
    # Reverting the `OverflowError` add to telemetry.py makes the inf/-inf cases fail.
    for bad in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(TelemetryUnavailable):
            telemetry.telemetry_from_payload(_telemetry_sunspots(bad))


def test_json_boundaries_refuse_via_finiteness_not_json_parse() -> None:
    # Anti-regression for the green-by-construction trap (Forge 2026-06-12): the
    # parsers accept a parsed object directly, so a NaN/Inf float reaches the
    # math.isfinite guard rather than being rejected at the json.loads stage. Prove
    # the refusal REASON names finiteness, so a future revert to %r-stringified JSON
    # (which json.loads rejects for unrelated reasons) can't silently re-vacuum this.
    with pytest.raises(TelemetryUnavailable, match="finite"):
        telemetry.telemetry_from_payload(_telemetry_payload(float("nan")))
    with pytest.raises(TelemetryUnavailable, match="finite"):
        telemetry.parse_noaa_f107_flux(_f107(float("inf")))
    with pytest.raises(TelemetryUnavailable, match="finite"):
        telemetry.parse_noaa_solar_wind(_solarwind(float("inf")))


def test_xray_plus_inf_and_plasma_nan_density_are_load_bearing() -> None:
    # H1/H2 regression: +Inf passes `> 0.0` and NaN density passes `s > 0.0`, so
    # these cells are refused ONLY by the new finiteness guards — they would have
    # leaked into the X-ray graph / plasma sparkline before the fix.
    with pytest.raises(TelemetryUnavailable):
        telemetry.parse_noaa_xray_flux(_xray_series(float("inf")))
    with pytest.raises(TelemetryUnavailable):
        telemetry.parse_noaa_plasma_series(_plasma_series(float("nan")))
    # and a clean series still parses (the guard didn't over-reject)
    good = telemetry.parse_noaa_plasma_series(
        [{"time_tag": "2026-06-10T11:59:00Z", "active": True, "proton_density": 5.0, "proton_speed": 420.0, "proton_temperature": 1.0e5}],
        max_age_s=10**9,
    )
    assert good[1] == [420.0]
