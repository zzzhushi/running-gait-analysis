"""Metric confidence combines evidence, tracking, events, and protocol."""

from gaitlab.analyze import analyze, metric_confidence_detail
from gaitlab.core.events import GaitEvents
from gaitlab.core.schema import KEYPOINTS, PoseSequence
from gaitlab.metrics.defs import METRIC_DEFS, value_confidence
from gaitlab.metrics.keys import MetricKey


def _rear_pose_with_hip_conf(conf: float, n: int = 8) -> PoseSequence:
    frames = []
    for i in range(n):
        frame = [(0.0, 0.0, 0.0)] * len(KEYPOINTS)
        frame[KEYPOINTS.index("l_hip")] = (100.0, 500.0 + i, conf)
        frame[KEYPOINTS.index("r_hip")] = (200.0, 500.0 - i, conf)
        frame[KEYPOINTS.index("mid_hip")] = (150.0, 500.0, conf)
        frames.append(frame)
    return PoseSequence(fps=60, width=1080, height=1920, view="rear", frames=frames, source="test")


def test_measurement_tiers_are_not_promoted_by_large_values():
    assert value_confidence(METRIC_DEFS[MetricKey.PELVIC_DROP], 20) == "low"
    assert value_confidence(METRIC_DEFS[MetricKey.PRONATION], 20) == "low"
    assert value_confidence(METRIC_DEFS[MetricKey.CADENCE], 180) == "moderate"


def test_tracking_downgrades_but_cannot_promote_measurement():
    definition = METRIC_DEFS[MetricKey.PELVIC_DROP]
    high = metric_confidence_detail(_rear_pose_with_hip_conf(0.95), "pelvic_drop", 8.0, definition)
    low = metric_confidence_detail(_rear_pose_with_hip_conf(0.2), "pelvic_drop", 8.0, definition)
    assert high["level"] == "low"  # measurement-validity tier is low
    assert low["tracking"]["level"] == "low"
    assert low["level"] == "low"


def test_every_card_exposes_confidence_components(synth):
    cards = analyze(synth("side-left", duration=6, cadence=176)).to_dict()["metrics"]
    assert cards
    for card in cards:
        assert card["confidence"] in ("low", "moderate", "high")
        assert {"measurement", "tracking", "event_detection", "protocol", "sample_count"} <= set(card["confidence_detail"])
        assert card["confidence"] != "high"  # capped pending criterion validation


def test_all_frame_metric_that_uses_stride_boundaries_inherits_event_confidence(synth):
    seq = synth("side-left", duration=6, cadence=176)
    events = GaitEvents(confidence="low")
    definition = METRIC_DEFS[MetricKey.VERTICAL_OSCILLATION]
    detail = metric_confidence_detail(
        seq, "vertical_oscillation", 11.0, definition, events
    )
    assert definition.event_phase == "all"
    assert definition.requires_events is True
    assert detail["event_detection"] == "low"
    assert detail["level"] == "low"
