"""Per-metric confidence: value-dependent (R3.2/R3.3) + keypoint propagation (R5.2)."""

from __future__ import annotations

import pytest

from gaitlab.analyze import analyze, metric_confidence
from gaitlab.core.schema import KEYPOINTS, PoseSequence
from gaitlab.metrics.defs import METRIC_DEFS, value_confidence
from gaitlab.metrics.keys import MetricKey


@pytest.mark.covers("R3.3")
def test_pelvic_drop_confidence_is_value_dependent():
    d = METRIC_DEFS[MetricKey.PELVIC_DROP]
    assert value_confidence(d, 3.0) == "low"        # near the ±4 deg noise floor
    assert value_confidence(d, 5.0) == "moderate"
    assert value_confidence(d, 8.0) == "high"       # clears the floor


@pytest.mark.covers("R3.3")
def test_pronation_stays_low_regardless():
    d = METRIC_DEFS[MetricKey.PRONATION]
    assert value_confidence(d, 2.0) == "low"
    assert value_confidence(d, 15.0) == "low"


def test_non_tier_c_uses_base_confidence():
    assert value_confidence(METRIC_DEFS[MetricKey.CADENCE], 999) == "high"
    assert value_confidence(METRIC_DEFS[MetricKey.CADENCE], float("nan")) == "low"


def _rear_pose_with_hip_conf(conf: float, n: int = 8) -> PoseSequence:
    frames = []
    for i in range(n):
        fr = [(0.0, 0.0, 0.0)] * len(KEYPOINTS)
        fr[KEYPOINTS.index("l_hip")] = (100.0, 500.0 + i, conf)
        fr[KEYPOINTS.index("r_hip")] = (200.0, 500.0 - i, conf)
        fr[KEYPOINTS.index("mid_hip")] = (150.0, 500.0, conf)
        frames.append(fr)
    return PoseSequence(fps=60, width=1080, height=1920, view="rear", frames=frames, source="test")


@pytest.mark.covers("R5.2")
def test_low_keypoint_confidence_downgrades_metric():
    d = METRIC_DEFS[MetricKey.PELVIC_DROP]
    high = _rear_pose_with_hip_conf(0.95)
    low = _rear_pose_with_hip_conf(0.2)
    # value 8 alone would be "high"; weak hip keypoints drag it down
    assert metric_confidence(high, "pelvic_drop", 8.0, d) == "high"
    assert metric_confidence(low, "pelvic_drop", 8.0, d) == "low"


@pytest.mark.covers("R3.2")
def test_every_card_has_confidence(synth, golden_pose):
    for seq in (synth("side-left", fps=60, duration=6, cadence=176, seed=1), golden_pose):
        cards = analyze(seq).to_dict()["metrics"]
        assert cards and all(c.get("confidence") in ("low", "moderate", "high") for c in cards)
