"""Loading and assertion helpers shared by the real-clip tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

DATA = Path(__file__).resolve().parents[1] / "data"

# How precisely each metric can be known, in percent. A property of the metric rather than of
# any clip, so it lives here; a clip overrides it only when its own measurement is looser.
TOLERANCE_PCT: Dict[str, float] = {
    "cadence_spm": 2.0,
    "duration_s": 0.5,
    "contact_time": 15.0,
    "duty_factor": 15.0,
    "overstride": 25.0,
    "vertical_oscillation": 15.0,
}

# Metrics the engine reports that no clip asserts yet, with the reason. A metric in neither
# this set nor some clip's record fails test_every_metric_is_validated_or_listed.
UNVALIDATED: Dict[str, str] = {
    # Needs a second 120 fps clip with contact measured from pixels; one point cannot
    # separate a wrong model from an uncalibrated one.
    "contact_time": "one measured clip",
    "contact_time_ms": "one measured clip",
    "duty_factor": "derived from contact_time",
    "flight_time": "derived from contact_time",
    # Measured by eye on one clip, to about 25%.
    "overstride": "one clip, read by eye",
    "vertical_oscillation": "one clip",
    "vertical_oscillation_cm": "one clip, and needs a pixel scale",
    "cadence": "asserted as cadence_spm",
}
# Everything the engine reports that has no pixel measurement at all. Separated from
# UNVALIDATED so the list above stays short enough to shrink.
UNMEASURED = {
    "arm_crossover", "arm_swing", "asymmetry", "crossover", "elbow_angle",
    "foot_strike_angle", "head_drop", "head_lateral_sway", "heel_recovery",
    "hip_extension", "knee_drive", "knee_flexion_contact", "knee_flexion_midstance",
    "lateral_trunk_sway", "pelvic_drop", "pronation", "step_length", "step_width",
    "stride_length", "trunk_lean", "trunk_pelvis_rotation", "vertical_ratio",
}


# Extractors a clip may carry a pose fixture for, and how much slack each needs beyond the
# per-metric tolerance. BlazePose has 4 foot keypoints to RTMPose's 6 and no small toe, so it
# is expected to be looser; the multiplier records that rather than hiding it.
EXTRACTORS = {"rtmpose": 1.0, "blazepose": 2.0}


@dataclass(frozen=True)
class Clip:
    """One ground-truth record plus the pose fixture for one extractor."""
    name: str
    record: Dict[str, Any]
    pose_path: Path
    extractor: str = "rtmpose"

    @property
    def id(self) -> str:
        return f"{self.name}-{self.extractor}"

    @property
    def metrics(self) -> Dict[str, Any]:
        return self.record.get("metrics", {})

    @property
    def composites(self) -> Dict[str, bool]:
        return self.record.get("composites", {})

    def tolerance(self, key: str) -> float:
        override = self.record.get("tolerance_pct", {}).get(key)
        if override is None and key not in TOLERANCE_PCT:
            raise AssertionError(
                f"{self.name}: no tolerance for {key!r}. Add one to TOLERANCE_PCT, or a "
                f"tolerance_pct override on the clip. Defaulting silently would let a "
                f"mistyped key assert nothing."
            )
        base = override if override is not None else TOLERANCE_PCT[key]
        return float(base) * EXTRACTORS[self.extractor]

    def subject(self) -> Dict[str, Any]:
        subjects = json.loads((DATA / "subjects.json").read_text())
        return subjects[self.record["subject"]]


def _records() -> List[Path]:
    return sorted(p for p in DATA.glob("*.groundtruth.json"))


def load_clips(extractors=None) -> List[Clip]:
    """Every (clip, extractor) pair whose pose fixture is present."""
    out = []
    for path in _records():
        record = json.loads(path.read_text())
        stem = path.name[: -len(".groundtruth.json")]
        for extractor in (extractors or EXTRACTORS):
            pose = DATA / f"{stem}.{extractor}.pose.json"
            if pose.exists():
                out.append(Clip(stem, record, pose, extractor))
    return out


def analyse(clip: Clip) -> Dict[str, Any]:
    """Run the engine over a clip's pose fixture and flatten the report."""
    from gaitlab.analyze import analyze
    from gaitlab.core.schema import PoseSequence

    seq = PoseSequence.from_pose_dict(json.loads(clip.pose_path.read_text())).validate()
    assert seq.view == clip.record["view"], (
        f"{clip.id}: pose fixture says view {seq.view!r}, record says "
        f"{clip.record['view']!r}"
    )
    result = analyze(seq, label=clip.name).to_dict()
    flat = {m["key"]: m["value"] for m in result["metrics"]}
    flat["cadence_spm"] = result["summary"]["cadence"]
    flat["duration_s"] = seq.duration
    from gaitlab.core.events import detect_events

    events = detect_events(seq)
    flat["_strikes"] = {side: len(frames) for side, frames in events.strikes.items()}
    flat["_findings"] = {f["key"] for f in result.get("findings", [])}
    flat["_quality"] = result.get("quality", [])
    return flat


def check(clip: Clip, key: str, expected: Any, actual: float) -> None:
    """Assert one metric, against a bound or against a value within tolerance."""
    if isinstance(expected, dict):
        lo, hi = expected.get("min"), expected.get("max")
        if lo is not None:
            assert actual >= lo, f"{clip.id}: {key} is {actual:.2f}, expected at least {lo}"
        if hi is not None:
            assert actual <= hi, f"{clip.id}: {key} is {actual:.2f}, expected at most {hi}"
        return
    tol = clip.tolerance(key)
    err = abs(actual - expected) / expected * 100 if expected else abs(actual - expected)
    assert err <= tol, (
        f"{clip.id}: {key} is {actual:.2f}, measured truth is {expected} "
        f"({err:.1f}% off, tolerance {tol}%)"
    )
