"""Drift detector: docs/spec/metrics.yaml (canonical) MUST match the code.

If a threshold, unit, view, or scoring role is edited in either the YAML or
gaitlab/metrics/defs.py without the other, one of these tests fails.
"""

from __future__ import annotations

import pytest

from gaitlab.metrics.asymmetry import ASYM_METRICS
from gaitlab.metrics.defs import METRIC_DEFS
from gaitlab.metrics.keys import MetricKey

from conftest import load_spec

SPEC = load_spec()
METRICS = SPEC.get("metrics", {})


def _def_key_set():
    return {k.value for k in METRIC_DEFS}


@pytest.mark.covers("R13.1")
def test_yaml_metric_keys_match_registry():
    assert set(METRICS) == _def_key_set(), (
        "metrics.yaml keys and METRIC_DEFS keys diverged:\n"
        f"  only in yaml: {set(METRICS) - _def_key_set()}\n"
        f"  only in code: {_def_key_set() - set(METRICS)}"
    )


def test_computed_only_keys_are_registry_absent_enum_members():
    computed = set(SPEC.get("computed_only", []))
    enum_vals = {m.value for m in MetricKey}
    # every computed_only key is a real enum member with no MetricDef entry
    assert computed <= enum_vals
    assert computed.isdisjoint(_def_key_set())
    # and together they account for every enum member
    assert computed | _def_key_set() == enum_vals


@pytest.mark.parametrize("key", sorted(METRICS))
def test_bands_and_flags_match_code(key):
    y = METRICS[key]
    d = METRIC_DEFS[MetricKey(key)]
    assert tuple(y["good"]) == d.good, f"{key} good band drift"
    assert tuple(y["warn"]) == d.warn, f"{key} warn band drift"
    assert y["unit"] == d.unit, f"{key} unit drift"
    assert y["confidence"] == d.confidence, f"{key} confidence drift"
    assert list(y["views"]) == list(d.views), f"{key} views drift"
    assert y["scored"] == d.scored, f"{key} scored flag drift"
    assert y["per_side"] == d.per_side, f"{key} per_side flag drift"
    assert y["asym_direction"] == d.asym_direction, f"{key} asym_direction drift"


@pytest.mark.covers("R17.1")
def test_pronation_excluded_from_scoring():
    assert METRICS["pronation"]["scored"] is False
    assert METRIC_DEFS[MetricKey.PRONATION].scored is False


@pytest.mark.covers("R13.1")
def test_asymmetry_directions_match_code():
    yaml_asym = SPEC["asymmetry"]["metrics"]
    code_asym = {k.value: METRIC_DEFS[k].asym_direction for k in ASYM_METRICS}
    assert yaml_asym == code_asym


def test_scored_key_lists_match_derivation():
    for view_str, listed in (("side", "scored_keys_side"), ("rear", "scored_keys_rear")):
        # asymmetry is the meta-metric (penalty path), excluded from the base-score key lists
        derived = {k for k, m in METRICS.items()
                   if m["scored"] and view_str in m["views"] and k != "asymmetry"}
        assert derived == set(SPEC["scoring"][listed]), (
            f"{listed} in metrics.yaml is stale vs the scored/views flags"
        )
