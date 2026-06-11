"""The global command-line grammar.

A persistent terminal line is mounted at the base of the SynthOBS interface and
remains in active focus; at any moment the operator can bypass the button console
to input scripting, macros, or routing overrides. This module is the parser for
that grammar — a clean, deterministic syntax (blueprint §7):

    /mode --observatory | --lab | --ship
    /transducer bind <source> --ratio=1.618034
    /swo calibrate --flux=130 --spots=3 --target=AR4465

Unknown verbs and invalid values fail closed (raise :class:`CommandError`) — the
terminal never silently no-ops.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from .console import Mode

__all__ = [
    "Command",
    "ModeCommand",
    "BindCommand",
    "CalibrateCommand",
    "CommandError",
    "parse",
]


class CommandError(ValueError):
    """Raised on an unknown verb, malformed argument, or out-of-range value."""


@dataclass(frozen=True)
class Command:
    """Base class for parsed commands."""

    raw: str


@dataclass(frozen=True)
class ModeCommand(Command):
    target: Mode = Mode.OBSERVATORY


@dataclass(frozen=True)
class BindCommand(Command):
    source: str = ""
    ratio: float = 0.0


@dataclass(frozen=True)
class CalibrateCommand(Command):
    flux: float = 0.0
    spots: int = 0
    target: str | None = None


_MODE_FLAGS = {
    "--observatory": Mode.OBSERVATORY,
    "--lab": Mode.LABORATORY,
    "--laboratory": Mode.LABORATORY,
    "--ship": Mode.EXPEDITION,
    "--expedition": Mode.EXPEDITION,
}


def _split_flags(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    """Partition tokens into positionals and ``--key=value`` / ``--flag`` flags."""
    positionals: list[str] = []
    flags: dict[str, str] = {}
    for tok in tokens:
        if tok.startswith("--"):
            if "=" in tok:
                key, _, val = tok.partition("=")
                flags[key] = val
            else:
                flags[tok] = ""
        else:
            positionals.append(tok)
    return positionals, flags


def _parse_mode(raw: str, positionals: list[str], flags: dict[str, str]) -> ModeCommand:
    for flag in flags:
        if flag in _MODE_FLAGS:
            return ModeCommand(raw=raw, target=_MODE_FLAGS[flag])
    # also accept bare positional like "/mode observatory"
    for pos in positionals:
        candidate = f"--{pos}"
        if candidate in _MODE_FLAGS:
            return ModeCommand(raw=raw, target=_MODE_FLAGS[candidate])
    raise CommandError(f"/mode requires one of {sorted(_MODE_FLAGS)}; got {flags or positionals}")


def _parse_transducer(raw: str, positionals: list[str], flags: dict[str, str]) -> BindCommand:
    if not positionals or positionals[0] != "bind":
        raise CommandError("/transducer expects 'bind <source> --ratio=<f>'")
    if len(positionals) < 2:
        raise CommandError("/transducer bind requires a <source>")
    source = positionals[1]
    if "--ratio" not in flags:
        raise CommandError("/transducer bind requires --ratio=<float>")
    try:
        ratio = float(flags["--ratio"])
    except ValueError as exc:
        raise CommandError(f"--ratio must be a float, got {flags['--ratio']!r}") from exc
    if ratio <= 0:
        raise CommandError(f"--ratio must be positive, got {ratio}")
    return BindCommand(raw=raw, source=source, ratio=ratio)


def _parse_swo(raw: str, positionals: list[str], flags: dict[str, str]) -> CalibrateCommand:
    if not positionals or positionals[0] != "calibrate":
        raise CommandError("/swo expects 'calibrate --flux=<f> --spots=<i> [--target=<id>]'")
    if "--flux" not in flags or "--spots" not in flags:
        raise CommandError("/swo calibrate requires --flux and --spots")
    try:
        flux = float(flags["--flux"])
        spots = int(flags["--spots"])
    except ValueError as exc:
        raise CommandError(f"invalid numeric flag for /swo calibrate: {flags!r}") from exc
    # Fail closed on non-physical telemetry (mirrors SWO Hold State).
    if flux <= 0:
        raise CommandError(f"--flux must be positive, got {flux}")
    if spots <= 0:
        raise CommandError(f"--spots must be positive, got {spots}")
    target = flags.get("--target") or None
    return CalibrateCommand(raw=raw, flux=flux, spots=spots, target=target)


_VERBS = {
    "/mode": _parse_mode,
    "/transducer": _parse_transducer,
    "/swo": _parse_swo,
}


def parse(line: str) -> Command:
    """Parse one command line into a typed :class:`Command` (ISC-42..48).

    Raises :class:`CommandError` on an empty line, unknown verb, or invalid args.
    """
    if not line or not line.strip():
        raise CommandError("empty command line")
    try:
        tokens = shlex.split(line.strip())
    except ValueError as exc:
        raise CommandError(f"unparseable command line: {line!r}") from exc
    verb, rest = tokens[0], tokens[1:]
    if verb not in _VERBS:
        raise CommandError(f"unknown command verb: {verb!r} (known: {sorted(_VERBS)})")
    positionals, flags = _split_flags(rest)
    return _VERBS[verb](line.strip(), positionals, flags)
