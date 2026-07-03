"""Scoring: per-metric band-edge anchors and the overall score/grade."""

from __future__ import annotations

import math

import pytest

from gaitlab.coaching import feedback as fb
from gaitlab.metrics.defs import METRIC_DEFS
from gaitlab.metrics.keys import MetricKey


def test_score_100_inside_good_band():
    cad = METRIC_DEFS[MetricKey.CADENCE]     # good (170, 185)
    assert cad.score(177) == 100.0
    assert cad.score(170) == 100.0           # edges are inclusive


def test_score_at_warn_edge_is_about_45():
    cad = METRIC_DEFS[MetricKey.CADENCE]     # good lo 170, warn lo 160 -> span 10
    assert cad.score(160) == pytest.approx(45.0, abs=0.01)   # frac = 1.0 -> 100-55


def test_score_deep_bad_clamps_to_about_17():
    cad = METRIC_DEFS[MetricKey.CADENCE]     # 1.5 * span past good edge = 170 - 15 = 155
    assert cad.score(155) == pytest.approx(17.5, abs=0.01)
    assert cad.score(120) == pytest.approx(17.5, abs=0.01)   # frac clamped at 1.5


def test_score_one_sided_band():
    over = METRIC_DEFS[MetricKey.OVERSTRIDE]   # good (None, 8), warn (None, 15) -> span 7
    assert over.score(5) == 100.0
    assert over.score(15) == pytest.approx(45.0, abs=0.01)   # warn edge
    assert over.score(8) == 100.0


def test_score_nan_is_50():
    assert METRIC_DEFS[MetricKey.CADENCE].score(float("nan")) == 50.0


def test_all_good_side_scores_grade_a(make_values):
    values = make_values("side-left")
    items, score, grade = fb.build(values, {}, [], "side-left", {})
    assert score >= 85 and grade == "A"
    assert not any(i["severity"] in ("high", "med") for i in items)


def test_degraded_side_scores_lower_grade(make_values):
    values = make_values("side-left", cadence=150, overstride=20, trunk_lean=20)
    _items, score, grade = fb.build(values, {}, [], "side-left", {})
    assert score < 85 and grade in ("B", "C", "D", "E")


def test_grade_cutoffs_are_monotonic(make_values):
    # sweep worsening cadence and confirm score never increases as the metric degrades
    prev = 101.0
    for cad in (177, 168, 162, 158, 150, 140):
        values = make_values("side-left", cadence=cad)
        _i, score, _g = fb.build(values, {}, [], "side-left", {})
        assert score <= prev + 1e-9, f"score rose as cadence worsened at {cad}"
        prev = score
