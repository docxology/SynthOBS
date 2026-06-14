"""SynthOBS / FractiSynth v1.618 — the tested Python engine.

This package is the verified source of truth for the SynthOBS console and the
FractiSynth transducer: golden-ratio (EGS) layout geometry, the fail-closed Solar
Wavefield Oscillator over live solar telemetry, φ-scaled audio/video DSP, the
3-mode 7-button console, and the command-line grammar. The native libobs C plugin
(``plugin/fractisynth``) and the obspython console script (``plugin/synthobs``)
mirror this engine.
"""

from __future__ import annotations

from .commands import (
    BindCommand,
    CalibrateCommand,
    Command,
    CommandError,
    DashboardCommand,
    ModeCommand,
    parse,
)
from .console import Button, Console, Mode
from .constants import (
    CRAB_PULSAR_HZ,
    DEFAULT_SOLAR_WIND_KMS,
    EGS_CONSTANT,
    EGS_GATEWAY_KEY,
    EGS_GATEWAY_KEY_C_LITERAL,
    H_LINE_MHZ,
    INV_PHI,
    INV_PHI_SQ,
    LAMBDA_H_ALPHA_NM,
    LAMBDA_READER_NM,
    PHI,
    PHI_C_LITERAL,
    REFERENCE_SOLAR_WIND_KMS,
)
from .dsp import (
    AudioEnvelope,
    audio_envelope,
    phi_soft_limit,
    phi_soft_limit_sample,
    spatial_scale_matrix,
    video_calibrated_dims,
)
from .engine import EngineState, SynthEngine
from .gateway import GatewayLock, egs_fractal_constant, gateway_filter
from .interference import (
    InterferenceVerdict,
    NodeField,
    holographic_gate,
    interference_intensity,
    is_holographic_false,
    is_holographic_true,
    rsi_is_stable,
    rsi_step,
)
from .interaction import Feed, GraphMetric, TargetAction, TargetHit, resolve_target_action
from .layers import DashboardLayer, DashboardPlan, dashboard_plan
from .layout import (
    Region,
    Viewport,
    assemble_viewport,
    golden_spiral_points,
    golden_split,
    recursive_subdivision,
)
from .swo import SolarWavefieldOscillator, phase_vector
from .history import Sample, TelemetryHistory
from .provenance import (
    ProvenanceError,
    TelemetryRecord,
    build_payload,
    canonical_bytes,
    embed_lsb,
    extract_lsb,
    provenance_digest,
    short_signature,
    signature_bits,
    verify_payload,
)
from .telemetry import (
    DEFAULT_MAX_AGE_S,
    NOAA_SOLAR_WIND_URL,
    NOAA_SOLAR_REGIONS_URL,
    SolarTelemetry,
    SolarWind,
    TelemetryUnavailable,
    fetch_live_solar_wind,
    fetch_live_telemetry,
    parse_noaa_f107_flux,
    parse_noaa_solar_wind,
    parse_noaa_solar_regions,
    telemetry_from_payload,
)
from .verification import (
    AUDIO_METER_TOP_FRACTION,
    GateResult,
    RoiDelta,
    audio_meter_roi,
    score_audio_meter_delta,
    score_roi_delta,
)

__version__ = "1.618.0"

__all__ = [
    "__version__",
    # constants
    "PHI",
    "EGS_CONSTANT",
    "INV_PHI",
    "INV_PHI_SQ",
    "PHI_C_LITERAL",
    "EGS_GATEWAY_KEY",
    "EGS_GATEWAY_KEY_C_LITERAL",
    "LAMBDA_READER_NM",
    "LAMBDA_H_ALPHA_NM",
    "REFERENCE_SOLAR_WIND_KMS",
    "DEFAULT_SOLAR_WIND_KMS",
    "H_LINE_MHZ",
    "CRAB_PULSAR_HZ",
    # gateway
    "GatewayLock",
    "egs_fractal_constant",
    "gateway_filter",
    # interference
    "NodeField",
    "InterferenceVerdict",
    "interference_intensity",
    "holographic_gate",
    "is_holographic_true",
    "is_holographic_false",
    "rsi_step",
    "rsi_is_stable",
    # layout
    "Region",
    "Viewport",
    "golden_split",
    "recursive_subdivision",
    "assemble_viewport",
    "golden_spiral_points",
    # telemetry
    "SolarTelemetry",
    "TelemetryUnavailable",
    "parse_noaa_f107_flux",
    "telemetry_from_payload",
    "fetch_live_telemetry",
    "DEFAULT_MAX_AGE_S",
    "SolarWind",
    "parse_noaa_solar_wind",
    "fetch_live_solar_wind",
    "NOAA_SOLAR_WIND_URL",
    "parse_noaa_solar_regions",
    "NOAA_SOLAR_REGIONS_URL",
    # swo
    "SolarWavefieldOscillator",
    "phase_vector",
    # dsp
    "AudioEnvelope",
    "audio_envelope",
    "video_calibrated_dims",
    "spatial_scale_matrix",
    "phi_soft_limit",
    "phi_soft_limit_sample",
    # console
    "Mode",
    "Button",
    "Console",
    # commands
    "Command",
    "ModeCommand",
    "BindCommand",
    "CalibrateCommand",
    "DashboardCommand",
    "CommandError",
    "parse",
    # interaction / dashboard
    "Feed",
    "GraphMetric",
    "TargetAction",
    "TargetHit",
    "resolve_target_action",
    "DashboardLayer",
    "DashboardPlan",
    "dashboard_plan",
    # engine
    "SynthEngine",
    "EngineState",
    # history / waveform
    "Sample",
    "TelemetryHistory",
    # provenance / steganography
    "ProvenanceError",
    "TelemetryRecord",
    "canonical_bytes",
    "provenance_digest",
    "short_signature",
    "signature_bits",
    "build_payload",
    "embed_lsb",
    "extract_lsb",
    "verify_payload",
    # live verification
    "AUDIO_METER_TOP_FRACTION",
    "GateResult",
    "RoiDelta",
    "audio_meter_roi",
    "score_audio_meter_delta",
    "score_roi_delta",
]
