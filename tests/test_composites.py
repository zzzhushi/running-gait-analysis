"""Exploratory composites require same-stride observations and confidence."""

from gaitlab.coaching import feedback as fb


BASE = {"overstride": 12.0, "hip_extension": 5.0, "cadence": 160.0}
CONF = {"overstride": "moderate", "hip_extension": "moderate", "cadence": "moderate"}


def _build(observations, confidences=CONF):
    return fb.build({}, {}, [], "side-left", {}, observations=observations, confidences=confidences)[0]


def test_composite_requires_two_same_side_matching_strides():
    observations = [dict(BASE, side="l", strike=10), dict(BASE, side="l", strike=40)]
    items = _build(observations)
    finding = next(item for item in items if item.get("metric") == "overstriding")
    assert finding["interpretation"] == "exploratory"
    assert finding["side"] == "l"
    assert finding["matching_strides"] == 2
    assert finding["severity"] == "low"


def test_conditions_split_across_strides_do_not_fire():
    observations = [
        dict(BASE, side="l", strike=10, hip_extension=20),
        dict(BASE, side="l", strike=40, overstride=2),
    ]
    assert all(item.get("metric") != "overstriding" for item in _build(observations))


def test_conditions_split_across_sides_do_not_fire():
    observations = [dict(BASE, side="l", strike=10), dict(BASE, side="r", strike=40)]
    assert all(item.get("metric") != "overstriding" for item in _build(observations))


def test_low_component_confidence_suppresses_pattern():
    confidence = dict(CONF, hip_extension="low")
    observations = [dict(BASE, side="l", strike=10), dict(BASE, side="l", strike=40)]
    assert all(item.get("metric") != "overstriding" for item in _build(observations, confidence))
