"""Single source of truth for all metric key strings.

Using str, Enum means:
- Misspelled keys are caught at import time, not runtime.
- Values are still plain strings so JSON serialisation and dict lookups
  using raw string literals both work without conversion.
"""

from __future__ import annotations

from enum import Enum


class MetricKey(str, Enum):
    # --- side-view scored ---
    CADENCE                 = "cadence"
    TRUNK_LEAN              = "trunk_lean"
    KNEE_FLEXION_MIDSTANCE  = "knee_flexion_midstance"
    OVERSTRIDE              = "overstride"
    VERTICAL_OSCILLATION    = "vertical_oscillation"
    CONTACT_TIME            = "contact_time"
    DUTY_FACTOR             = "duty_factor"
    HIP_EXTENSION           = "hip_extension"
    ELBOW_ANGLE             = "elbow_angle"
    # --- rear-view scored ---
    PELVIC_DROP             = "pelvic_drop"
    PRONATION               = "pronation"
    STEP_WIDTH              = "step_width"
    LATERAL_TRUNK_SWAY      = "lateral_trunk_sway"
    # --- shared / informational ---
    ASYMMETRY               = "asymmetry"
    FOOT_STRIKE_ANGLE       = "foot_strike_angle"
    ARM_SWING               = "arm_swing"
    ARM_CROSSOVER           = "arm_crossover"
    HEEL_RECOVERY           = "heel_recovery"
    HEAD_DROP               = "head_drop"
    HEAD_LATERAL_SWAY       = "head_lateral_sway"
    FLIGHT_TIME             = "flight_time"
    TRUNK_PELVIS_ROTATION   = "trunk_pelvis_rotation"
    CROSSOVER               = "crossover"
    # --- per-side only (asymmetry inputs, not globally scored) ---
    KNEE_FLEXION_CONTACT    = "knee_flexion_contact"
    KNEE_FLEXION_PEAK       = "knee_flexion_peak"
    KNEE_FLEXION_EXCURSION  = "knee_flexion_excursion"
    HIP_FLEXION_PEAK        = "hip_flexion_peak"
    ANKLE_DORSIFLEXION      = "ankle_dorsiflexion_midstance"
    ANKLE_PLANTARFLEXION    = "ankle_plantarflexion_toeoff"
    SHANK_ANGLE_CONTACT     = "shank_angle_contact"
    CONTACT_TIME_MS         = "contact_time_ms"
    STEP_TIME               = "step_time"
    STRIDE_TIME             = "stride_time"
    SWING_TIME              = "swing_time"
    CADENCE_CV              = "cadence_cv"
    CONTACT_TIME_CV         = "contact_time_cv"
    STRIDE_LENGTH           = "stride_length"
    STEP_LENGTH             = "step_length"
    STEP_LENGTH_LEG_RATIO   = "step_length_leg_ratio"
    DIMENSIONLESS_SPEED     = "dimensionless_speed"
    # --- calibration-derived absolutes ---
    VERTICAL_OSCILLATION_CM = "vertical_oscillation_cm"
    VERTICAL_RATIO          = "vertical_ratio"
