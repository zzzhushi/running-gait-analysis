"""Top-level orchestration: PoseSequence -> AnalysisResult (JSON-ready).

Card layout, contributing keypoints, and confidence propagation are all
derived from the metric registry (gaitlab/metrics/spec.py) — to add a metric's
card or change its keypoints, edit that metric's own module under
gaitlab/metrics/definitions/; nothing here needs to change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, median, stdev
from typing import Dict, List, Optional

from .coaching import exercises as exercises_mod
from .coaching import feedback as fb
from .core.events import detect_events
from .core.profile import RunnerProfile
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
        "cadence", "trunk_lean", "knee_flexion_contact", "knee_flexion_midstance", "overstride", "hip_extension",
        "hip_flexion_peak", "knee_flexion_peak", "knee_flexion_excursion",
        "ankle_dorsiflexion_midstance", "ankle_plantarflexion_toeoff", "shank_angle_contact",
        "vertical_oscillation", "contact_time", "step_time", "stride_time", "swing_time",
        "duty_factor", "elbow_angle",
        "arm_swing", "heel_recovery", "flight_time", "foot_strike_angle",
    ],
    "rear": [
        "cadence", "pelvic_drop", "pronation", "step_width", "lateral_trunk_sway",
        "trunk_pelvis_rotation", "crossover", "arm_crossover",
    ],
}
CONDITIONAL_ORDER = [
    "vertical_oscillation_cm", "vertical_ratio", "stride_length", "step_length",
    "step_length_leg_ratio", "dimensionless_speed", "cadence_cv", "contact_time_cv",
    "head_drop", "head_lateral_sway",
]


def _ordered(defs: List, order: List[str]) -> List:
    rank = {k: i for i, k in enumerate(order)}
    return sorted(defs, key=lambda d: rank.get(d.key.value, len(order)))


def _metric_frames(seq: PoseSequence, ev, phase: str) -> List[int]:
    if phase == "strike":
        return sorted(ev.strikes["l"] + ev.strikes["r"])
    if phase == "midstance":
        return sorted(ev.midstance("l") + ev.midstance("r"))
    if phase == "toeoff":
        return sorted(ev.toeoffs["l"] + ev.toeoffs["r"])
    if phase == "events":
        return ev.event_frames()
    return list(range(seq.n))


def _keypoint_conf_detail(seq: PoseSequence, names, frames: List[int]) -> Dict:
    vals = [min(1.0, seq.pt(f, name)[2]) for f in frames for name in names if seq.has(name)]
    if not vals:
        return {"level": "low", "mean": 0.0, "coverage": 0.0}
    visible = [value for value in vals if value >= 0.35]
    coverage = len(visible) / len(vals)
    mean_conf = sum(vals) / len(vals)
    level = "high" if mean_conf >= 0.75 and coverage >= 0.9 else "moderate" if mean_conf >= 0.5 and coverage >= 0.75 else "low"
    return {"level": level, "mean": round(mean_conf, 3), "coverage": round(coverage, 3)}


def metric_confidence_detail(seq: PoseSequence, key: str, value, defn, ev=None) -> Dict:
    """Final metric confidence: value-dependent tier downgraded by weak
    contributing keypoints. Returns the worse of the two levels."""
    vc = value_confidence(defn, value) if defn is not None else "moderate"
    names = registry.keypoints_map().get(key, ())
    frames = _metric_frames(seq, ev, defn.event_phase) if ev is not None else list(range(seq.n))
    tracking = _keypoint_conf_detail(seq, names, frames) if names else {"level": "moderate", "mean": None, "coverage": None}
    levels = [vc, tracking["level"]]
    if ev is not None and (defn.event_phase != "all" or defn.requires_events):
        levels.append(ev.confidence)
    timing_keys = {"contact_time", "contact_time_ms", "flight_time", "duty_factor", "swing_time", "contact_time_cv"}
    protocol = "low" if key in timing_keys and seq.effective_fps < 120 else "moderate"
    levels.append(protocol)
    final = min(levels, key=lambda level: _CONF_RANK[level])
    return {
        "level": final,
        "measurement": vc,
        "tracking": tracking,
        "event_detection": ev.confidence if ev is not None and (defn.event_phase != "all" or defn.requires_events) else None,
        "protocol": protocol,
        "sample_count": len(frames),
    }


def metric_confidence(seq: PoseSequence, key: str, value, defn, ev=None) -> str:
    return metric_confidence_detail(seq, key, value, defn, ev)["level"]


def _central_samples(values: List[float], tolerance: float = 0.25) -> List[float]:
    """Exclude incomplete-clip/event-detector edge intervals from variability summaries."""
    values = [v for v in values if math.isfinite(v) and v > 0]
    if len(values) < 3:
        return values
    center = median(values)
    return [v for v in values if center * (1 - tolerance) <= v <= center * (1 + tolerance)]


def _metric_samples(key: str, computed: Dict, ev, seq: PoseSequence) -> List[float]:
    temporal = {
        "contact_time": [v * 1000.0 for side in ("l", "r") for v in ev.contact_times[side]],
        "contact_time_ms": [v * 1000.0 for side in ("l", "r") for v in ev.contact_times[side]],
        "step_time": [v * 1000.0 for side in ("l", "r") for v in ev.step_times[side]],
        "stride_time": [v * 1000.0 for side in ("l", "r") for v in ev.stride_times[side]],
        "flight_time": [v * 1000.0 for side in ("l", "r") for v in ev.flight_times[side]],
    }
    if key == "swing_time":
        swings = []
        for side in ("l", "r"):
            for strike, toeoff in ev.stance[side]:
                later = [frame for frame in ev.strikes[side] if frame > strike]
                if later:
                    swings.append(seq.elapsed(toeoff, later[0]) * 1000.0)
        return swings
    if key == "cadence":
        strikes = sorted(ev.strikes["l"] + ev.strikes["r"])
        intervals = _central_samples([seq.elapsed(a, b) for a, b in zip(strikes, strikes[1:]) if b > a])
        return [60.0 / value for value in intervals]
    if key in temporal:
        return _central_samples(temporal[key])
    return [
        row[key] for row in computed.get("stride_observations", [])
        if isinstance(row.get(key), (int, float)) and math.isfinite(row[key])
    ]


def _sample_statistics(samples: List[float]) -> Optional[Dict]:
    samples = [v for v in samples if math.isfinite(v)]
    if not samples:
        return None
    result = {"n": len(samples)}
    if len(samples) >= 3:
        avg = mean(samples)
        half = 1.96 * stdev(samples) / math.sqrt(len(samples))
        result.update({
            "mean": round(avg, 3),
            "ci95_mean": [round(avg - half, 3), round(avg + half, 3)],
            "method": "normal-approximation CI across detected events/strides",
        })
    return result


def _foot_strike_class(angle: float) -> str:
    if angle != angle:
        return "n/a"
    if angle > 8:
        return "rearfoot"
    if angle < -1.6:
        return "forefoot"
    return "midfoot"


def _card(defn, values: Dict, per_side: Dict, targets: Dict, profile=None) -> Dict:
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
    else:
        card = {
            "key": key, "label": t.label, "unit": t.unit,
            "value": v, "status": "info", "note": t.note,
        }
    if defn.is_boolean:
        card["is_boolean"] = True
        card["text"] = "observed" if bool(v) else "not observed"
    card["evidence_level"] = defn.evidence_level
    card["interpretation"] = defn.interpretation
    reference = defn.reference(profile)
    if reference:
        card["reference"] = reference
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
    def score(self) -> Optional[float]:
        return self.data["summary"]["overall_score"]

    @property
    def grade(self) -> Optional[str]:
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
    # Filtering (from the metric-correctness work) happens before detection so events
    # and metrics see the same series; the typed profile (from #44) is resolved once
    # here so nothing downstream has to know which form the caller sent.
    analysis_seq = seq.filtered_for_analysis()
    ev = detect_events(analysis_seq)
    # The raw input is kept for the summary echo below — callers (notably
    # POST /api/analyze) may send keys the engine doesn't model, and those are
    # reported back verbatim.
    runner = profile if isinstance(profile, RunnerProfile) else RunnerProfile.from_dict(profile)
    targets = personalize(runner)
    m = metrics_mod.compute(analysis_seq, ev, runner)
    values = m["values"]
    per_side = m.get("per_side", {})

    view_str = "side" if seq.is_side() else "rear"
    always = _ordered(registry.cards_for_view(view_str), CARD_ORDER.get(view_str, []))
    cards = [_card(defn, values, per_side, targets, profile) for defn in always]

    # calibration-derived absolutes and head-keypoint-gated metrics only appear
    # once their value is actually computed.
    conditional = _ordered(registry.conditional_cards_for_view(view_str), CONDITIONAL_ORDER)
    for defn in conditional:
        if values.get(defn.key.value) is not None:
            cards.append(_card(defn, values, per_side, targets, profile))

    # every card carries a value-dependent, keypoint-propagated confidence
    confidence_map = {}
    for c in cards:
        defn = targets.get(MetricKey(c["key"]))
        detail = metric_confidence_detail(seq, c["key"], c.get("value"), defn, ev)
        c["confidence"] = detail["level"]
        c["confidence_detail"] = detail
        statistics = _sample_statistics(_metric_samples(c["key"], m, ev, analysis_seq))
        if statistics:
            c["statistics"] = statistics
        confidence_map[c["key"]] = detail["level"]

    for defn in registry.asym_metrics():
        key = defn.key.value
        if key in confidence_map:
            continue
        detail = metric_confidence_detail(seq, key, values.get(key), defn, ev)
        confidence_map[key] = detail["level"]

    asym = asym_mod.compute(per_side, confidence_map)
    items, score, grade = fb.build(
        values, per_side, asym, seq.view, m["frames_of_interest"], targets,
        observations=m.get("stride_observations"), confidences=confidence_map,
    )

    events_dict = {
        "strikes": ev.strikes,
        "toeoffs": ev.toeoffs,
        "stance": {s: [list(iv) for iv in ev.stance[s]] for s in ("l", "r")},
        "cadence": ev.cadence_spm,
        "stride_time": ev.stride_time,
        "contact_time": ev.contact_time,
        "step_time": ev.step_time,
        "flight_time": ev.flight_time,
        "duty_factor": ev.duty_factor,
        "sample_count": ev.sample_count,
        "alternation_ratio": ev.alternation_ratio,
        "confidence": ev.confidence,
        "warnings": ev.warnings,
    }

    data = {
        "summary": {
            "label": label,
            "view": seq.view,
            "source": seq.source,
            "fps": seq.fps,
            "effective_fps": round(seq.effective_fps, 3),
            "duration": round(seq.duration, 2),
            "n_frames": seq.n,
            "cadence": values.get("cadence"),
            "overall_score": score,
            "grade": grade,
            "analysis_mode": "descriptive_research",
            "score_status": "disabled_unvalidated",
            "n_findings": sum(1 for i in items if i["severity"] in ("high", "med")),
            # Echo what the caller sent. A dict passes through untouched (extra
            # keys included); a RunnerProfile is rendered back to the sparse wire
            # form so the output shape is identical either way.
            "profile": (profile.to_dict() or None) if isinstance(profile, RunnerProfile) else (profile or None),
        },
        "metrics": cards,
        "asymmetry": asym,
        "feedback": items,
        "plan": exercises_mod.build_plan(items),
        "quality": quality_mod.assess(analysis_seq, ev),
        "events": events_dict,
        "series": m["series"],
        "frames_of_interest": m["frames_of_interest"],
        "leg_length": m["leg_length"],
        "pose": seq.to_pose_dict(),
    }
    return AnalysisResult(data)


SEVERITIES = {"high", "med", "low", "good"}
CARD_STATUSES = {"good", "warn", "bad", "info"}


class ResultValidationError(ValueError):
    """Raised when an AnalysisResult does not conform to the output schema."""


def validate_result(data: Dict) -> Dict:
    """Assert the analysis output conforms to the declared schema; raise on violation.

    Invariants: unvalidated score/grade stay disabled, every metric card is
    complete, and every feedback item has a known severity.
    """
    errs: List[str] = []
    s = data.get("summary")
    if not isinstance(s, dict):
        raise ResultValidationError("missing summary")
    score = s.get("overall_score")
    if score is not None:
        errs.append(f"overall_score must be disabled (got {score!r})")
    if s.get("grade") is not None:
        errs.append(f"grade must be disabled (got {s.get('grade')!r})")
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
