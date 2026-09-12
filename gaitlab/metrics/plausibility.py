"""Physiological plausibility bounds — an engineering sanity check, not a verdict.

These are deliberately NOT the `good`/`warn` target bands this release retired. A
target band judges the runner ("you should be at 180 spm"); these judge the
measurement ("no human runs at 60 spm, so our number is wrong"). Nothing here says a
value is good, bad, or worth changing — only that a value outside the range means the
pipeline produced something a running human cannot have done.

They exist because a wrong number is otherwise indistinguishable from a real one. The
gait-event anchoring regression this release fixed reported a 67 ms contact time and a
10.5% duty factor with high event confidence and no warning; both are caught here.

Three kinds of bound, in descending order of how arguable they are:

* definitional — these delimit running as a gait mode. A duty factor at or above 50%
  means the subject is walking, whatever else is true.
* anatomical — joint range of motion. A knee cannot flex 200 degrees.
* literature — wide ranges from running-biomechanics texts. Loose on purpose: these
  are sensitivity, not specificity. A cadence of 90 says something is broken; a
  cadence of 165 says nothing at all.

Signed metrics get symmetric bounds. Several of these (overstride, pelvic_drop,
ankle_plantarflexion_toeoff, shank_angle_contact, foot_strike_angle, step_width) can
legitimately be negative, and a one-sided bound on them produces false positives on
real data.

Bounds are validated in tests/test_plausibility.py against every clip in the
repository. Any change here must keep that at zero false positives.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

DEFINITIONAL = "definitional"
ANATOMICAL = "anatomical"
LITERATURE = "literature"

# key -> (low, high, basis)
BOUNDS: Dict[str, Tuple[float, float, str]] = {
    # -- definitional: these delimit running as a gait mode --------------------
    "duty_factor": (15, 50, DEFINITIONAL),          # >=50% is walking; <15% beats sprinting
    "flight_time": (20, 400, DEFINITIONAL),         # flight >0 is what makes it running
    "cadence_cv": (0, 30, DEFINITIONAL),            # >30% is detector instability
    "contact_time_cv": (0, 30, DEFINITIONAL),
    # -- anatomical: joint range of motion -------------------------------------
    "knee_flexion_contact": (0, 60, ANATOMICAL),
    "knee_flexion_midstance": (0, 90, ANATOMICAL),
    "knee_flexion_peak": (20, 160, ANATOMICAL),
    "knee_flexion_excursion": (0, 90, ANATOMICAL),
    "hip_extension": (0, 90, ANATOMICAL),
    "hip_flexion_peak": (0, 90, ANATOMICAL),
    "elbow_angle": (30, 180, ANATOMICAL),
    "ankle_dorsiflexion_midstance": (-50, 50, ANATOMICAL),   # signed
    "ankle_plantarflexion_toeoff": (-90, 90, ANATOMICAL),    # signed
    "shank_angle_contact": (-45, 45, ANATOMICAL),            # signed
    "foot_strike_angle": (-45, 60, ANATOMICAL),              # signed; negative = forefoot
    "trunk_lean": (-10, 45, ANATOMICAL),
    "pelvic_drop": (-30, 30, ANATOMICAL),                    # signed; drop on either side
    "pronation": (-40, 40, ANATOMICAL),                      # signed
    "trunk_pelvis_rotation": (0, 45, ANATOMICAL),
    # -- literature: wide ranges, sensitivity not specificity ------------------
    "cadence": (100, 260, LITERATURE),
    "contact_time": (80, 500, LITERATURE),
    "contact_time_ms": (80, 500, LITERATURE),
    "step_time": (150, 600, LITERATURE),
    "stride_time": (300, 1200, LITERATURE),
    "swing_time": (200, 900, LITERATURE),
    "step_length": (0.3, 3.0, LITERATURE),
    "stride_length": (0.6, 6.0, LITERATURE),
    "step_length_leg_ratio": (30, 250, LITERATURE),
    "dimensionless_speed": (0.1, 4.0, LITERATURE),
    "vertical_oscillation": (2, 25, LITERATURE),
    "vertical_oscillation_cm": (2, 25, LITERATURE),
    "vertical_ratio": (2, 30, LITERATURE),
    "overstride": (-60, 60, LITERATURE),                     # signed; ankle fore/aft of hip
    "heel_recovery": (0, 100, LITERATURE),
    "arm_swing": (0, 80, LITERATURE),
    "head_drop": (0, 30, LITERATURE),
    "head_lateral_sway": (0, 30, LITERATURE),
    "lateral_trunk_sway": (0, 30, LITERATURE),
    "step_width": (-20, 60, LITERATURE),                     # signed; negative = crossover
}

# Boolean/categorical or meta outputs, which no numeric range applies to.
UNBOUNDED = frozenset({"arm_crossover", "crossover", "asymmetry"})


def check(key: str, value) -> Optional[Dict]:
    """Return a report when `value` is outside the bound for `key`, else None.

    A missing bound and a NaN both return None: absence of a bound is not evidence,
    and an uncomputed metric is already represented as NaN downstream.
    """
    bound = BOUNDS.get(key)
    if bound is None or value is None or value != value:
        return None
    low, high, basis = bound
    if low <= value <= high:
        return None
    return {
        "value": round(float(value), 3),
        "range": [low, high],
        "basis": basis,
        "message": (
            f"{value:.1f} is outside the {basis} range {low}–{high}; "
            f"treat this as a measurement problem, not a finding"
        ),
    }
