"""Composite patterns (§14): triggering, component suppression, and the 3-finding cap."""

from __future__ import annotations

from gaitlab.coaching import feedback as fb


def _metrics(items):
    return {i.get("metric") for i in items}


def _titles(items):
    return " || ".join(i["title"] for i in items)


def test_overstriding_composite_fires_and_supersedes(make_values):
    values = make_values("side-left", overstride=20, hip_extension=4, cadence=150)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert "overstriding" in _metrics(items)
    # component single-metric findings are suppressed by the composite
    assert {"overstride", "hip_extension", "cadence"}.isdisjoint(_metrics(items))


def test_sinking_composite_fires_and_supersedes(make_values):
    values = make_values("side-left", knee_flexion_midstance=60, trunk_lean=20)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert "sinking_midstance" in _metrics(items)
    assert {"knee_flexion_midstance", "trunk_lean"}.isdisjoint(_metrics(items))


def test_bouncing_composite_fires_and_supersedes(make_values):
    values = make_values("side-left", vertical_oscillation=25, cadence=150)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert "bouncing" in _metrics(items)
    assert {"vertical_oscillation", "cadence"}.isdisjoint(_metrics(items))


def test_heavy_heelstrike_composite(make_values):
    values = make_values("side-left", foot_strike_angle=20, overstride=12)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert "heavy_heelstrike" in _metrics(items)
    assert "foot_strike_angle" not in _metrics(items)


def test_at_most_three_substantive_findings(make_values):
    values = make_values("side-left", cadence=150, trunk_lean=20, knee_flexion_midstance=60,
                         vertical_oscillation=25, contact_time=400, duty_factor=60,
                         elbow_angle=130, hip_extension=4, overstride=20)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    non_good = [i for i in items if i["severity"] != "good"]
    assert len(non_good) <= 3


def test_composite_ranks_above_components(make_values):
    values = make_values("side-left", overstride=20, hip_extension=4, cadence=150)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    # the surviving finding is the composite, at high severity, ranked first
    assert items[0]["metric"] == "overstriding"
    assert items[0]["severity"] == "high"


def test_lateral_chain_composite_fires_and_supersedes(make_values):
    # hip_adduction is a hedged, low-confidence estimate (§7.3 rejects true knee valgus
    # from a single rear camera) — the composite still fires but at "med", not "high".
    values = make_values("rear", pelvic_drop=12, hip_adduction=10)
    items, _s, _g = fb.build(values, {}, [], "rear", {})
    assert "lateral_chain" in _metrics(items)
    assert {"pelvic_drop", "hip_adduction"}.isdisjoint(_metrics(items))
    lc = next(i for i in items if i["metric"] == "lateral_chain")
    assert lc["severity"] == "med"
