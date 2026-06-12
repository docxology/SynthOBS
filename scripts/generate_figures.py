#!/usr/bin/env python3
"""Generate SynthOBS manuscript figures (thin orchestrator).

All geometry/telemetry/DSP comes from the tested engine in ``src/synthobs``; this
script only does I/O and visualization (matplotlib, headless Agg). It prints each
output path to stdout for manifest collection.

Figures:
  1. goldilocks_layout.png — the 61.8% / 38.2% viewport self-assembly.
  2. golden_spiral.png      — the φ spiral used by TRANS_WIPE_SEQUENCE.
  3. swo_calibration.png    — phase_vector response to live-style telemetry sweeps.
  4. phi_soft_limiter.png   — the φ-scaled audio knee vs. hard clipping.
  5. gateway_lock.png       — K_EGS solar-wind phase-lock response.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from synthobs import (  # noqa: E402
    DEFAULT_SOLAR_WIND_KMS,
    EGS_GATEWAY_KEY,
    PHI,
    SolarWavefieldOscillator,
    assemble_viewport,
    gateway_filter,
    golden_spiral_points,
    phi_soft_limit,
)

# Mid-century palette from the blueprint §3.3.
CHARCOAL = "#36352f"
LINEN = "#efe9dc"
BONE = "#d8d2c4"
ROBIN = "#3aafa9"  # robin's-egg / turquoise — phase-locked status
MARIGOLD = "#e8a33d"  # telemetry markers

FIGURE_FILES = (
    "goldilocks_layout.png",
    "golden_spiral.png",
    "swo_calibration.png",
    "phi_soft_limiter.png",
    "gateway_lock.png",
)


def _outdir() -> Path:
    d = Path(__file__).resolve().parents[1] / "output" / "figures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fig_layout(outdir: Path) -> Path:
    vp = assemble_viewport(1920, 1080)
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    fig.patch.set_facecolor(LINEN)
    ax.set_facecolor(LINEN)
    decks = [
        (vp.primary, ROBIN, f"Primary Output\n{vp.primary_fraction()*100:.1f}%"),
        (vp.console, BONE, "Console Deck\n(3 common + 4 unique)"),
        (vp.telemetry, MARIGOLD, "SWO Telemetry"),
    ]
    for region, color, label in decks:
        ax.add_patch(
            mpatches.Rectangle(
                (region.x, region.y), region.width, region.height,
                facecolor=color, edgecolor=CHARCOAL, lw=2, alpha=0.85,
            )
        )
        ax.text(
            region.x + region.width / 2, region.y + region.height / 2, label,
            ha="center", va="center", color=CHARCOAL, fontsize=9, weight="bold",
        )
    ax.set_xlim(0, 1920)
    ax.set_ylim(1080, 0)
    ax.set_aspect("equal")
    ax.set_title("Goldilocks Layout Matrix — golden-ratio viewport self-assembly", color=CHARCOAL)
    ax.set_xticks([])
    ax.set_yticks([])
    path = outdir / "goldilocks_layout.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=LINEN)
    plt.close(fig)
    return path


def fig_spiral(outdir: Path) -> Path:
    pts = golden_spiral_points(64, a=1.0)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    fig, ax = plt.subplots(figsize=(5.4, 5.4))
    fig.patch.set_facecolor(CHARCOAL)
    ax.set_facecolor(CHARCOAL)
    ax.plot(xs, ys, color=MARIGOLD, lw=2)
    ax.scatter(xs[::4], ys[::4], color=ROBIN, s=18, zorder=3)
    ax.set_aspect("equal")
    ax.set_title("φ Spiral — TRANS_WIPE_SEQUENCE trajectory", color=LINEN)
    ax.tick_params(colors=BONE)
    for spine in ax.spines.values():
        spine.set_color(BONE)
    path = outdir / "golden_spiral.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=CHARCOAL)
    plt.close(fig)
    return path


def fig_swo(outdir: Path) -> Path:
    swo = SolarWavefieldOscillator()
    fluxes = list(range(70, 260, 5))
    series = {}
    for spots in (1, 3, 7):
        ys = []
        for f in fluxes:
            swo.calibrate(float(f), spots)
            ys.append(swo.system_phase_vector)
        series[spots] = ys
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    fig.patch.set_facecolor(LINEN)
    ax.set_facecolor(LINEN)
    for spots, ys in series.items():
        ax.plot(fluxes, ys, lw=2, label=f"{spots} active region(s)")
    ax.set_xlabel("F10.7 solar radio flux (sfu)", color=CHARCOAL)
    ax.set_ylabel("system_phase_vector = (flux/spots)·φ", color=CHARCOAL)
    ax.set_title("Solar Wavefield Oscillator calibration response", color=CHARCOAL)
    ax.legend()
    ax.grid(True, alpha=0.3)
    path = outdir / "swo_calibration.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=LINEN)
    plt.close(fig)
    return path


def fig_limiter(outdir: Path) -> Path:
    xs = [(-3.0 + i * 0.02) for i in range(301)]
    soft = phi_soft_limit(xs, threshold=1.0)
    hard = [max(-1.0, min(1.0, x)) for x in xs]
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    fig.patch.set_facecolor(LINEN)
    ax.set_facecolor(LINEN)
    ax.plot(xs, hard, color=CHARCOAL, lw=1.2, ls="--", label="hard clip (rejected)")
    ax.plot(xs, soft, color=ROBIN, lw=2.4, label="φ soft limiter")
    knee = 1.0 / PHI
    ax.axvline(knee, color=MARIGOLD, lw=1, ls=":")
    ax.axvline(-knee, color=MARIGOLD, lw=1, ls=":")
    ax.text(knee, -0.9, " knee = 1/φ", color=MARIGOLD, fontsize=8)
    ax.set_xlabel("input sample", color=CHARCOAL)
    ax.set_ylabel("output sample", color=CHARCOAL)
    ax.set_title("FractiSynth φ harmonic limiter vs. hard clipping", color=CHARCOAL)
    ax.legend()
    ax.grid(True, alpha=0.3)
    path = outdir / "phi_soft_limiter.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=LINEN)
    plt.close(fig)
    return path


def fig_gateway(outdir: Path) -> Path:
    """EGS gateway lock strength |cos(phase_bias)| across the solar-wind range."""
    winds = [200.0 + i * 5.0 for i in range(141)]  # 200–900 km/s
    locks = [gateway_filter(w).lock_strength for w in winds]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    fig.patch.set_facecolor(LINEN)
    ax.set_facecolor(LINEN)
    ax.plot(winds, locks, color=ROBIN, lw=2.4)
    ax.fill_between(winds, locks, color=ROBIN, alpha=0.12)
    nominal = gateway_filter(DEFAULT_SOLAR_WIND_KMS)
    ax.axvline(DEFAULT_SOLAR_WIND_KMS, color=MARIGOLD, lw=1, ls=":")
    ax.scatter([DEFAULT_SOLAR_WIND_KMS], [nominal.lock_strength], color=MARIGOLD, s=40, zorder=3)
    ax.text(
        DEFAULT_SOLAR_WIND_KMS + 8, nominal.lock_strength,
        f" nominal {DEFAULT_SOLAR_WIND_KMS:.0f} km/s\n lock={nominal.lock_strength:.3f}",
        color=CHARCOAL, fontsize=8, va="center",
    )
    ax.set_xlabel("solar-wind speed (km/s)", color=CHARCOAL)
    ax.set_ylabel("gateway lock strength  |cos(phase bias)|", color=CHARCOAL)
    ax.set_title(
        f"EGS Gateway phase lock (K_EGS = {EGS_GATEWAY_KEY:.4f})", color=CHARCOAL
    )
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)
    path = outdir / "gateway_lock.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=LINEN)
    plt.close(fig)
    return path


def main() -> None:
    outdir = _outdir()
    for builder in (fig_layout, fig_spiral, fig_swo, fig_limiter, fig_gateway):
        print(str(builder(outdir)))


if __name__ == "__main__":
    main()
