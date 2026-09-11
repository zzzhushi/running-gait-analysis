"""Regression tests for the evidence-led measurement contract."""

import math
import re
from pathlib import Path

import pytest

from gaitlab import analyze, synthetic
from gaitlab.core.events import detect_events
from gaitlab.core.schema import KEYPOINTS, PoseSequence, PoseValidationError
from gaitlab.metrics.defs import METRIC_DEFS
from scripts.evaluate_validation import summarize


def _blank_sequence(n=8, fps=60, timestamps=None):
    frames = [[(0.0, 0.0, 0.0) for _ in KEYPOINTS] for _ in range(n)]
    return PoseSequence(fps=fps, width=100, height=100, view="side-left",
                        frames=frames, timestamps=timestamps, source="test")


def test_timestamps_drive_event_time_instead_of_nominal_fps():
    base = synthetic.generate("side-left", fps=60, duration=6, cadence=172)
    nominal = detect_events(base).cadence_spm
    base.timestamps = [i / 30 for i in range(base.n)]
    timestamped = detect_events(base).cadence_spm
    assert timestamped == pytest.approx(nominal / 2, rel=0.02)
    assert base.duration == pytest.approx(12.0)


def test_timestamps_drive_protocol_frame_rate():
    seq = synthetic.generate("side-left", fps=60, duration=6, cadence=172)
    seq.timestamps = [i / 240 for i in range(seq.n)]
    result = analyze(seq).to_dict()
    contact = next(card for card in result["metrics"] if card["key"] == "contact_time")
    assert result["summary"]["effective_fps"] == pytest.approx(240)
    assert contact["confidence_detail"]["protocol"] == "moderate"


def test_timestamp_validation_rejects_nonfinite_or_nonincreasing():
    with pytest.raises(PoseValidationError, match="timestamps has"):
        PoseSequence.from_pose_dict(_blank_sequence(4).to_pose_dict() | {"timestamps": []}).validate()
    with pytest.raises(PoseValidationError, match="finite"):
        _blank_sequence(4, timestamps=[0.0, 0.1, float("nan"), 0.3]).validate()
    with pytest.raises(PoseValidationError, match="non-decreasing"):
        _blank_sequence(4, timestamps=[0.0, 0.2, 0.1, 0.3]).validate()
    with pytest.raises(PoseValidationError, match="positive duration"):
        _blank_sequence(4, timestamps=[0.0, 0.0, 0.0, 0.0]).validate()


def test_only_short_bounded_low_confidence_gaps_are_interpolated():
    seq = _blank_sequence(8)
    index = KEYPOINTS.index("l_knee")
    xs = [0, 10, 99, 30, 99, 99, 99, 70]
    conf = [1, 1, 0.1, 1, 0.1, 0.1, 0.1, 1]
    for frame, (x, confidence) in enumerate(zip(xs, conf)):
        seq.frames[frame][index] = (x, 5.0, confidence)
    filtered = seq.filtered_for_analysis(max_gap_seconds=0.05)
    assert filtered.xy(2, "l_knee")[0] == pytest.approx(20.0)
    assert filtered.pt(2, "l_knee")[2] == pytest.approx(0.35)
    assert all(math.isnan(filtered.xy(frame, "l_knee")[0]) for frame in (4, 5, 6))
    assert seq.xy(2, "l_knee")[0] == 99  # raw input remains unchanged


def test_flat_foot_signal_does_not_fabricate_toeoff():
    seq = _blank_sequence(120)
    for frame in range(seq.n):
        for side in ("l", "r"):
            for name in ("ankle", "heel", "big_toe"):
                index = KEYPOINTS.index(f"{side}_{name}")
                seq.frames[frame][index] = (20.0 if side == "l" else 80.0, 90.0, 1.0)
    events = detect_events(seq)
    assert events.toeoffs == {"l": [], "r": []}
    assert events.stance == {"l": [], "r": []}
    assert events.confidence == "low"


def test_new_outputs_and_sample_statistics_are_exposed():
    result = analyze(
        synthetic.generate("side-left", fps=120, duration=8, cadence=172),
        profile={"height_cm": 160, "leg_length_cm": 76, "speed_kmh": 12,
                 "age_years": 35, "body_mass_kg": 58, "sex": "female"},
    ).to_dict()
    cards = {card["key"]: card for card in result["metrics"]}
    expected = {
        "step_time", "stride_time", "swing_time", "cadence_cv", "contact_time_cv",
        "knee_flexion_contact", "knee_flexion_peak", "knee_flexion_excursion", "hip_flexion_peak",
        "ankle_dorsiflexion_midstance", "ankle_plantarflexion_toeoff",
        "shank_angle_contact", "step_length_leg_ratio", "dimensionless_speed",
    }
    assert expected <= set(cards)
    assert cards["cadence"]["statistics"]["n"] >= 3
    assert len(cards["cadence"]["statistics"]["ci95_mean"]) == 2
    assert cards["hip_extension"]["statistics"]["mean"] == pytest.approx(
        cards["hip_extension"]["value"], abs=0.1
    )
    assert cards["cadence"]["reference"]["label"] == "population estimate"


def test_boolean_rear_view_observations_are_visible_cards():
    result = analyze(synthetic.generate("rear", duration=6)).to_dict()
    cards = {card["key"]: card for card in result["metrics"]}
    for key in ("crossover", "arm_crossover"):
        assert cards[key]["is_boolean"] is True
        assert cards[key]["text"] in ("observed", "not observed")


def test_untracked_optional_head_does_not_emit_head_card():
    seq = synthetic.generate("side-left", duration=6)
    index = KEYPOINTS.index("head")
    for frame in seq.frames:
        x, y, _confidence = frame[index]
        frame[index] = (x, y, 0.0)
    keys = {card["key"] for card in analyze(seq).to_dict()["metrics"]}
    assert "head_drop" not in keys


def test_invalid_calibration_values_do_not_produce_spatial_outputs():
    result = analyze(
        synthetic.generate("side-left", duration=6),
        profile={"height_cm": -160, "leg_length_cm": "unknown", "speed_kmh": float("inf")},
    ).to_dict()
    keys = {card["key"] for card in result["metrics"]}
    assert "vertical_oscillation_cm" not in keys
    assert "step_length" not in keys
    assert "dimensionless_speed" not in keys


def test_validation_summary_reports_failures_and_agreement_errors():
    rows = [
        {"split": "test", "metric": "cadence", "unit": "spm", "observed": "170", "criterion": "172"},
        {"split": "test", "metric": "cadence", "unit": "spm", "observed": "174", "criterion": "173"},
        {"split": "test", "metric": "cadence", "unit": "spm", "observed": "", "criterion": "171"},
    ]
    result = summarize(rows)[0]
    assert result["n_valid"] == 2
    assert result["failure_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert result["bias"] == -0.5
    assert result["mae"] == 1.5
    assert "loa95" in result


def test_every_metric_reference_id_exists_in_evidence_register():
    evidence = (Path(__file__).parent.parent / "docs" / "references.md").read_text()
    registered = set(re.findall(r"^\| `([^`]+)` \|", evidence, flags=re.MULTILINE))
    used = {
        reference
        for definition in METRIC_DEFS.values()
        for reference in definition.reference_ids
    }
    assert used <= registered
