"""Top-level orchestration: PoseSequence -> AnalysisResult (JSON-ready).

Card layout, contributing keypoints, and confidence propagation are all
derived from the metric registry (gaitlab/metrics/spec.py) — to add a metric's
card or change its keypoints, edit that metric's own module under
gaitlab/metrics/definitions/; nothing here needs to change.
"""

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
from .metrics import spec as registry
from .metrics.defs import METRIC_DEFS, personalize, value_confidence
from .metrics.keys import MetricKey

_CONF_RANK = {"low": 0, "moderate": 1, "high": 2}

# Display order within a view (registration order is alphabetical by filename,
# which reads poorly in the report). Any metric not listed here still appears
# via the registry — this only controls the ordering of the "always" cards.
CARD_ORDER = {
    "side": [
        "cadence", "trunk_lean", "knee_flexion_midstance", "overstride", "hip_extension",
        "knee_drive", "vertical_oscillation", "contact_time", "duty_factor", "elbow_angle",
        "arm_swing", "heel_recovery", "flight_time", "foot_strike_angle",
    ],
    "rear": [
        "cadence", "pelvic_drop", "pronation", "step_width", "lateral_trunk_sway",
        "trunk_pelvis_rotation",
    ],
}
CONDITIONAL_ORDER = [
    "vertical_oscillation_cm", "vertical_ratio", "stride_length", "step_length",
    "head_drop", "head_lateral_sway",
]


def _ordered(defs: List, order: List[str]) -> List:
    rank = {k: i for i, k in enumerate(order)}
    return sorted(defs, key=lambda d: rank.get(d.key.value, len(order)))


def _keypoint_conf_level(seq: PoseSequence, names) -> str:
    vals = [seq.pt(f, n)[2] for f in range(seq.n) for n in names
            if seq.has(n) and seq.pt(f, n)[2] > 0]
    if not vals:
        return "low"
    m = sum(vals) / len(vals)
    return "high" if m >= 0.6 else "moderate" if m >= 0.4 else "low"


def metric_confidence(seq: PoseSequence, key: str, value, defn) -> str:
    """Final metric confidence: value-dependent tier downgraded by weak
    contributing keypoints. Returns the worse of the two levels."""
    vc = value_confidence(defn, value) if defn is not None else "moderate"
    names = registry.keypoints_map().get(key)
    if not names:
        return vc
    kl = _keypoint_conf_level(seq, names)
    return vc if _CONF_RANK[vc] <= _CONF_RANK[kl] else kl


def _foot_strike_class(angle: float) -> str:
    if angle != angle:
        return "n/a"
    if angle > 8:
        return "heel"
    if angle < -5:
        return "forefoot"
    return "midfoot"


def _card(defn, values: Dict, per_side: Dict, targets: Dict) -> Dict:
    key = defn.key.value
    t = targets.get(defn.key, defn)
    v = values.get(key)
    v = v if isinstance(v, (int, float)) else float("nan")

    if defn.key == MetricKey.FOOT_STRIKE_ANGLE:
        card = {
            "key": key, "label": "Foot strike", "unit": "deg",
            "value": v, "status": "info",
            "text": _foot_strike_class(v),
            "note": defn.note,
        }
    elif defn.card_visibility == "conditional":
        card = {"key": key, "label": defn.label, "unit": defn.unit, "value": v,
                "status": "info", "note": defn.note}
    else:
        card = {
            "key": key, "label": t.label, "unit": t.unit,
            "value": v, "status": defn.card_status or t.status(v),
            "good": list(t.good), "warn": list(t.warn), "note": t.note,
        }
    if defn.card_per_side_key and per_side:
        card["per_side"] = {
            "l": per_side.get("l", {}).get(defn.card_per_side_key),
            "r": per_side.get("r", {}).get(defn.card_per_side_key),
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

    view_str = "side" if seq.is_side() else "rear"
    always = _ordered(registry.cards_for_view(view_str), CARD_ORDER.get(view_str, []))
    cards = [_card(defn, values, per_side, targets) for defn in always]

    # calibration-derived absolutes and head-keypoint-gated metrics only appear
    # once their value is actually computed.
    conditional = _ordered(registry.conditional_cards_for_view(view_str), CONDITIONAL_ORDER)
    for defn in conditional:
        if values.get(defn.key.value) is not None:
            cards.append(_card(defn, values, per_side, targets))

    # every card carries a value-dependent, keypoint-propagated confidence
    for c in cards:
        c["confidence"] = metric_confidence(seq, c["key"], c.get("value"), targets.get(MetricKey(c["key"])))

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

    Invariants: score in [0,100], grade in A-E, every metric card is complete,
    and every feedback item has a known severity.
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
