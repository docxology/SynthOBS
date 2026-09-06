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
  6–8. obs_*.png             — real OBS compositor, HUD, and audio captures.
  9–16. architecture, parser, telemetry, split, matrix, parity, and lifecycle figures.

The user-supplied OBS operator window is copied beside the generated figures for
PDF/HTML path resolution, but it is intentionally excluded from the figure manifest:
it is contextual evidence, not an analytical figure or a promoted live-gate asset.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
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
RUST = "#d48b7f"  # fail-closed / rejected state
MUTED = "#625f56"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 14,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9,
        "figure.dpi": 150,
        "savefig.dpi": 180,
    }
)

FIGURE_FILES = (
    "goldilocks_layout.png",
    "golden_spiral.png",
    "swo_calibration.png",
    "phi_soft_limiter.png",
    "gateway_lock.png",
    "obs_scene_render.png",
    "obs_telemetry_hud.png",
    "obs_audio_tone.png",
    "architecture_layers.png",
    "command_parse_pipeline.png",
    "telemetry_pipeline.png",
    "telemetry_thread.png",
    "golden_split.png",
    "phi_matrix.png",
    "parity_bridge.png",
    "plugin_lifecycle.png",
)

CONTEXTUAL_ASSETS = ("obs_operator_window.png",)

FIGURE_SOURCES = {
    "goldilocks_layout.png": "synthobs.layout.assemble_viewport",
    "golden_spiral.png": "synthobs.layout.golden_spiral_points",
    "swo_calibration.png": "synthobs.swo.SolarWavefieldOscillator",
    "phi_soft_limiter.png": "synthobs.dsp.phi_soft_limit",
    "gateway_lock.png": "synthobs.gateway.gateway_filter",
    "obs_scene_render.png": "versioned live OBS evidence bundle; obs_manifest.json",
    "obs_telemetry_hud.png": "versioned live OBS evidence bundle; obs_manifest.json",
    "obs_audio_tone.png": "versioned live OBS evidence bundle; obs_manifest.json",
    "architecture_layers.png": "SynthOBS architecture specification; src/synthobs source-of-truth invariant",
    "command_parse_pipeline.png": "synthobs.commands.parse and four typed command classes",
    "telemetry_pipeline.png": "synthobs.telemetry fail-closed parsers and SolarWavefieldOscillator",
    "telemetry_thread.png": "plugin/fractisynth/src/fractisynth.c telemetry lifecycle",
    "golden_split.png": "synthobs.layout.golden_split and recursive_subdivision",
    "phi_matrix.png": "synthobs.dsp.spatial_scale_matrix and video_calibrated_dims",
    "parity_bridge.png": "constants.py, fractisynth.c, and test_plugin_artifacts.py parity contracts",
    "plugin_lifecycle.png": "plugin/fractisynth/src/fractisynth.c OBS module lifecycle",
}


def _outdir() -> Path:
    d = Path(__file__).resolve().parents[1] / "output" / "figures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(fig: plt.Figure, path: Path, facecolor: str) -> Path:
    """Save a figure with enough breathing room for its provenance footer."""

    fig.savefig(path, dpi=180, bbox_inches="tight", pad_inches=0.18, facecolor=facecolor)
    plt.close(fig)
    return path


def _style_axes(ax, *, grid: bool = True, dark: bool = False) -> None:
    """Apply a consistent, high-contrast chart treatment."""

    text_color = LINEN if dark else CHARCOAL
    grid_color = BONE if dark else CHARCOAL
    ax.tick_params(axis="both", colors=text_color, labelsize=10, length=4)
    ax.xaxis.label.set_color(text_color)
    ax.yaxis.label.set_color(text_color)
    if grid:
        ax.grid(True, color=grid_color, alpha=0.22 if dark else 0.18, linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_color(BONE if dark else CHARCOAL)
        spine.set_linewidth(0.9)


def _stats_box(
    ax,
    lines: list[str],
    *,
    xy: tuple[float, float] = (0.03, 0.96),
    facecolor: str = BONE,
    textcolor: str = CHARCOAL,
    edgecolor: str = CHARCOAL,
    ha: str = "left",
) -> None:
    """Place a compact evidence/statistics callout in axes coordinates."""

    ax.text(
        xy[0],
        xy[1],
        "\n".join(lines),
        transform=ax.transAxes,
        ha=ha,
        va="top",
        fontsize=9,
        linespacing=1.25,
        color=textcolor,
        bbox={
            "boxstyle": "round,pad=0.42",
            "facecolor": facecolor,
            "edgecolor": edgecolor,
            "linewidth": 0.9,
            "alpha": 0.94,
        },
        zorder=8,
    )


def _live_manifest() -> dict:
    """Read the canonical live evidence bundle for run-specific annotations."""

    path = Path(__file__).resolve().parents[1] / "manuscript" / "assets" / "obs" / "obs_manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _live_metric(gate: str, key: str, default: object = "—") -> object:
    metrics = _live_manifest().get("gates", {}).get(gate, {}).get("metrics", {})
    return metrics.get(key, default)


def _live_run_id() -> str:
    """Return the canonical promoted run identifier for figure annotations."""

    manifest = _live_manifest()
    return str(manifest.get("source_run") or "canonical-live-run")


def _fmt(value: object, digits: int = 1) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def fig_layout(outdir: Path) -> Path:
    vp = assemble_viewport(1920, 1080)
    fig, ax = plt.subplots(figsize=(8.8, 5.1))
    fig.patch.set_facecolor(LINEN)
    ax.set_facecolor(LINEN)
    decks = [
        (
            vp.primary,
            ROBIN,
            f"PRIMARY OUTPUT\n{vp.primary.width} × {vp.primary.height} px\n"
            f"{vp.primary.area / vp.canvas.area * 100:.1f}% of canvas area",
        ),
        (
            vp.console,
            BONE,
            f"CONSOLE DECK\n{vp.console.width} × {vp.console.height} px\n"
            "3 common + 4 unique",
        ),
        (
            vp.telemetry,
            MARIGOLD,
            f"SWO TELEMETRY\n{vp.telemetry.width} × {vp.telemetry.height} px\n"
            "exact residual",
        ),
    ]
    for region, color, label in decks:
        ax.add_patch(
            mpatches.Rectangle(
                (region.x, region.y), region.width, region.height,
                facecolor=color, edgecolor=CHARCOAL, lw=2, alpha=0.85,
            )
        )
        ax.text(
            region.x + region.width / 2,
            region.y + region.height / 2,
            label,
            ha="center",
            va="center",
            color=CHARCOAL,
            fontsize=11 if region is vp.primary else 10,
            weight="bold",
            linespacing=1.35,
        )
    ax.set_xlim(0, 1920)
    ax.set_ylim(1080, 0)
    ax.set_aspect("equal")
    ax.set_title("Goldilocks Layout Matrix — integer-exact viewport self-assembly", color=CHARCOAL, pad=12)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(
        0.5,
        -0.035,
        "1920 × 1080 canvas  ·  3 regions  ·  tiles_exactly() = True  ·  0 px gap / 0 px overlap",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=10,
        color=CHARCOAL,
        weight="bold",
    )
    _source_footer(ax, FIGURE_SOURCES["goldilocks_layout.png"])
    path = outdir / "goldilocks_layout.png"
    return _save(fig, path, LINEN)


def fig_spiral(outdir: Path) -> Path:
    pts = golden_spiral_points(64, a=1.0)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    fig, ax = plt.subplots(figsize=(6.2, 5.9))
    fig.patch.set_facecolor(CHARCOAL)
    ax.set_facecolor(CHARCOAL)
    ax.plot(xs, ys, color=MARIGOLD, lw=2.6, label="sampled trajectory")
    ax.scatter(xs[::4], ys[::4], color=ROBIN, s=34, zorder=3, label="quarter-turn samples")
    ax.set_aspect("equal")
    ax.set_xlabel("x / a")
    ax.set_ylabel("y / a")
    ax.set_title("φ Spiral — TRANS_WIPE_SEQUENCE trajectory", color=LINEN, pad=12)
    _style_axes(ax, grid=True, dark=True)
    _stats_box(
        ax,
        [
            "64 deterministic points",
            "16 quarter-turn markers",
            r"r(θ) = a · φ^(2θ/π)",
            f"growth / quarter-turn = φ = {PHI:.6f}",
        ],
        xy=(0.03, 0.97),
        facecolor="#45433b",
        textcolor=LINEN,
        edgecolor=BONE,
    )
    ax.legend(loc="lower right", frameon=False, labelcolor=LINEN)
    _source_footer(ax, FIGURE_SOURCES["golden_spiral.png"], color=BONE)
    path = outdir / "golden_spiral.png"
    return _save(fig, path, CHARCOAL)


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
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    fig.patch.set_facecolor(LINEN)
    ax.set_facecolor(LINEN)
    for spots, ys in series.items():
        ax.plot(fluxes, ys, lw=2.6, label=f"{spots} active region(s)")
    ax.set_xlabel("F10.7 solar radio flux (sfu)", color=CHARCOAL)
    ax.set_ylabel("system_phase_vector = (flux/spots)·φ", color=CHARCOAL)
    ax.set_title("Solar Wavefield Oscillator calibration response", color=CHARCOAL, pad=12)
    ax.set_xlim(fluxes[0], fluxes[-1])
    ax.legend(loc="upper left", frameon=True, facecolor=LINEN, edgecolor=BONE)
    _style_axes(ax)
    _stats_box(
        ax,
        [
            f"sweep: {fluxes[0]}–{fluxes[-1]} sfu in 5-sfu steps",
            "active-region counts: 1 · 3 · 7",
            f"vector range: {min(min(v) for v in series.values()):.2f}–{max(max(v) for v in series.values()):.2f}",
            "law: flux / spots × φ  ·  no smoothing",
        ],
        xy=(0.98, 0.97),
        ha="right",
        facecolor=LINEN,
        edgecolor=MARIGOLD,
    )
    _source_footer(ax, FIGURE_SOURCES["swo_calibration.png"])
    path = outdir / "swo_calibration.png"
    return _save(fig, path, LINEN)


def fig_limiter(outdir: Path) -> Path:
    xs = [(-3.0 + i * 0.02) for i in range(301)]
    soft = phi_soft_limit(xs, threshold=1.0)
    hard = [max(-1.0, min(1.0, x)) for x in xs]
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    fig.patch.set_facecolor(LINEN)
    ax.set_facecolor(LINEN)
    ax.plot(xs, hard, color=CHARCOAL, lw=1.5, ls="--", label="hard clip (rejected)")
    ax.plot(xs, soft, color=ROBIN, lw=2.8, label="φ soft limiter")
    knee = 1.0 / PHI
    ax.axvline(knee, color=MARIGOLD, lw=1.4, ls=":")
    ax.axvline(-knee, color=MARIGOLD, lw=1.4, ls=":")
    ax.axhline(1.0, color=CHARCOAL, lw=0.9, ls=":", alpha=0.7)
    ax.axhline(-1.0, color=CHARCOAL, lw=0.9, ls=":", alpha=0.7)
    ax.text(knee + 0.04, -0.92, f"knee = 1/φ = {knee:.6f}", color=MARIGOLD, fontsize=10)
    ax.set_xlabel("input sample", color=CHARCOAL)
    ax.set_ylabel("output sample", color=CHARCOAL)
    ax.set_title("FractiSynth φ harmonic limiter vs. hard clipping", color=CHARCOAL, pad=12)
    ax.set_xlim(-3.0, 3.0)
    ax.set_ylim(-1.08, 1.08)
    ax.legend(loc="upper left", frameon=True, facecolor=LINEN, edgecolor=BONE)
    _style_axes(ax)
    _stats_box(
        ax,
        [
            "threshold τ = 1.000",
            f"identity band: |x| ≤ {knee:.6f}",
            "bounded output: |y| ≤ τ",
            "non-finite input: absorbed, never propagated",
        ],
        xy=(0.98, 0.97),
        ha="right",
        facecolor=LINEN,
        edgecolor=ROBIN,
    )
    _source_footer(ax, FIGURE_SOURCES["phi_soft_limiter.png"])
    path = outdir / "phi_soft_limiter.png"
    return _save(fig, path, LINEN)


def fig_gateway(outdir: Path) -> Path:
    """EGS gateway lock strength |cos(phase_bias)| across the solar-wind range."""
    winds = [200.0 + i * 5.0 for i in range(141)]  # 200–900 km/s
    locks = [gateway_filter(w).lock_strength for w in winds]
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    fig.patch.set_facecolor(LINEN)
    ax.set_facecolor(LINEN)
    ax.plot(winds, locks, color=ROBIN, lw=2.8, label="gateway_filter(wind)")
    ax.fill_between(winds, locks, color=ROBIN, alpha=0.12)
    nominal = gateway_filter(DEFAULT_SOLAR_WIND_KMS)
    ax.axvline(DEFAULT_SOLAR_WIND_KMS, color=MARIGOLD, lw=1, ls=":")
    ax.scatter([DEFAULT_SOLAR_WIND_KMS], [nominal.lock_strength], color=MARIGOLD, s=40, zorder=3)
    ax.set_xlabel("solar-wind speed (km/s)", color=CHARCOAL)
    ax.set_ylabel("gateway lock strength  |cos(phase bias)|", color=CHARCOAL)
    ax.set_title(
        f"EGS Gateway phase lock (K_EGS = {EGS_GATEWAY_KEY:.6f})", color=CHARCOAL, pad=12
    )
    ax.set_ylim(-0.02, 1.02)
    _style_axes(ax)
    live_wind = _live_metric("provenance_lsb", "solar_wind_kms", None)
    live_lock = _live_metric("provenance_lsb", "lock_strength", None)
    if isinstance(live_wind, (int, float)):
        ax.axvline(live_wind, color=ROBIN, lw=1.2, ls="--", alpha=0.9)
        ax.text(float(live_wind) + 8, 0.12, "captured wind", color=ROBIN, fontsize=9, rotation=90, va="bottom")
    _stats_box(
        ax,
        [
            "model sweep: 200–900 km/s",
            f"design point: {DEFAULT_SOLAR_WIND_KMS:.1f} km/s · lock={nominal.lock_strength:.4f}",
            f"live payload fields (verbatim): {_fmt(live_wind, 1)} km/s · lock={_fmt(live_lock, 4)}",
            f"phase law: |cos(2π · wind/400 · K_EGS)|",
        ],
        xy=(0.98, 0.97),
        ha="right",
        facecolor=LINEN,
        edgecolor=MARIGOLD,
    )
    ax.legend(loc="lower left", frameon=True, facecolor=LINEN, edgecolor=BONE)
    _source_footer(ax, FIGURE_SOURCES["gateway_lock.png"])
    path = outdir / "gateway_lock.png"
    return _save(fig, path, LINEN)


def _source_footer(ax, source: str, *, color: str = MUTED) -> None:
    ax.text(
        0.01, -0.13, f"Source: {source}", transform=ax.transAxes,
        ha="left", va="top", fontsize=8, color=color,
    )


def _box(ax, xy, width, height, title, detail, color=ROBIN):
    rect = mpatches.FancyBboxPatch(
        xy, width, height, boxstyle="round,pad=0.018,rounding_size=0.025",
        facecolor=color, edgecolor=CHARCOAL, linewidth=1.6, alpha=0.9,
    )
    ax.add_patch(rect)
    ax.text(xy[0] + width / 2, xy[1] + height * 0.62, title,
            ha="center", va="center", fontsize=11, weight="bold", color=CHARCOAL)
    ax.text(xy[0] + width / 2, xy[1] + height * 0.30, detail,
            ha="center", va="center", fontsize=9, color=CHARCOAL, wrap=True, linespacing=1.2)


def _arrow(ax, start, end, color=CHARCOAL, label=None, rad=0.0):
    ax.add_patch(mpatches.FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=13, linewidth=1.5,
        color=color, connectionstyle=f"arc3,rad={rad}",
    ))
    if label:
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        ax.text(mid[0], mid[1] + 0.035, label, ha="center", va="bottom",
                fontsize=9, color=color)


def fig_architecture(outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    fig.patch.set_facecolor(LINEN)
    ax.set_facecolor(LINEN)
    _box(ax, (0.04, 0.67), 0.92, 0.18, "φ / K_EGS constants", "constants.py → C literal parity", MARIGOLD)
    _box(ax, (0.04, 0.35), 0.27, 0.18, "Python engine", "src/synthobs\nmath + tests", ROBIN)
    _box(ax, (0.365, 0.35), 0.27, 0.18, "Native libobs", "plugin/fractisynth\nrender + audio", BONE)
    _box(ax, (0.69, 0.35), 0.27, 0.18, "obspython bridge", "plugin/synthobs\noperator console", MARIGOLD)
    _box(ax, (0.18, 0.07), 0.64, 0.15, "Live OBS runtime", "dashboard · telemetry HUD · audio-reactive scene", ROBIN)
    for x in (0.175, 0.50, 0.825):
        _arrow(ax, (x, 0.67), (x, 0.535), label="mirror" if x == 0.50 else None)
        _arrow(ax, (x, 0.35), (x, 0.225))
    ax.text(0.5, 0.93, "SynthOBS layered architecture and evidence path", ha="center", va="center", fontsize=15, weight="bold", color=CHARCOAL)
    _stats_box(
        ax,
        [
            "3 layers · 1 source-of-truth engine",
            "1217 tests · 96.09% src coverage",
            "live target: OBS 32.1.2",
        ],
        xy=(0.02, 0.64),
        facecolor=LINEN,
        edgecolor=ROBIN,
    )
    ax.set_xlim(0, 1); ax.set_ylim(-0.02, 1.0); ax.axis("off")
    _source_footer(ax, FIGURE_SOURCES["architecture_layers.png"])
    path = outdir / "architecture_layers.png"
    return _save(fig, path, LINEN)


def fig_command_pipeline(outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9.1, 5.8))
    fig.patch.set_facecolor(LINEN); ax.set_facecolor(LINEN)
    stages = [
        ("Input", "raw command line", BONE),
        ("Tokenize", "shlex; quotes must balance", ROBIN),
        ("Dispatch", "/mode · /transducer · /swo · /dashboard", MARIGOLD),
        ("Validate", "verb-specific finite/range checks", ROBIN),
        ("Typed result", "four classes: mode · bind · calibrate · dashboard", BONE),
    ]
    ys = [0.79, 0.61, 0.43, 0.25, 0.07]
    for (title, detail, color), y in zip(stages, ys):
        _box(ax, (0.20, y), 0.58, 0.12, title, detail, color)
        if y > 0.1:
            _arrow(ax, (0.50, y), (0.50, y - 0.04))
    ax.add_patch(mpatches.FancyBboxPatch((0.82, 0.30), 0.16, 0.28, boxstyle="round,pad=0.02", facecolor=RUST, edgecolor=CHARCOAL, linewidth=1.6))
    ax.text(0.90, 0.47, "CommandError\nexplicit sink", ha="center", va="center", fontsize=10, weight="bold", color=CHARCOAL)
    for y in (0.61, 0.43, 0.25):
        _arrow(ax, (0.78, y + 0.06), (0.82, 0.44), color="#9c4d43", rad=-0.22)
    ax.text(0.5, 0.98, "Global command grammar: accepted path and rejection sink", ha="center", fontsize=14, weight="bold", color=CHARCOAL)
    ax.text(
        0.5,
        0.925,
        "4 verbs · 4 typed result classes · 3 validation choke points · all malformed paths → CommandError",
        ha="center",
        va="top",
        fontsize=9,
        color=CHARCOAL,
        bbox={"boxstyle": "round,pad=0.28", "facecolor": LINEN, "edgecolor": MARIGOLD, "linewidth": 0.9},
    )
    ax.set_xlim(-0.03, 1.03); ax.set_ylim(0, 1); ax.axis("off")
    _source_footer(ax, FIGURE_SOURCES["command_parse_pipeline.png"])
    path = outdir / "command_parse_pipeline.png"
    return _save(fig, path, LINEN)


def fig_telemetry_pipeline(outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9.2, 5.1))
    fig.patch.set_facecolor(LINEN); ax.set_facecolor(LINEN)
    _box(ax, (0.03, 0.66), 0.25, 0.18, "NOAA SWPC", "F10.7 + active regions", MARIGOLD)
    _box(ax, (0.03, 0.34), 0.25, 0.18, "NOAA RTSW", "wind + plasma series", BONE)
    _box(ax, (0.37, 0.50), 0.27, 0.22, "Parse and gate", "positive · finite · fresh\nmalformed rows skipped", ROBIN)
    _box(ax, (0.37, 0.17), 0.27, 0.18, "Hold State", "retain last verified vector", RUST)
    _box(ax, (0.73, 0.50), 0.24, 0.22, "SWO / Gateway", "phase vector + lock", MARIGOLD)
    _box(ax, (0.73, 0.17), 0.24, 0.18, "Consumers", "layout · DSP · HUD", ROBIN)
    _arrow(ax, (0.28, 0.75), (0.37, 0.62), label="JSON")
    _arrow(ax, (0.28, 0.43), (0.37, 0.59), label="JSON")
    _arrow(ax, (0.64, 0.61), (0.73, 0.61), label="valid")
    _arrow(ax, (0.64, 0.43), (0.50, 0.35), color="#9c4d43", label="invalid")
    _arrow(ax, (0.64, 0.26), (0.73, 0.26), color="#9c4d43", label="held")
    _arrow(ax, (0.85, 0.50), (0.85, 0.35))
    ax.text(0.5, 0.98, "Fail-closed telemetry pipeline", ha="center", fontsize=15, weight="bold", color=CHARCOAL)
    ax.text(
        0.5,
        0.91,
        f"Live payload fields · run {_live_run_id()}: F10.7={_fmt(_live_metric('provenance_lsb', 'flux'), 1)} sfu · spots={_fmt(_live_metric('provenance_lsb', 'sunspots'), 0)} · wind={_fmt(_live_metric('provenance_lsb', 'solar_wind_kms'), 1)} km/s · reported lock={_fmt(_live_metric('provenance_lsb', 'lock_strength'), 4)} · invalid/stale → Hold State",
        ha="center",
        va="top",
        fontsize=8.5,
        color=CHARCOAL,
        bbox={"boxstyle": "round,pad=0.30", "facecolor": LINEN, "edgecolor": ROBIN, "linewidth": 0.9},
    )
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _source_footer(ax, FIGURE_SOURCES["telemetry_pipeline.png"])
    path = outdir / "telemetry_pipeline.png"
    return _save(fig, path, LINEN)


def fig_telemetry_thread(outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    fig.patch.set_facecolor(LINEN); ax.set_facecolor(LINEN)
    xs = [0.12, 0.31, 0.50, 0.69, 0.88]
    labels = [("start", "curl init"), ("fetch", "F10.7 · spots · wind"), ("gate", "finite + fresh"), ("publish", "mutex\nstate"), ("stop", "abort +\nbounded join")]
    for i, ((title, detail), x) in enumerate(zip(labels, xs)):
        _box(ax, (x - 0.08, 0.39), 0.16, 0.22, title, detail, [BONE, MARIGOLD, ROBIN, ROBIN, RUST][i])
        if i < len(xs) - 1:
            _arrow(ax, (x + 0.08, 0.50), (xs[i + 1] - 0.08, 0.50))
    ax.text(0.5, 0.96, "Native telemetry thread lifecycle (60 s poll cadence)", ha="center", fontsize=15, weight="bold", color=CHARCOAL)
    ax.text(0.5, 0.17, "Invalid payloads follow the hold path; cleanup is explicit and bounded.", ha="center", fontsize=10, color=CHARCOAL)
    _stats_box(
        ax,
        [
            "worker contract: fetch → finite/fresh gate → mutex publish",
            "shutdown contract: abort → bounded join → curl cleanup",
            "cadence: TELEMETRY_POLL_SECONDS = 60",
        ],
        xy=(0.02, 0.84),
        facecolor=LINEN,
        edgecolor=MARIGOLD,
    )
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _source_footer(ax, FIGURE_SOURCES["telemetry_thread.png"])
    path = outdir / "telemetry_thread.png"
    return _save(fig, path, LINEN)


def fig_golden_split(outdir: Path) -> Path:
    total = 1000
    major, minor = int(round(total / PHI)), total - int(round(total / PHI))
    fig, ax = plt.subplots(figsize=(8.4, 3.7))
    fig.patch.set_facecolor(LINEN); ax.set_facecolor(LINEN)
    ax.barh([0], [major], color=ROBIN, edgecolor=CHARCOAL, height=0.42, label="major = round(total / φ)")
    ax.barh([0], [minor], left=[major], color=MARIGOLD, edgecolor=CHARCOAL, height=0.42, label="minor = total − major")
    ax.text(major / 2, 0, f"MAJOR\n{major}/{total} = {major / total:.1%}\n1/φ", ha="center", va="center", fontsize=12, weight="bold", color=CHARCOAL)
    ax.text(major + minor / 2, 0, f"MINOR\n{minor}/{total} = {minor / total:.1%}\n1/φ²", ha="center", va="center", fontsize=11, weight="bold", color=CHARCOAL)
    ax.set_xlim(0, total); ax.set_ylim(-0.58, 0.58); ax.set_yticks([]); ax.set_xticks([0, major, total], ["0", f"{major} = round(total/φ)", f"{total} = exact total"])
    ax.set_title("Integer-exact golden split and recursive remainder", color=CHARCOAL, weight="bold", pad=12)
    _style_axes(ax, grid=False)
    _stats_box(
        ax,
        [
            f"example total: {total} units",
            f"major + minor = {major} + {minor} = {total}",
            "minor is residual; no rounding gap",
            "recursive source: golden_split(total)",
        ],
        xy=(0.98, 0.96),
        ha="right",
        facecolor=LINEN,
        edgecolor=ROBIN,
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.26), ncol=2, frameon=False)
    _source_footer(ax, FIGURE_SOURCES["golden_split.png"])
    path = outdir / "golden_split.png"
    return _save(fig, path, LINEN)


def fig_phi_matrix(outdir: Path) -> Path:
    s = 1.0 / PHI
    matrix = [[s, 0.0, 0.0], [0.0, s, 0.0], [0.0, 0.0, 1.0]]
    fig, ax = plt.subplots(figsize=(6.1, 5.2))
    fig.patch.set_facecolor(LINEN); ax.set_facecolor(LINEN)
    # Reserve a distinct title band above the matrix so the evidence banner
    # remains readable at manuscript and PDF raster sizes.
    fig.subplots_adjust(left=0.15, right=0.80, bottom=0.18, top=0.70)
    im = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{matrix[i][j]:.3f}", ha="center", va="center", color=CHARCOAL, fontsize=11, weight="bold")
    ax.set_xticks(range(3), ["x", "y", "h"]); ax.set_yticks(range(3), ["x′", "y′", "h′"])
    ax.set_title("φ spatial transform matrix", color=CHARCOAL, weight="bold", pad=12)
    fig.colorbar(im, ax=ax, shrink=0.78, label="scale")
    fig.text(
        0.48,
        0.90,
        f"1/φ = {s:.6f}  ·  x/y shrink together  ·  h = 1  ·  1920 × 1080 → 1187 × 667 px",
        ha="center",
        va="center",
        fontsize=9,
        color=CHARCOAL,
        bbox={"boxstyle": "round,pad=0.30", "facecolor": LINEN, "edgecolor": ROBIN, "linewidth": 0.9},
    )
    _source_footer(ax, FIGURE_SOURCES["phi_matrix.png"])
    path = outdir / "phi_matrix.png"
    return _save(fig, path, LINEN)


def fig_parity_bridge(outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9.1, 5.0))
    fig.patch.set_facecolor(LINEN); ax.set_facecolor(LINEN)
    _box(ax, (0.04, 0.48), 0.29, 0.25, "Python reference", "PHI = 1.61803398875\nK_EGS = φ·1030/656.28", ROBIN)
    _box(ax, (0.67, 0.48), 0.29, 0.25, "C plugin mirror", "EGS_PHI = 1.61803398875f\nEGS_GATEWAY_KEY literal", MARIGOLD)
    _box(ax, (0.28, 0.08), 0.44, 0.22, "Parity contracts", "constants · dimensions · limiter ·\ntelemetry gates · live behavior", BONE)
    _arrow(ax, (0.33, 0.60), (0.67, 0.60), label="same numeric pins")
    _arrow(ax, (0.20, 0.48), (0.40, 0.30), label="tests", rad=0.20)
    _arrow(ax, (0.80, 0.48), (0.60, 0.30), label="static + live", rad=-0.20)
    ax.text(0.5, 0.96, "Python/native parity is an executable contract", ha="center", fontsize=15, weight="bold", color=CHARCOAL)
    _stats_box(
        ax,
        [
            "φ pin: ≥9 significant digits",
            "K_EGS pin: < 1e−6 tolerance",
            "1217 tests · 96.09% coverage · native build · live OBS",
        ],
        xy=(0.02, 0.84),
        facecolor=LINEN,
        edgecolor=MARIGOLD,
    )
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _source_footer(ax, FIGURE_SOURCES["parity_bridge.png"])
    path = outdir / "parity_bridge.png"
    return _save(fig, path, LINEN)


def fig_plugin_lifecycle(outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9.1, 4.6))
    fig.patch.set_facecolor(LINEN); ax.set_facecolor(LINEN)
    xs = [0.10, 0.30, 0.50, 0.70, 0.90]
    states = [("load", "register sources"), ("init", "curl + mutex"), ("run", "video + audio +\ninspector + poller"), ("unload", "stop + join"), ("clean", "curl cleanup")]
    for i, ((title, detail), x) in enumerate(zip(states, xs)):
        width = 0.17
        _box(ax, (x - width / 2, 0.42), width, 0.22, title, detail, [BONE, MARIGOLD, ROBIN, RUST, BONE][i])
        if i < len(xs) - 1:
            _arrow(ax, (x + width / 2, 0.53), (xs[i + 1] - width / 2, 0.53))
    ax.text(0.5, 0.96, "FractiSynth OBS module lifecycle", ha="center", fontsize=15, weight="bold", color=CHARCOAL)
    ax.text(0.5, 0.18, "Runtime owns three filters, the console source, and the fail-closed telemetry worker.", ha="center", fontsize=10, color=CHARCOAL)
    _stats_box(
        ax,
        [
            "4 registered runtime surfaces",
            "3 filters + console source; Qt dock optional",
            "unload: stop flag → bounded join",
        ],
        xy=(0.02, 0.84),
        facecolor=LINEN,
        edgecolor=ROBIN,
    )
    ax.set_xlim(-0.03, 1.03); ax.set_ylim(0, 1); ax.axis("off")
    _source_footer(ax, FIGURE_SOURCES["plugin_lifecycle.png"])
    path = outdir / "plugin_lifecycle.png"
    return _save(fig, path, LINEN)


def copy_live_obs_evidence(outdir: Path) -> list[Path]:
    """Copy the versioned, verified real OBS screenshots into figure output."""

    root = Path(__file__).resolve().parents[1]
    srcdir = root / "manuscript" / "assets" / "obs"
    manifest_path = srcdir / "obs_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"versioned live OBS manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = tuple(manifest.get("required_gates", ()))
    gates = manifest.get("gates", {})
    if manifest.get("schema") != "synthobs.live_scenario.v2" or not required:
        raise ValueError("versioned OBS evidence manifest has an invalid schema or gate list")
    failed = [gate for gate in required if gates.get(gate, {}).get("status") != "pass"]
    if failed:
        raise ValueError(f"versioned OBS evidence is not fail-closed: gates={failed}")
    names = (
        "obs_scene_render.png",
        "obs_telemetry_hud.png",
        "obs_audio_tone.png",
    )
    copied: list[Path] = []
    missing: list[Path] = []
    for name in names:
        src = srcdir / name
        dst = outdir / name
        asset_key = name.removeprefix("obs_").removesuffix(".png")
        expected = manifest.get("assets", {}).get(asset_key, {})
        if not src.exists() or not expected:
            missing.append(src)
            continue
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        if digest != expected.get("sha256"):
            raise ValueError(f"OBS asset hash mismatch for {src}: {digest}")
        shutil.copy2(src, dst)
        copied.append(dst)
    if missing:
        joined = ", ".join(str(p) for p in missing)
        raise FileNotFoundError(
            "versioned real OBS evidence screenshots are missing; rerun the live scenario "
            f"and promote the passing captures into docs/manuscript/assets/obs: {joined}"
        )
    return copied


def copy_contextual_assets(outdir: Path) -> list[Path]:
    """Copy manuscript-context images without promoting them into the figure manifest."""

    root = Path(__file__).resolve().parents[1]
    srcdir = root / "manuscript" / "assets" / "obs"
    copied: list[Path] = []
    for name in CONTEXTUAL_ASSETS:
        src = srcdir / name
        if not src.is_file():
            raise FileNotFoundError(f"contextual manuscript asset is missing: {src}")
        dst = outdir / name
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def _source_revision() -> str:
    """Return the inspected source revision without making generation depend on git."""

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _png_dimensions(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or len(raw) < 24:
        raise ValueError(f"figure is not a valid PNG: {path}")
    return struct.unpack(">II", raw[16:24])


def write_figure_manifest(outdir: Path) -> Path:
    live = {"obs_scene_render.png", "obs_telemetry_hud.png", "obs_audio_tone.png"}
    figures = []
    for name in FIGURE_FILES:
        path = outdir / name
        width, height = _png_dimensions(path)
        figures.append(
            {
                "file": name,
                "kind": "live_obs_capture" if name in live else "analytical",
                "source": FIGURE_SOURCES[name],
                "description": name.removesuffix(".png").replace("_", " "),
                "width": width,
                "height": height,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    manifest = {
        "schema": "synthobs.figure_manifest.v1",
        "generator": "scripts/generate_figures.py",
        "source_revision": _source_revision(),
        "deterministic": all(item["kind"] == "analytical" for item in figures),
        "analytical_count": sum(item["kind"] == "analytical" for item in figures),
        "live_capture_count": sum(item["kind"] == "live_obs_capture" for item in figures),
        "live_manifest": "docs/manuscript/assets/obs/obs_manifest.json",
        "figures": figures,
    }
    path = outdir / "figure_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    outdir = _outdir()
    for builder in (
        fig_layout, fig_spiral, fig_swo, fig_limiter, fig_gateway,
        fig_architecture, fig_command_pipeline, fig_telemetry_pipeline,
        fig_telemetry_thread, fig_golden_split, fig_phi_matrix,
        fig_parity_bridge, fig_plugin_lifecycle,
    ):
        print(str(builder(outdir)))
    for path in copy_live_obs_evidence(outdir):
        print(str(path))
    for path in copy_contextual_assets(outdir):
        print(str(path))
    print(str(write_figure_manifest(outdir)))


if __name__ == "__main__":
    main()
