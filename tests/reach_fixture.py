"""Loader and diagnostic records for the authored stage-3 reach fixture.

This remains test support. The debug serialization and rendering modules under gaitlab/debug
and scripts/ consume the same language-neutral JSON rather than recreating the geometry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from gaitlab.core.reach import Denominator, ReachSample
from gaitlab.core.schema import KEYPOINTS, PoseSequence

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "overstride_stage3.json"


@dataclass(frozen=True)
class AuthoredReachFixture:
    name: str
    sequence: PoseSequence
    side: str
    facing: int
    denominator: Denominator
    forced_strikes: Dict[str, List[int]]
    hand_computed_anchor_frames: List[int]
    expected_metric_pct: float
    frames: List[Dict[str, Any]]
    does_not_validate: List[str]


def load_authored_reach_fixture() -> AuthoredReachFixture:
    raw = json.loads(FIXTURE_PATH.read_text())
    pose = raw["pose"]
    measurement = raw["measurement"]
    frames = []
    timestamps = []

    for authored in raw["frames"]:
        frame = [(0.0, 0.0, 0.0)] * len(KEYPOINTS)
        for name, point in authored["points"].items():
            frame[KEYPOINTS.index(name)] = tuple(float(value) for value in point)
        frames.append(frame)
        timestamps.append(float(authored["timestamp"]))

    sequence = PoseSequence(
        fps=float(pose["fps"]),
        width=int(pose["width"]),
        height=int(pose["height"]),
        view=pose["view"],
        frames=frames,
        timestamps=timestamps,
        source=f"authored:{raw['name']}",
    ).validate()
    denominator = measurement["denominator"]

    return AuthoredReachFixture(
        name=raw["name"],
        sequence=sequence,
        side=measurement["side"],
        facing=int(measurement["facing"]),
        denominator=Denominator.injected(
            float(denominator["px"]), method=denominator["method"]),
        forced_strikes={
            side: [int(frame) for frame in indices]
            for side, indices in measurement["forced_strikes"].items()
        },
        hand_computed_anchor_frames=[
            int(frame) for frame in measurement["hand_computed_anchor_frames"]
        ],
        expected_metric_pct=float(measurement["expected_metric_pct"]),
        frames=raw["frames"],
        does_not_validate=list(raw["does_not_validate"]),
    )


def actual_trace_record(sample: ReachSample) -> Dict[str, Any]:
    """Serialize only the formula-slice fields, directly from the computed sample."""
    def reading(value):
        return {
            "px": value.px,
            "pct": value.pct,
            "px_unavailable": value.px_unavailable,
            "pct_unavailable": value.pct_unavailable,
        }

    return {
        "frame": sample.frame,
        "timestamp": sample.t,
        "side": sample.side,
        "facing": sample.facing,
        "processing": sample.processing,
        "points": {
            "hip": list(sample.hip),
            "ankle": list(sample.ankle),
            "heel": list(sample.heel),
            "toe": list(sample.toe),
        },
        "denominator": {
            "px": sample.denominator.px,
            "method": sample.denominator.method,
        },
        "ankle_reach": reading(sample.ankle_reach),
        "heel_reach": reading(sample.heel_reach),
        "toe_reach": reading(sample.toe_reach),
        "midpoint_reach": reading(sample.midpoint_reach),
        "foot_midpoint_proxy": list(sample.foot_midpoint_proxy),
        "inclination_deg": sample.inclination_deg,
        "inclination_unavailable": sample.inclination_unavailable,
    }


def expected_trace_record(case: AuthoredReachFixture, frame: int) -> Dict[str, Any]:
    """Expand the independently authored expectation into the diagnostic record shape."""
    authored = case.frames[frame]
    points = authored["points"]
    expected = authored["expected"]

    def reading(name):
        return {
            **expected[name],
            "px_unavailable": None,
            "pct_unavailable": None,
        }

    return {
        "frame": frame,
        "timestamp": authored["timestamp"],
        "side": case.side,
        "facing": case.facing,
        "processing": "raw",
        "points": {
            "hip": points[f"{case.side}_hip"],
            "ankle": points[f"{case.side}_ankle"],
            "heel": points[f"{case.side}_heel"],
            "toe": points[f"{case.side}_big_toe"],
        },
        "denominator": {
            "px": case.denominator.px,
            "method": case.denominator.method,
        },
        "ankle_reach": reading("ankle_reach"),
        "heel_reach": reading("heel_reach"),
        "toe_reach": reading("toe_reach"),
        "midpoint_reach": reading("midpoint_reach"),
        "foot_midpoint_proxy": expected["foot_midpoint_proxy"],
        "inclination_deg": expected["inclination_deg"],
        "inclination_unavailable": None,
    }


def format_trace_failure(name: str, expected: Dict[str, Any], actual: Dict[str, Any]) -> str:
    return (
        f"authored reach trace mismatch for {name}\n"
        f"expected:\n{json.dumps(expected, indent=2, sort_keys=True)}\n"
        f"actual:\n{json.dumps(actual, indent=2, sort_keys=True)}"
    )
