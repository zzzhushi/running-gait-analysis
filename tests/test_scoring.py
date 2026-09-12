"""Universal scoring and target bands are deliberately disabled."""

from gaitlab import analyze, synthetic
from gaitlab.coaching import feedback as fb
from gaitlab.metrics.defs import METRIC_DEFS


def test_registry_metrics_are_unscored_and_unbanded():
    assert all(not definition.scored for definition in METRIC_DEFS.values())
    assert all(definition.good == (None, None) and definition.warn == (None, None)
               for definition in METRIC_DEFS.values())
    assert all(not definition.finding_text and not definition.exercises
               and definition.trigger_fn is None for definition in METRIC_DEFS.values())


def test_supported_metrics_have_explicit_references():
    assert all(definition.reference_ids for definition in METRIC_DEFS.values()
               if definition.evidence_level == "supported")
    assert all(definition.confidence == "low" for definition in METRIC_DEFS.values()
               if definition.evidence_level == "experimental")


def test_feedback_returns_no_score_or_grade(make_values):
    _items, score, grade = fb.build(make_values("side-left", cadence=80), {}, [], "side-left", {})
    assert score is None and grade is None


def test_analysis_declares_descriptive_mode():
    result = analyze(synthetic.generate("side-left", duration=6)).to_dict()
    assert result["summary"]["overall_score"] is None
    assert result["summary"]["grade"] is None
    assert result["summary"]["analysis_mode"] == "descriptive_research"
    assert result["summary"]["score_status"] == "disabled_unvalidated"
    assert all(card["status"] == "info" for card in result["metrics"])
