"""Physiological plausibility bounds — engineering sanity, not a verdict.

The bounds only earn their place if they are silent on every clip we believe is good
and loud on output a running human cannot produce. Both directions are pinned here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaitlab import synthetic
from gaitlab.analyze import analyze
from gaitlab.core.schema import PoseSequence
from gaitlab.metrics import plausibility
from gaitlab.metrics.defs import METRIC_DEFS

REAL_POSE = Path(__file__).parent / "data" / "male_side.pose.json"
REAL_PROFILE = {
    "height_cm": 178, "age_years": 35, "body_mass_kg": 72,
    "speed_kmh": 12.0, "sex": "male", "leg_length_cm": 88,
}


def _every_clip():
    clips = []
    if REAL_POSE.exists():
        seq = PoseSequence.from_pose_dict(json.loads(REAL_POSE.read_text())).validate()
        clips.append(("real side clip", seq, REAL_PROFILE))
    clips += [(label, seq, profile) for label, seq, profile in synthetic.demo_runs()]
    return clips


def test_every_registered_metric_is_bounded_or_explicitly_exempt():
    """A new metric must make a deliberate choice, not inherit silence by default."""
    registered = {key.value for key in METRIC_DEFS}
    covered = set(plausibility.BOUNDS) | set(plausibility.UNBOUNDED)
    assert registered - covered == set(), "metrics with no plausibility decision"
    assert covered - registered == set(), "bounds for metrics that no longer exist"


def test_no_bound_fires_on_any_clip_we_believe_is_good():
    """The false-positive guard. A sanity check that cries wolf gets ignored, and
    then it is not a sanity check."""
    offenders = []
    for label, seq, profile in _every_clip():
        for card in analyze(seq, label=label, profile=profile).to_dict()["metrics"]:
            if "plausibility" in card:
                offenders.append(f"{label}: {card['key']} = {card['plausibility']['value']} "
                                 f"outside {card['plausibility']['range']}")
    assert offenders == [], "plausibility bounds fired on good data:\n" + "\n".join(offenders)


def test_signed_metrics_have_symmetric_bounds():
    """These legitimately go negative on real footage — overstride reads about -23 %leg
    on the synthetic clip, where the ankle lands behind the hip. A one-sided bound on
    any of them is a false-positive generator, which is how the first draft failed."""
    for key in ("overstride", "pelvic_drop", "ankle_plantarflexion_toeoff",
                "shank_angle_contact", "ankle_dorsiflexion_midstance", "step_width"):
        low, high, _ = plausibility.BOUNDS[key]
        assert low < 0, f"{key} is signed but its lower bound is {low}"
        assert high > 0


def test_the_anchoring_regression_would_have_been_caught():
    """The gait-event anchoring bug reported 67 ms contact and 10.5% duty with high
    event confidence and an empty warning list. This is the check that would have
    surfaced it in the report rather than only in an integration test."""
    assert plausibility.check("duty_factor", 10.5)["basis"] == "definitional"
    assert plausibility.check("contact_time", 67.0)["basis"] == "literature"


@pytest.mark.parametrize("key,value", [
    ("duty_factor", 55.0),          # >=50% is walking, by definition
    ("flight_time", 0.0),           # no flight phase is not running
    ("knee_flexion_peak", 200.0),   # exceeds knee range of motion
    ("cadence", 60.0),              # no human runs this slow a step rate
    ("elbow_angle", 200.0),         # exceeds elbow range of motion
])
def test_impossible_values_are_flagged(key, value):
    report = plausibility.check(key, value)
    assert report is not None, f"{key}={value} should be implausible"
    assert report["basis"] in {"definitional", "anatomical", "literature"}


def test_missing_and_uncomputed_values_are_not_flagged():
    """Absence of a bound is not evidence, and NaN already means 'not computed'."""
    assert plausibility.check("cadence", None) is None
    assert plausibility.check("cadence", float("nan")) is None
    assert plausibility.check("arm_crossover", 999) is None


def test_an_implausible_metric_reaches_the_quality_panel():
    """The card annotation is machine-readable; this is the part a person sees."""
    from gaitlab.metrics import quality
    seq = synthetic.demo_runs()[0][1]
    from gaitlab.core.events import detect_events
    checks = quality.assess(seq, detect_events(seq), implausible=["duty_factor"])
    messages = [c["message"] for c in checks if c["level"] == "warn"]
    assert any("Outside the physiological range" in m and "duty_factor" in m for m in messages)
