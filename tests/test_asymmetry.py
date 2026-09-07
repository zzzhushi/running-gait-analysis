"""Descriptive left/right comparison behavior."""

import math

import pytest

from gaitlab.metrics import asymmetry as A


def test_ratio_formula_and_zero_denominator():
    assert A.diff_pct(10, 12) == pytest.approx(2 / 11 * 100)
    assert A.diff_pct(20, 20) == 0.0
    assert math.isnan(A.diff_pct(0.0, 0.0))
    assert math.isnan(A.diff_pct(float("nan"), 5))


def test_native_unit_difference_is_primary_and_unflagged():
    rows = A.compute(
        {"l": {"hip_extension": 20.0}, "r": {"hip_extension": 8.0}},
        confidences={"hip_extension": "moderate"},
    )
    row = next(item for item in rows if item["key"] == "hip_extension")
    assert row["left"] == 20.0
    assert row["right"] == 8.0
    assert row["difference"] == 12.0
    assert row["status"] == "info"
    assert row["interpretation"] == "descriptive"
    assert row["mdc"] is None
    assert row["confidence"] == "moderate"
    assert "worse_side" not in row


def test_no_overall_asymmetry_score_penalty():
    assert A.overall_diff([{"difference": 100}]) == 0.0
