"""The Goldilocks Layout Matrix — golden-ratio viewport self-assembly.

SynthOBS replaces manual canvas configuration with a recursive golden-ratio
layout engine. The active stream output (the *primary object of attention*) is
allocated ``1/φ ≈ 61.8%`` of the canvas; the control & telemetry deck takes the
remaining ``38.2%``. Every split here is a pure function — zero I/O — and the
native adapter is checked against the resulting layout contract.

Integer-exactness rule: a golden split of an integer canvas dimension always
partitions it with **no lost pixels** — ``major + minor == total`` exactly — by
rounding the major part and giving the remainder to the minor part.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import INV_PHI, PHI

__all__ = [
    "Region",
    "Viewport",
    "golden_split",
    "recursive_subdivision",
    "assemble_viewport",
    "golden_spiral_points",
]


def golden_split(total: int) -> tuple[int, int]:
    """Partition ``total`` into a golden (major, minor) pair with no lost units.

    ``major ≈ total / φ`` (≈61.8%); ``minor = total − major`` (≈38.2%). The
    remainder is absorbed by the minor part so ``major + minor == total`` exactly
    for every non-negative integer ``total`` (ISC-3, ISC-4).
    """
    if total < 0:
        raise ValueError(f"golden_split requires total >= 0, got {total}")
    major = int(round(total * INV_PHI))
    # Clamp so neither part is negative for tiny totals.
    major = max(0, min(major, total))
    minor = total - major
    return major, minor


@dataclass(frozen=True)
class Region:
    """An axis-aligned rectangle in canvas pixels."""

    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return self.width * self.height

    def overlaps(self, other: "Region") -> bool:
        return not (
            self.x + self.width <= other.x
            or other.x + other.width <= self.x
            or self.y + self.height <= other.y
            or other.y + other.height <= self.y
        )


@dataclass(frozen=True)
class Viewport:
    """The assembled SynthOBS canvas: a primary output deck, a console deck, and a
    telemetry strip — all tiling the canvas exactly with no overlap or gaps."""

    canvas: Region
    primary: Region
    console: Region
    telemetry: Region

    def regions(self) -> tuple[Region, Region, Region]:
        return (self.primary, self.console, self.telemetry)

    def tiles_exactly(self) -> bool:
        """True iff the three decks partition the canvas with no overlap or gap."""
        if self.canvas.width < 0 or self.canvas.height < 0:
            return False
        for region in self.regions():
            if (
                region.width < 0
                or region.height < 0
                or region.x < self.canvas.x
                or region.y < self.canvas.y
                or region.x + region.width > self.canvas.x + self.canvas.width
                or region.y + region.height > self.canvas.y + self.canvas.height
            ):
                return False
        total = sum(r.area for r in self.regions())
        if total != self.canvas.area:
            return False
        a, b, c = self.regions()
        return not (a.overlaps(b) or a.overlaps(c) or b.overlaps(c))

    def primary_fraction(self) -> float:
        return self.primary.area / self.canvas.area


def recursive_subdivision(total: int, depth: int) -> list[int]:
    """Recursively golden-split ``total`` ``depth`` times along one axis.

    Returns a list of ``depth`` sizes whose sum is exactly ``total`` (ISC-5). Each
    successive boundary sits at the golden ratio of the remaining span, so the
    ratio of consecutive cuts approaches ``1/φ`` (ISC-6).
    """
    if depth < 1:
        raise ValueError(f"depth must be >= 1, got {depth}")
    sizes: list[int] = []
    remaining = total
    for _ in range(depth - 1):
        major, minor = golden_split(remaining)
        sizes.append(major)
        remaining = minor
    sizes.append(remaining)
    return sizes


def assemble_viewport(width: int, height: int) -> Viewport:
    """Self-assemble the canvas into primary (61.8% width) + console/telemetry.

    The canvas is split horizontally: the primary output deck takes the major
    (left, ≈61.8%) column; the right column is split vertically into the console
    deck (major, ≈61.8% height — the 7 hardwired buttons) and the live telemetry
    strip (minor, ≈38.2% — the SWO tracking graphs). Tiles exactly (ISC-7, ISC-8).
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"canvas dims must be positive, got {width}x{height}")
    canvas = Region(0, 0, width, height)
    primary_w, deck_w = golden_split(width)
    console_h, telemetry_h = golden_split(height)
    primary = Region(0, 0, primary_w, height)
    console = Region(primary_w, 0, deck_w, console_h)
    telemetry = Region(primary_w, console_h, deck_w, telemetry_h)
    return Viewport(canvas=canvas, primary=primary, console=console, telemetry=telemetry)


def golden_spiral_points(n: int, *, a: float = 1.0, start_theta: float = 0.0) -> list[tuple[float, float]]:
    """Sample ``n`` points on a logarithmic (golden) spiral.

    The spiral grows by a factor of ``φ`` every quarter-turn (π/2 radians) — the
    classic golden-spiral growth used by the ``TRANS_WIPE_SEQUENCE`` fractal wipe.
    Polar form ``r = a · φ^(2θ/π)`` (ISC-9).
    """
    if n < 0:
        raise ValueError(f"n must be >= 0, got {n}")
    if not math.isfinite(a):
        raise ValueError(f"a must be finite, got {a}")
    if not math.isfinite(start_theta):
        raise ValueError(f"start_theta must be finite, got {start_theta}")
    # b such that r multiplies by φ each quarter turn: r = a·e^{bθ}, e^{b·(π/2)} = φ
    b = math.log(PHI) / (math.pi / 2.0)
    pts: list[tuple[float, float]] = []
    for i in range(n):
        theta = start_theta + i * (math.pi / 2.0) / 4.0  # 4 samples per quarter-turn
        r = a * math.exp(b * theta)
        pts.append((r * math.cos(theta), r * math.sin(theta)))
    return pts
