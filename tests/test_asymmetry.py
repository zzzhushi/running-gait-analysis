"""Left/right asymmetry (gaitlab/metrics/asymmetry.py)."""

from __future__ import annotations

import math

import pytest

from gaitlab.metrics import asymmetry as A
from gaitlab.metrics.keys import MetricKey


def test_diff_pct_formula():
    # AI = |L-R| / mean(|L|,|R|) * 100
    assert A.diff_pct(10, 12) == pytest.approx(abs(10 - 12) / 11 * 100)
    assert A.diff_pct(20, 20) == 0.0
    assert math.isnan(A.diff_pct(float("nan"), 5))


def test_diff_pct_near_zero_is_zero_not_infinite():
    assert A.diff_pct(0.0, 0.0) == 0.0


def test_flags_large_imbalance():
    # hip extension L 20 vs R 8 -> big gap, both not "good" enough to suppress (R 8 warn)
    per_side = {"l": {"hip_extension": 20.0}, "r": {"hip_extension": 8.0}}
    out = A.compute(per_side)
    he = [a for a in out if a["key"] == MetricKey.HIP_EXTENSION][0]
    assert he["status"] in ("warn", "bad")
    assert he["worse_side"] == "right"        # lower is worse for higher_better


def test_both_sides_good_suppresses_flag():
    # pelvic drop L 2 vs R 5: %-diff is large, but BOTH are within good (<=6) -> suppressed
    per_side = {"l": {"pelvic_drop": 2.0}, "r": {"pelvic_drop": 5.0}}
    out = A.compute(per_side)
    pd = [a for a in out if a["key"] == MetricKey.PELVIC_DROP][0]
    assert pd["diff_pct"] > 10                 # raw percent difference is large
    assert pd["status"] == "good"              # ...but suppressed because both are healthy


def test_worse_side_direction_semantics():
    # higher_worse: the larger value is the worse side
    per_side = {"l": {"overstride": 18.0}, "r": {"overstride": 6.0}}
    out = A.compute(per_side)
    ov = [a for a in out if a["key"] == MetricKey.OVERSTRIDE][0]
    assert ov["worse_side"] == "left"


def test_overall_diff_averages_flagged_only():
    asym = [
        {"diff_pct": 20.0, "status": "bad"},
        {"diff_pct": 12.0, "status": "warn"},
        {"diff_pct": 50.0, "status": "good"},   # ignored
    ]
    assert A.overall_diff(asym) == pytest.approx(16.0)
    assert A.overall_diff([]) == 0.0
