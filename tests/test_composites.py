"""Composite patterns (§14): triggering, component suppression, and the 3-finding cap."""

from __future__ import annotations

import pytest

from gaitlab.coaching import feedback as fb


def _metrics(items):
    return {i.get("metric") for i in items}


def _titles(items):
    return " || ".join(i["title"] for i in items)


@pytest.mark.covers("R14.1")
def test_overstriding_composite_fires_and_supersedes(make_values):
    values = make_values("side-left", overstride=20, hip_extension=4, cadence=150)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert "overstriding" in _metrics(items)
    # component single-metric findings are suppressed by the composite
    assert {"overstride", "hip_extension", "cadence"}.isdisjoint(_metrics(items))


@pytest.mark.covers("R14.2")
def test_sinking_composite_fires_and_supersedes(make_values):
    values = make_values("side-left", knee_flexion_midstance=60, trunk_lean=20)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert "sinking_midstance" in _metrics(items)
    assert {"knee_flexion_midstance", "trunk_lean"}.isdisjoint(_metrics(items))


@pytest.mark.covers("R14.3")
def test_bouncing_composite_fires_and_supersedes(make_values):
    values = make_values("side-left", vertical_oscillation=25, cadence=150)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert "bouncing" in _metrics(items)
    assert {"vertical_oscillation", "cadence"}.isdisjoint(_metrics(items))


@pytest.mark.covers("R14.4")
def test_heavy_heelstrike_composite(make_values):
    values = make_values("side-left", foot_strike_angle=20, overstride=12)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert "heavy_heelstrike" in _metrics(items)
    assert "foot_strike_angle" not in _metrics(items)


@pytest.mark.covers("R14.0")
def test_at_most_three_substantive_findings(make_values):
    values = make_values("side-left", cadence=150, trunk_lean=20, knee_flexion_midstance=60,
                         vertical_oscillation=25, contact_time=400, duty_factor=60,
                         elbow_angle=130, hip_extension=4, overstride=20)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    non_good = [i for i in items if i["severity"] != "good"]
    assert len(non_good) <= 3


@pytest.mark.covers("R14.0")
def test_composite_ranks_above_components(make_values):
    values = make_values("side-left", overstride=20, hip_extension=4, cadence=150)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    # the surviving finding is the composite, at high severity, ranked first
    assert items[0]["metric"] == "overstriding"
    assert items[0]["severity"] == "high"


@pytest.mark.covers("R14.5")
def test_lateral_chain_composite_fires_and_supersedes(make_values):
    values = make_values("rear", pelvic_drop=12, hip_adduction=10)
    items, _s, _g = fb.build(values, {}, [], "rear", {})
    assert "lateral_chain" in _metrics(items)
    assert {"pelvic_drop", "hip_adduction"}.isdisjoint(_metrics(items))


@pytest.mark.covers("R14.6")
def test_underpowered_pushoff_composite_fires_and_supersedes(make_values):
    values = make_values("side-left", hip_extension=4, knee_drive=8, cadence=198)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert "underpowered_pushoff" in _metrics(items)
    assert {"hip_extension", "knee_drive"}.isdisjoint(_metrics(items))


@pytest.mark.covers("R14.7")
def test_upper_body_rotation_composite_fires_and_supersedes(make_values):
    values = make_values("rear", arm_crossover=True, lateral_trunk_sway=14)
    items, _s, _g = fb.build(values, {}, [], "rear", {})
    assert "upper_body_rotation" in _metrics(items)
    assert {"lateral_trunk_sway", "arm_crossover"}.isdisjoint(_metrics(items))


@pytest.mark.covers("R14.8")
def test_one_sided_deficit_fires_when_same_side_worse_across_metrics(make_values):
    values = make_values("side-left")
    asym = [
        {"key": "hip_extension", "label": "Hip extension (peak)", "unit": "deg",
         "left": 8.0, "right": 18.0, "diff_pct": 76.9, "status": "bad", "worse_side": "left"},
        {"key": "knee_flexion_midstance", "label": "Knee flexion (midstance)", "unit": "deg",
         "left": 30.0, "right": 44.0, "diff_pct": 37.8, "status": "warn", "worse_side": "left"},
        {"key": "overstride", "label": "Overstride", "unit": "%leg",
         "left": 5.0, "right": 6.0, "diff_pct": 18.2, "status": "good", "worse_side": "left"},
    ]
    items, _s, _g = fb.build(values, {}, asym, "side-left", {})
    metas = [i for i in items if i["metric"] == "one_sided_deficit"]
    assert len(metas) == 1
    assert "left" in metas[0]["title"]
    # the two absorbed per-metric imbalance findings are not duplicated separately
    assert not any(i["title"].startswith("Left/right imbalance: Hip extension") for i in items)
    assert not any(i["title"].startswith("Left/right imbalance: Knee flexion") for i in items)


def test_one_sided_deficit_does_not_fire_on_single_metric_or_tie(make_values):
    values = make_values("side-left")
    single = [{"key": "hip_extension", "label": "Hip extension (peak)", "unit": "deg",
               "left": 8.0, "right": 18.0, "diff_pct": 76.9, "status": "bad", "worse_side": "left"}]
    items, _s, _g = fb.build(values, {}, single, "side-left", {})
    assert "one_sided_deficit" not in _metrics(items)

    tied = single + [{"key": "knee_drive", "label": "Knee drive (peak)", "unit": "deg",
                       "left": 25.0, "right": 12.0, "diff_pct": 70.3, "status": "bad", "worse_side": "right"}]
    items, _s, _g = fb.build(values, {}, tied, "side-left", {})
    assert "one_sided_deficit" not in _metrics(items)
