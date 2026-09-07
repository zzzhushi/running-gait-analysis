"""Published context equations replace invented personalized target bands."""

import pytest

from gaitlab.metrics.defs import METRIC_DEFS, personalize
from gaitlab.metrics.keys import MetricKey
from gaitlab.metrics.reference_models import population_reference


def test_definitions_have_no_personalized_good_bands():
    for profile in (None, {"height_cm": 155}, {"sex": "female", "height_cm": 170}):
        definitions = personalize(profile)
        assert all(definition.good == (None, None) for definition in definitions.values())


def test_cadence_population_equation_exact():
    profile = {"age_years": 30, "height_cm": 160, "speed_kmh": 12}
    reference = population_reference("cadence", profile)
    expected = 203.056 + 0.193 * 30 - 44.242 * 1.6 + 3.067 * 12
    assert reference["value"] == pytest.approx(expected, abs=0.01)
    assert reference["label"] == "population estimate"
    assert "not an optimal" in reference["caveat"]


def test_equation_requires_exact_predictors_and_never_guesses_sex():
    assert population_reference("cadence", {"height_cm": 160}) is None
    complete = {"sex": "female", "body_mass_kg": 55, "height_cm": 160, "speed_kmh": 12}
    assert population_reference("contact_time", complete) is not None
    assert population_reference("contact_time", dict(complete, sex="nonbinary")) is None


def test_card_reference_is_context_not_target(synth):
    from gaitlab import analyze

    profile = {"age_years": 30, "height_cm": 160, "speed_kmh": 12}
    result = analyze(synth("side-left", duration=6), profile=profile).to_dict()
    cadence = next(card for card in result["metrics"] if card["key"] == "cadence")
    assert cadence["status"] == "info"
    assert cadence["reference"]["label"] == "population estimate"
    assert METRIC_DEFS[MetricKey.CADENCE].scored is False
