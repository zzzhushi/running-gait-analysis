"""Descriptive feedback and language guardrails."""

from gaitlab import analyze, synthetic
from gaitlab.coaching import feedback as fb
from gaitlab.coaching import guardrails


def test_metric_values_do_not_create_prescriptive_findings(make_values):
    values = make_values("side-left", cadence=120, overstride=40, trunk_lean=30)
    items, score, grade = fb.build(values, {}, [], "side-left", {})
    assert score is None and grade is None
    assert items == [items[0]]
    assert items[0]["title"] == "Descriptive analysis complete"
    assert items[0]["severity"] == "good"


def test_analysis_has_no_exercise_plan_or_score():
    result = analyze(synthetic.generate("side-left", duration=6, cadence=150)).to_dict()
    assert result["plan"] == []
    assert result["summary"]["overall_score"] is None
    assert result["summary"]["grade"] is None


def test_guardrail_detects_prohibited_language():
    assert guardrails.find_prohibited("You likely have IT band syndrome.")
    assert guardrails.find_prohibited("This is causing your pain.")
    assert guardrails.find_prohibited("You may be diagnosed with a stress fracture.")


def test_no_prohibited_language_across_scenarios(golden_pose):
    scenarios = [
        synthetic.generate("side-left", duration=6, cadence=150, asymmetry=0.35),
        synthetic.generate("rear", duration=6, cadence=170, asymmetry=0.6),
        golden_pose,
    ]
    for seq in scenarios:
        result = analyze(seq).to_dict()
        assert guardrails.scan_findings(result["feedback"]) == []
        assert result["plan"] == []
