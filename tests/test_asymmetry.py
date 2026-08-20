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


def test_bandless_metric_is_not_auto_suppressed():
    """A metric with no good band must still be able to flag a left/right imbalance.

    `MetricDef.status()` returns "good" unconditionally when good == (None, None) — that is
    deliberate for metrics where no value is inherently better (foot-strike angle). The
    "both sides individually healthy" suppression must not read that sentinel as evidence
    of health, or every asymmetry on such a metric is silently downgraded however large.
    Regression guard: an 82% foot-strike difference once displayed as "good".
    """
    from gaitlab.metrics.defs import METRIC_DEFS

    defn = METRIC_DEFS[MetricKey.FOOT_STRIKE_ANGLE]
    assert tuple(defn.good) == (None, None), "fixture assumption: this metric has no band"
    assert defn.status(999.0) == "good", "fixture assumption: status() is an always-good sentinel"

    per_side = {"l": {"foot_strike_angle": 15.0}, "r": {"foot_strike_angle": 6.0}}
    out = A.compute(per_side)
    fsa = [a for a in out if a["key"] == MetricKey.FOOT_STRIKE_ANGLE][0]
    assert fsa["diff_pct"] > 80.0
    assert fsa["status"] != "good", "large asymmetry on a band-less metric was suppressed"


def test_banded_metric_still_suppressed_when_both_sides_healthy():
    """The suppression itself is intended behaviour where a band exists — keep it."""
    # knee drive good band is (20, None); both sides comfortably inside it.
    per_side = {"l": {"knee_drive": 26.0}, "r": {"knee_drive": 30.0}}
    out = A.compute(per_side)
    kd = [a for a in out if a["key"] == MetricKey.KNEE_DRIVE][0]
    assert kd["diff_pct"] > 10.0
    assert kd["status"] == "good"
