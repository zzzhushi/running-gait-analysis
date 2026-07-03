"""Coaching: metric -> finding mapping, exercise plans, and language guardrails."""

from __future__ import annotations

import pytest

from gaitlab import analyze, synthetic
from gaitlab.coaching import feedback as fb
from gaitlab.coaching import guardrails


# --- metric -> finding mapping --------------------------------------------

@pytest.mark.parametrize("view,overrides,expect_title", [
    ("side-left", {"cadence": 150}, "Increase your cadence"),
    ("side-left", {"overstride": 20}, "You're overstriding"),
    ("side-left", {"trunk_lean": 20}, "Too much trunk lean"),
    ("side-left", {"trunk_lean": 2}, "Run a touch more forward"),
    ("side-left", {"hip_extension": 4}, "Limited hip extension"),
    ("side-left", {"knee_drive": 6}, "Limited knee drive"),
    ("rear", {"pelvic_drop": 12}, "Hip drop"),
    ("rear", {"lateral_trunk_sway": 15}, "Trunk swaying side to side"),
])
def test_out_of_band_metric_surfaces_expected_finding(make_values, view, overrides, expect_title):
    values = make_values(view, **overrides)
    items, _score, _grade = fb.build(values, {}, [], view, {})
    titles = " || ".join(i["title"] for i in items)
    assert expect_title in titles, titles


def test_heavy_heelstrike_plus_overstride_combo(make_values):
    values = make_values("side-left", foot_strike_angle=20, overstride=12)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    assert any("Heavy heel-strike" in i["title"] for i in items)


def test_findings_carry_cue_and_drill(make_values):
    values = make_values("side-left", cadence=150)
    items, _s, _g = fb.build(values, {}, [], "side-left", {})
    finding = [i for i in items if i["severity"] in ("high", "med")][0]
    assert finding["cue"] and finding["drill"]


def test_clean_run_gives_positive_note(make_values):
    items, _s, _g = fb.build(make_values("side-left"), {}, [], "side-left", {})
    assert any(i["severity"] == "good" for i in items)


def test_plan_built_from_findings():
    plan = analyze(synthetic.generate("side-left", fps=60, duration=6, cadence=150,
                                      asymmetry=0.25, seed=21)).to_dict()["plan"]
    assert plan and "name" in plan[0]["exercises"][0]


# --- language guardrails ---------------------------------------------------

def test_guardrail_detects_prohibited_language():
    assert guardrails.find_prohibited("You likely have IT band syndrome.")
    assert guardrails.find_prohibited("This is causing your pain.")
    assert guardrails.find_prohibited("You may be diagnosed with a stress fracture.")
    # structure mentions and normal cues are allowed
    assert not guardrails.find_prohibited("This can stress the IT band and knee.")
    assert not guardrails.find_prohibited("Lean until you have to step.")


def test_no_prohibited_language_across_scenarios(golden_pose):
    scenarios = [
        synthetic.generate("side-left", fps=60, duration=6, cadence=150, asymmetry=0.35, seed=61),
        synthetic.generate("side-left", fps=60, duration=6, cadence=200, seed=62),
        synthetic.generate("rear", fps=60, duration=6, cadence=170, asymmetry=0.6, seed=63),
        golden_pose,
    ]
    for seq in scenarios:
        d = analyze(seq).to_dict()
        hits = guardrails.scan_findings(d["feedback"])
        # also scan the plan text
        for p in d["plan"]:
            hits += guardrails.find_prohibited(p.get("title", "") + " " + p.get("why", ""))
            for ex in p.get("exercises", []):
                hits += guardrails.find_prohibited(" ".join(str(v) for v in ex.values()))
        assert hits == [], f"prohibited language in output: {hits}"
