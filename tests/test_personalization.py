"""Personalization formulas (gaitlab.metrics.defs.personalize)."""

from __future__ import annotations

import pytest

from gaitlab.metrics.defs import METRIC_DEFS, personalize
from gaitlab.metrics.keys import MetricKey


def _center(good):
    return sum(good) / 2.0


def test_cadence_center_formula_exact():
    # center = 188 - 0.615*(stature-157); good = round(center)±7
    good = personalize({"height_cm": 170})[MetricKey.CADENCE].good
    expected_center = 188.0 - 0.615 * (170 - 157)
    assert _center(good) == pytest.approx(expected_center, abs=1.0)
    assert good[1] - good[0] == pytest.approx(14, abs=1)   # ±7 band


def test_cadence_higher_for_shorter_runner():
    short = _center(personalize({"height_cm": 155})[MetricKey.CADENCE].good)
    tall = _center(personalize({"height_cm": 188})[MetricKey.CADENCE].good)
    assert short > tall


def test_cadence_speed_nudge_and_clamp():
    base = _center(personalize({"height_cm": 170})[MetricKey.CADENCE].good)
    fast = _center(personalize({"height_cm": 170, "speed_kmh": 16})[MetricKey.CADENCE].good)
    assert fast > base                       # +1.2 per km/h over 10
    # clamp: a very tall, slow runner cannot go below 160 center
    slow_tall = _center(personalize({"height_cm": 210})[MetricKey.CADENCE].good)
    assert slow_tall >= 160 - 7


def test_leg_length_preferred_over_height():
    # leg length maps to stature via /0.48; should still center sensibly and be personalized
    g = personalize({"leg_length_cm": 80})[MetricKey.CADENCE].good
    assert g != METRIC_DEFS[MetricKey.CADENCE].good


def test_female_pelvic_drop_band_widened():
    base = METRIC_DEFS[MetricKey.PELVIC_DROP].good
    fem = personalize({"sex": "female"})[MetricKey.PELVIC_DROP].good
    assert fem[1] > base[1]
    assert fem == (None, 7)


def test_no_profile_returns_base_defs():
    assert personalize(None)[MetricKey.CADENCE].good == METRIC_DEFS[MetricKey.CADENCE].good
