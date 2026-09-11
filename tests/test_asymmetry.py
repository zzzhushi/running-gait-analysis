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



def test_diff_pct_is_suppressed_below_the_reported_precision():
    """Values print to 2 decimals, so a mean magnitude under half that step has no
    significant digits left to build a percentage from. The old 1e-6 floor only
    caught exact zeros and reported 66.7% for L=0.01 vs R=0.02."""
    assert math.isnan(A.diff_pct(0.001, 0.002))
    assert math.isnan(A.diff_pct(0.0, 0.004))
    # Comfortably above the floor, so still reported.
    assert A.diff_pct(2.0, 3.0) == pytest.approx(40.0)


def test_rows_are_ordered_by_native_difference_not_percentage():
    """The percentage explodes near zero, so ordering by it would rank the least
    meaningful comparisons highest."""
    rows = A.compute({
        "l": {"hip_extension": 20.0, "pelvic_drop": 0.5},
        "r": {"hip_extension": 26.0, "pelvic_drop": 1.0},
    })
    by_key = {row["key"]: row for row in rows}
    # pelvic_drop has the larger percentage, hip_extension the larger real difference.
    assert by_key["pelvic_drop"]["diff_pct"] > by_key["hip_extension"]["diff_pct"]
    assert abs(by_key["hip_extension"]["difference"]) > abs(by_key["pelvic_drop"]["difference"])
    assert [row["key"] for row in rows].index("hip_extension") < \
           [row["key"] for row in rows].index("pelvic_drop")
