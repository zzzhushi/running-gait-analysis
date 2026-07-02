"""Data validation: input (PoseSequence) and output (AnalysisResult) schemas.

Property-based fuzzing (hypothesis) asserts that ANY structurally valid pose analyzes
into a schema-conformant result without crashing, and that malformed input is rejected.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gaitlab import analyze as analyze_mod
from gaitlab.analyze import ResultValidationError, analyze, validate_result
from gaitlab.core.schema import KEYPOINTS, VIEWS, PoseSequence, PoseValidationError

K = len(KEYPOINTS)

_coord = st.floats(min_value=-5000, max_value=5000, allow_nan=False, allow_infinity=False)
_conf = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_point = st.tuples(_coord, _coord, _conf)


@st.composite
def _pose_seqs(draw):
    n = draw(st.integers(min_value=4, max_value=18))
    frames = draw(st.lists(st.lists(_point, min_size=K, max_size=K), min_size=n, max_size=n))
    return PoseSequence(
        fps=draw(st.sampled_from([30.0, 60.0, 120.0, 240.0])),
        width=1080, height=1920,
        view=draw(st.sampled_from(VIEWS)),
        frames=frames, source="hyp",
    )


def _valid_base():
    frames = [[(float(i), float(i + 1), 1.0)] * 1 * K for i in range(6)]
    # each frame must be K points; build explicitly
    frames = [[(float(i + j), float(i - j), 0.9) for j in range(K)] for i in range(6)]
    return PoseSequence(fps=60.0, width=1080, height=1920, view="side-left",
                        frames=frames, source="test")


# --- input validation ------------------------------------------------------

def test_valid_pose_validates():
    _valid_base().validate()  # must not raise


@pytest.mark.parametrize("mutate,match", [
    (lambda s: setattr(s, "fps", 0), "fps"),
    (lambda s: setattr(s, "fps", -30), "fps"),
    (lambda s: setattr(s, "view", "diagonal"), "view"),
    (lambda s: setattr(s, "frames", []), "frames is empty"),
    (lambda s: s.frames.__setitem__(0, s.frames[0][:-1]), "keypoints, expected"),
    (lambda s: s.frames[0].__setitem__(0, (1.0, 2.0, 3.0)), "confidence"),
    (lambda s: s.frames[0].__setitem__(0, (float("nan"), 2.0, 1.0)), "non-finite"),
])
def test_malformed_pose_rejected(mutate, match):
    s = _valid_base()
    mutate(s)
    with pytest.raises(PoseValidationError, match=match):
        s.validate()


def test_analyze_rejects_malformed_input():
    s = _valid_base()
    s.view = "diagonal"
    with pytest.raises(PoseValidationError):
        analyze(s)


# --- output validation -----------------------------------------------------

def test_synthetic_and_golden_outputs_conform(synth, golden_pose):
    for seq in (synth("side-left", fps=60, duration=6, cadence=176, seed=1),
                synth("rear", fps=60, duration=6, cadence=170, seed=2),
                golden_pose):
        analyze(seq).validate()


def test_validate_result_rejects_bad_score():
    with pytest.raises(ResultValidationError, match="overall_score"):
        validate_result({"summary": {"overall_score": 250, "grade": "A", "view": "rear"},
                         "metrics": [], "feedback": []})


def test_validate_result_rejects_bad_grade():
    with pytest.raises(ResultValidationError, match="grade"):
        validate_result({"summary": {"overall_score": 90, "grade": "Z", "view": "rear"},
                         "metrics": [], "feedback": []})


# --- property-based: any valid pose -> conformant, strictly-JSON result -----

@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_pose_seqs())
def test_any_valid_pose_analyzes_to_conformant_result(seq):
    seq.validate()
    d = analyze(seq).validate().to_dict()
    assert 0 <= d["summary"]["overall_score"] <= 100
    json.dumps(d, allow_nan=False)   # strictly JSON-safe (no NaN/Infinity)
