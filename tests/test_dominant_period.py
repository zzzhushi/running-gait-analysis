"""gaitlab.core.geometry.dominant_period and scripts/measure_cadence_groundtruth.py's
dominant_lag share normalized_autocorrelation and local_maxima but keep separate
period-picking policies. These tests protect both the shared arithmetic and the fact that
the two policies are genuinely different, not just differently named.
"""

from __future__ import annotations

import importlib.util
import math
import pathlib

import pytest

from gaitlab.core import geometry as geo

_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "measure_cadence_groundtruth.py"
_spec = importlib.util.spec_from_file_location("_measure_cadence_groundtruth", _SCRIPT)
_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_script)
dominant_lag = _script.dominant_lag


def sine(period: float, n: int = 150) -> list:
    return [math.sin(2 * math.pi * i / period) for i in range(n)]


def pulses(period: int, width: int, n: int, amp: float = 1.0) -> list:
    return [amp if (i % period) < width else 0.0 for i in range(n)]


def test_period_at_min_lag_is_not_missed():
    """The regression this file exists for: a true period sitting exactly at the search
    floor used to be misread as inside the zero-lag skirt and skipped."""
    assert dominant_lag(sine(10), 10, 40) == 10.0


def test_period_at_both_search_endpoints():
    assert dominant_lag(sine(15), 15, 60) == 15.0  # true period at the low end
    assert dominant_lag(sine(15), 5, 15) == 15.0  # true period at the high end


def test_shorter_fundamental_wins_over_its_own_harmonics():
    """A pure repeating pulse train correlates near-equally at every multiple of its true
    period; both selectors must prefer the shortest of those ties."""
    sig = pulses(period=14, width=3, n=300)
    assert dominant_lag(sig, 5, 60) == 14.0
    assert geo.dominant_period(sig, 5, 60) == 14.0


def test_ground_truth_divisor_rule_diverges_from_production_by_design():
    """Two superposed periodic components (16 and 10, LCM 80) create a real competing peak
    at 32 that scores within tolerance of the true 80-sample period but does not divide it.
    Production's plain 'smallest comparable peak' accepts 32; ground truth's divisor
    requirement rejects it and falls back to the true period. If this ever stops diverging,
    the two implementations have started sharing a policy they are meant to keep separate.
    """
    sig = [a + 0.4 * b for a, b in zip(pulses(16, 4, 360), pulses(10, 3, 360))]
    assert geo.dominant_period(sig, 4, 90) == 32.0
    assert dominant_lag(sig, 4, 90) == 80.0
