"""Top-level orchestration: PoseSequence -> AnalysisResult (JSON-ready)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from .coaching import exercises as exercises_mod
from .coaching import feedback as fb
from .core.events import detect_events
from .core.schema import PoseSequence
from .metrics import asymmetry as asym_mod
from .metrics import compute as metrics_mod
from .metrics import quality as quality_mod
from .metrics.defs import METRIC_DEFS, personalize, value_confidence

# Contributing keypoints per metric — used to propagate tracking confidence (R5.2).
METRIC_KEYPOINTS = {
    "trunk_lean": ("mid_hip", "neck"),
    "knee_flexion_midstance": ("l_hip", "l_knee", "l_ankle", "r_hip", "r_knee", "r_ankle"),
    "overstride": ("l_hip", "l_ankle", "r_hip", "r_ankle"),
    "hip_extension": ("l_hip", "l_knee", "r_hip", "r_knee"),
    "knee_drive": ("l_hip", "l_knee", "r_hip", "r_knee"),
    "vertical_oscillation": ("mid_hip",),
    "elbow_angle": ("l_shoulder", "l_elbow", "l_wrist", "r_shoulder", "r_elbow", "r_wrist"),
    "pelvic_drop": ("l_hip", "r_hip"),
    "hip_adduction": ("l_hip", "l_knee", "r_hip", "r_knee"),
    "pronation": ("l_heel", "l_ankle", "r_heel", "r_ankle"),
    "step_width": ("l_ankle", "r_ankle", "mid_hip"),
    "lateral_trunk_sway": ("neck", "mid_hip"),
}
_CONF_RANK = {"low": 0, "moderate": 1, "high": 2}


def _keypoint_conf_level(seq: PoseSequence, names) -> str:
    vals = [seq.pt(f, n)[2] for f in range(seq.n) for n in names
            if seq.has(n) and seq.pt(f, n)[2] > 0]
    if not vals:
        return "low"
    m = sum(vals) / len(vals)
    return "high" if m >= 0.6 else "moderate" if m >= 0.4 else "low"


def metric_confidence(seq: PoseSequence, key: str, value, defn, _cache: Optional[Dict[tuple, str]] = None) -> str:
    """Final metric confidence: value-dependent tier (R3.2/R3.3) downgraded by weak
    contributing keypoints (R5.2). Returns the worse of the two levels.

    `_cache` (optional) memoizes `_keypoint_conf_level` by keypoint tuple for the
    duration of one `analyze()` call — several metrics share identical tuples (e.g.
    hip_extension/knee_drive/hip_adduction all use the same 4 hip/knee points), so
    without it the same per-frame scan repeats once per card.
    """
    vc = value_confidence(defn, value) if defn is not None else "moderate"
    names = METRIC_KEYPOINTS.get(key)
    if not names:
        return vc
    if _cache is not None and names in _cache:
        kl = _cache[names]
    else:
        kl = _keypoint_conf_level(seq, names)
        if _cache is not None:
            _cache[names] = kl
    return vc if _CONF_RANK[vc] <= _CONF_RANK[kl] else kl

SIDE_CARDS = [
    ("cadence", None),
    ("trunk_lean", None),
    ("knee_flexion_midstance", "knee_flexion_midstance"),
    ("overstride", "overstride"),
    ("hip_extension", "hip_extension"),
    ("knee_drive", "knee_drive"),
    ("vertical_oscillation", None),
    ("contact_time", "contact_time_ms"),
    ("duty_factor", "duty_factor"),
    ("elbow_angle", "elbow_angle"),
    ("arm_swing", None),
    ("heel_recovery", "heel_recovery"),
    ("flight_time", None),
    ("foot_strike_angle", None),
]
REAR_CARDS = [
    ("cadence", None),
    ("pelvic_drop", "pelvic_drop"),
    ("hip_adduction", "hip_adduction"),
    ("pronation", "pronation"),
    ("step_width", None),
    ("lateral_trunk_sway", None),
    ("trunk_pelvis_rotation", None),
]


def _foot_strike_class(angle: float) -> str:
    if angle != angle:
        return "n/a"
    if angle > 8:
        return "heel"
    if angle < -5:
        return "forefoot"
    return "midfoot"


def _card(key: str, values: Dict, per_side_key: Optional[str], per_side: Dict, targets: Dict) -> Dict:
    t = targets.get(key)
    v = values.get(key)
    v = v if isinstance(v, (int, float)) else float("nan")
    if key == "foot_strike_angle":
        card = {
            "key": key, "label": "Foot strike", "unit": "deg",
            "value": v, "status": "info",
            "text": _foot_strike_class(v),
            "note": "Where your foot first contacts: heel, midfoot, or forefoot. None is inherently bad — "
                    "it's the overstride that matters.",
        }
    elif t is None:
        units = {"arm_swing": "%leg", "heel_recovery": "%leg", "flight_time": "ms", "trunk_pelvis_rotation": "deg"}
        notes = {
            "arm_swing": "Fore-aft arm drive. Aim for relaxed, even swing front-to-back (not across the body).",
            "heel_recovery": "How much the heel picks up in swing (proxy). More recovery = a shorter, springier swing leg.",
            "flight_time": "Time both feet are off the ground per step (fps-limited estimate).",
            "trunk_pelvis_rotation": "Shoulder-vs-pelvis counter-rotation — a low-confidence 2-D rear-view proxy.",
        }
        card = {
            "key": key, "label": key.replace("_", " ").title(), "unit": units.get(key, ""),
            "value": v, "status": "info", "note": notes.get(key, ""),
        }
    else:
        card = {
            "key": key, "label": t.label, "unit": t.unit,
            "value": v, "status": t.status(v),
            "good": list(t.good), "warn": list(t.warn), "note": t.note,
        }
    if per_side_key and per_side:
        card["per_side"] = {
            "l": per_side.get("l", {}).get(per_side_key),
            "r": per_side.get("r", {}).get(per_side_key),
        }
    return card


@dataclass
class AnalysisResult:
    data: Dict

    @property
    def score(self) -> float:
        return self.data["summary"]["overall_score"]

    @property
    def grade(self) -> str:
        return self.data["summary"]["grade"]

    @property
    def cadence(self) -> float:
        return self.data["summary"]["cadence"]

    @property
    def view(self) -> str:
        return self.data["summary"]["view"]

    def to_dict(self) -> Dict:
        return _sanitize(self.data)

    def validate(self) -> "AnalysisResult":
        """Assert the (JSON-safe) output conforms to the schema; returns self."""
        validate_result(self.to_dict())
        return self


def _info_card(key, label, unit, value, note, per_side=None):
    card = {"key": key, "label": label, "unit": unit, "value": value, "status": "info", "note": note}
    if per_side:
        card["per_side"] = per_side
    return card


def analyze(seq: PoseSequence, label: str = "", profile=None) -> AnalysisResult:
    seq.validate()  # reject malformed pose input early with a clear error
    ev = detect_events(seq)
    cal = None
    if profile:
        cal = {k: profile.get(k) for k in ("height_cm", "leg_length_cm", "speed_kmh")
               if profile.get(k) is not None} or None
    targets = personalize(profile)
    m = metrics_mod.compute(seq, ev, cal)
    values = m["values"]
    per_side = m.get("per_side", {})
    asym = asym_mod.compute(per_side, targets)
    items, score, grade = fb.build(values, per_side, asym, seq.view, m["frames_of_interest"], targets)

    # _card() still uses t.label / t.unit / t.status() / t.score() / t.good / t.warn / t.note
    # MetricDef has all these, so METRIC_DEFS and personalized targets both work here.
    cards_spec = SIDE_CARDS if seq.is_side() else REAR_CARDS
    cards = [_card(k, values, psk, per_side, targets) for (k, psk) in cards_spec]

    # calibration-derived absolutes only appear when height/speed were provided
    if values.get("vertical_oscillation_cm") is not None:
        cards.append(_info_card("vertical_oscillation_cm", "Vertical oscillation", "cm",
                                values["vertical_oscillation_cm"], "Absolute hip bounce (from your height)."))
    if values.get("vertical_ratio") is not None:
        cards.append(_info_card("vertical_ratio", "Vertical ratio", "%", values["vertical_ratio"],
                                "Bounce relative to step length — lower is more economical (~6-7% is good)."))
    if values.get("stride_length") is not None:
        ps = {"l": per_side.get("l", {}).get("stride_length"), "r": per_side.get("r", {}).get("stride_length")}
        cards.append(_info_card("stride_length", "Stride length", "m", values["stride_length"],
                                "From treadmill speed × stride time.", per_side=ps))
    if values.get("step_length") is not None:
        ps = {"l": per_side.get("l", {}).get("step_length"), "r": per_side.get("r", {}).get("step_length")}
        cards.append(_info_card("step_length", "Step length", "m", values["step_length"],
                                "Distance per step (speed × step time).", per_side=ps))
    if values.get("head_drop") is not None:
        cards.append(_info_card("head_drop", "Head bobbing", "%leg", values["head_drop"],
                                "Vertical head-crown bounce per stride. Ideally tracks with hip VO; "
                                "a much higher value suggests the head is nodding independently."))
    if values.get("head_lateral_sway") is not None:
        cards.append(_info_card("head_lateral_sway", "Head lateral sway", "%leg", values["head_lateral_sway"],
                                "Side-to-side head movement per stride. Often mirrors pelvic drop; "
                                "a compensatory tilt is common when hip stabilisers are weak."))

    # R3.2/R3.3/R5.2 — every card carries a value-dependent, keypoint-propagated confidence
    _conf_cache: Dict[tuple, str] = {}
    for c in cards:
        c["confidence"] = metric_confidence(seq, c["key"], c.get("value"), targets.get(c["key"]), _conf_cache)

    events_dict = {
        "strikes": ev.strikes,
        "toeoffs": ev.toeoffs,
        "stance": {s: [list(iv) for iv in ev.stance[s]] for s in ("l", "r")},
        "cadence": ev.cadence_spm,
        "stride_time": ev.stride_time,
        "contact_time": ev.contact_time,
    }

    data = {
        "summary": {
            "label": label,
            "view": seq.view,
            "source": seq.source,
            "fps": seq.fps,
            "duration": round(seq.duration, 2),
            "n_frames": seq.n,
            "cadence": values.get("cadence"),
            "overall_score": score,
            "grade": grade,
            "n_findings": sum(1 for i in items if i["severity"] in ("high", "med")),
            "profile": profile or None,
        },
        "metrics": cards,
        "asymmetry": asym,
        "feedback": items,
        "plan": exercises_mod.build_plan(items),
        "quality": quality_mod.assess(seq, ev),
        "events": events_dict,
        "series": m["series"],
        "frames_of_interest": m["frames_of_interest"],
        "leg_length": m["leg_length"],
        "pose": seq.to_pose_dict(),
    }
    return AnalysisResult(data)


GRADES = {"A", "B", "C", "D", "E"}
SEVERITIES = {"high", "med", "low", "good"}
CARD_STATUSES = {"good", "warn", "bad", "info"}


class ResultValidationError(ValueError):
    """Raised when an AnalysisResult does not conform to the output schema."""


def validate_result(data: Dict) -> Dict:
    """Assert the analysis output conforms to the declared schema; raise on violation.

    Invariants (tech_requirements.md §16-§18): score in [0,100], grade in A-E, every
    metric card is complete, and every feedback item has a known severity.
    """
    errs: List[str] = []
    s = data.get("summary")
    if not isinstance(s, dict):
        raise ResultValidationError("missing summary")
    score = s.get("overall_score")
    if not isinstance(score, (int, float)) or not (0 <= score <= 100):
        errs.append(f"overall_score {score!r} not in [0,100]")
    if s.get("grade") not in GRADES:
        errs.append(f"grade {s.get('grade')!r} not in {GRADES}")
    if s.get("view") not in ("side-left", "side-right", "rear", "front"):
        errs.append(f"view {s.get('view')!r} invalid")

    for c in data.get("metrics", []):
        for req in ("key", "label", "unit", "value", "status"):
            if req not in c:
                errs.append(f"metric card {c.get('key')!r} missing '{req}'")
        if c.get("status") not in CARD_STATUSES:
            errs.append(f"metric card {c.get('key')!r} bad status {c.get('status')!r}")
        v = c.get("value")
        if v is not None and not isinstance(v, (int, float)):
            errs.append(f"metric card {c.get('key')!r} value not numeric/None: {v!r}")

    for it in data.get("feedback", []):
        if it.get("severity") not in SEVERITIES:
            errs.append(f"feedback item bad severity {it.get('severity')!r}")

    if errs:
        raise ResultValidationError("; ".join(errs))
    return data


def _sanitize(obj):
    """Make a structure strictly JSON-safe: NaN/inf -> None, tuples -> lists, round floats."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return round(obj, 3)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj
