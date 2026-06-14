import Std

namespace SynthOBS

/-!
Buildable Lean scaffold for the stable SynthOBS invariants.

The executable engine remains Python/C. This module captures the structural contracts that should
not depend on floating-point runtime details: console cardinality, shared common buttons, disjoint
mode-unique buttons, safety controls, literal pinning, and fail-closed acceptance predicates.
-/

inductive Mode where
  | observatory
  | laboratory
  | expedition
  deriving Repr, DecidableEq

def modes : List Mode :=
  [Mode.observatory, Mode.laboratory, Mode.expedition]

def commonIds : List String :=
  ["CREW_COLLAB_LINK", "RECORD_WAVE_PASS", "LAUNCH_STREAM"]

def uniqueIds : Mode -> List String
  | Mode.observatory =>
      ["SWO_SYNC", "CAP_DEV_ALIGN", "HOLO_GRID_ENGAGE", "OBS_DUMP"]
  | Mode.laboratory =>
      ["EGS_SCALE_LOCK", "TRANS_VIDEO_FLUID", "HARMONIC_COMP", "LAB_RESET_ZERO"]
  | Mode.expedition =>
      ["TRANS_WIPE_SEQUENCE", "BITRATE_THROTTLE", "HULL_INTEG_CHECK", "EMERGENCY_ABORT"]

def safetyId : Mode -> String
  | Mode.observatory => "OBS_DUMP"
  | Mode.laboratory => "LAB_RESET_ZERO"
  | Mode.expedition => "EMERGENCY_ABORT"

def buttonIds (mode : Mode) : List String :=
  commonIds ++ uniqueIds mode

def overlaps (left right : List String) : Bool :=
  left.any fun id => right.contains id

theorem mode_count : modes.length = 3 := by
  native_decide

theorem common_count : commonIds.length = 3 := by
  native_decide

theorem unique_count (mode : Mode) : (uniqueIds mode).length = 4 := by
  cases mode <;> native_decide

theorem button_count (mode : Mode) : (buttonIds mode).length = 7 := by
  cases mode <;> native_decide

theorem common_prefix_identical (mode : Mode) : (buttonIds mode).take 3 = commonIds := by
  cases mode <;> native_decide

theorem safety_id_present (mode : Mode) : (uniqueIds mode).contains (safetyId mode) = true := by
  cases mode <;> native_decide

theorem observatory_unique_not_common :
    overlaps (uniqueIds Mode.observatory) commonIds = false := by
  native_decide

theorem laboratory_unique_not_common :
    overlaps (uniqueIds Mode.laboratory) commonIds = false := by
  native_decide

theorem expedition_unique_not_common :
    overlaps (uniqueIds Mode.expedition) commonIds = false := by
  native_decide

theorem observatory_laboratory_unique_disjoint :
    overlaps (uniqueIds Mode.observatory) (uniqueIds Mode.laboratory) = false := by
  native_decide

theorem observatory_expedition_unique_disjoint :
    overlaps (uniqueIds Mode.observatory) (uniqueIds Mode.expedition) = false := by
  native_decide

theorem laboratory_expedition_unique_disjoint :
    overlaps (uniqueIds Mode.laboratory) (uniqueIds Mode.expedition) = false := by
  native_decide

def phiLiteral : String :=
  "1.61803398875"

def egsGatewayKeyLiteral : String :=
  "2.53942700"

theorem phi_literal_pinned : phiLiteral = "1.61803398875" := by
  rfl

theorem egs_gateway_literal_pinned : egsGatewayKeyLiteral = "2.53942700" := by
  rfl

structure SwoInput where
  fluxFinite : Bool
  fluxPositive : Bool
  spotsPositive : Bool
  deriving Repr, DecidableEq

def acceptsSwoInput (input : SwoInput) : Bool :=
  input.fluxFinite && input.fluxPositive && input.spotsPositive

theorem rejects_nonfinite_flux (fluxPositive spotsPositive : Bool) :
    acceptsSwoInput
      { fluxFinite := false, fluxPositive := fluxPositive, spotsPositive := spotsPositive } =
        false := by
  cases fluxPositive <;> cases spotsPositive <;> native_decide

theorem rejects_nonpositive_flux (fluxFinite spotsPositive : Bool) :
    acceptsSwoInput
      { fluxFinite := fluxFinite, fluxPositive := false, spotsPositive := spotsPositive } =
        false := by
  cases fluxFinite <;> cases spotsPositive <;> native_decide

theorem rejects_nonpositive_spots (fluxFinite fluxPositive : Bool) :
    acceptsSwoInput
      { fluxFinite := fluxFinite, fluxPositive := fluxPositive, spotsPositive := false } =
        false := by
  cases fluxFinite <;> cases fluxPositive <;> native_decide

theorem accepts_only_finite_positive_flux_and_positive_spots :
    acceptsSwoInput { fluxFinite := true, fluxPositive := true, spotsPositive := true } =
      true := by
  native_decide

structure ProvenanceReadiness where
  swoCalibrated : Bool
  gatewayLocked : Bool
  fluxPositive : Bool
  windPositive : Bool
  deriving Repr, DecidableEq

def provenanceReady (state : ProvenanceReadiness) : Bool :=
  state.swoCalibrated && state.gatewayLocked && state.fluxPositive && state.windPositive

theorem provenance_requires_swo_calibration (gatewayLocked fluxPositive windPositive : Bool) :
    provenanceReady
      { swoCalibrated := false,
        gatewayLocked := gatewayLocked,
        fluxPositive := fluxPositive,
        windPositive := windPositive } = false := by
  cases gatewayLocked <;> cases fluxPositive <;> cases windPositive <;> native_decide

theorem provenance_requires_gateway_lock (swoCalibrated fluxPositive windPositive : Bool) :
    provenanceReady
      { swoCalibrated := swoCalibrated,
        gatewayLocked := false,
        fluxPositive := fluxPositive,
        windPositive := windPositive } = false := by
  cases swoCalibrated <;> cases fluxPositive <;> cases windPositive <;> native_decide

theorem provenance_ready_exactly_when_all_runtime_gates_hold :
    provenanceReady
      { swoCalibrated := true,
        gatewayLocked := true,
        fluxPositive := true,
        windPositive := true } = true := by
  native_decide

end SynthOBS
