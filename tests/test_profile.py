"""RunnerProfile and the calibration derived from it.

`calibrate()` takes pixel measurements as plain numbers rather than a
PoseSequence, so the unit-conversion and scale-preference rules are testable here
without building a skeleton — that decoupling is the point of the class.
"""

from __future__ import annotations

import pytest

from gaitlab.core.profile import Calibration, RunnerProfile


class TestFromDict:
    def test_ignores_keys_the_engine_does_not_model(self):
        """Profiles arrive from the browser, CLI and HTTP API; an unrecognized
        key must not fail an analysis."""
        p = RunnerProfile.from_dict({"height_cm": 170, "nickname": "zoom"})
        assert p.height_cm == 170
        assert not hasattr(p, "nickname")

    @pytest.mark.parametrize("empty", [None, {}])
    def test_empty_input_gives_an_empty_profile(self, empty):
        assert RunnerProfile.from_dict(empty) == RunnerProfile()

    def test_round_trips_through_the_wire_form(self):
        d = {"sex": "female", "height_cm": 170.0, "speed_kmh": 12.0}
        assert RunnerProfile.from_dict(d).to_dict() == d


class TestToDict:
    def test_omits_unset_fields_rather_than_emitting_null(self):
        """The browser only sends fields the runner filled in, and the report
        echoes that sparse shape back. Emitting nulls would change the payload
        every consumer sees."""
        assert RunnerProfile(height_cm=170).to_dict() == {"height_cm": 170}

    def test_empty_profile_serializes_to_an_empty_dict(self):
        assert RunnerProfile().to_dict() == {}


class TestTruthiness:
    def test_empty_profile_is_falsey(self):
        assert not RunnerProfile()

    def test_any_single_field_makes_it_truthy(self):
        assert RunnerProfile(sex="female")
        assert RunnerProfile(speed_kmh=12.0)


class TestSpeed:
    def test_kmh_converts_to_mps(self):
        assert RunnerProfile(speed_kmh=18.0).speed_mps == pytest.approx(5.0)

    def test_absent_speed_stays_none(self):
        assert RunnerProfile().speed_mps is None

    def test_zero_speed_is_treated_as_unset(self):
        """A treadmill speed of 0 can't calibrate anything; metrics that need it
        check for falsiness, so None keeps that check working."""
        assert RunnerProfile(speed_kmh=0).speed_mps is None


class TestCalibrate:
    def test_prefers_measured_leg_length_over_height(self):
        """Leg length is measured against the same limb the pose model tracks;
        height-derived scale depends on noisier head/heel keypoints."""
        p = RunnerProfile(height_cm=170, leg_length_cm=80)
        cal = p.calibrate(leg_px=400, body_px_height=850)
        assert cal.px_per_cm == pytest.approx(5.0)  # 400/80, not 850/170

    def test_falls_back_to_height_without_leg_length(self):
        cal = RunnerProfile(height_cm=170).calibrate(leg_px=400, body_px_height=850)
        assert cal.px_per_cm == pytest.approx(5.0)  # 850/170

    def test_no_measurements_gives_no_scale(self):
        cal = RunnerProfile(speed_kmh=12.0).calibrate(leg_px=400, body_px_height=850)
        assert cal.px_per_cm is None
        assert cal.speed_mps == pytest.approx(12.0 / 3.6)

    def test_empty_profile_gives_an_empty_calibration(self):
        assert RunnerProfile().calibrate(400, 850) == Calibration()

    def test_degenerate_leg_pixels_do_not_divide_by_zero(self):
        """_leg_length() floors at 1.0, but a caller passing 0 must not explode."""
        cal = RunnerProfile(leg_length_cm=80).calibrate(leg_px=0, body_px_height=None)
        assert cal.px_per_cm is None

    def test_missing_body_height_falls_through_cleanly(self):
        """_body_px_height returns None when head or feet are never tracked."""
        cal = RunnerProfile(height_cm=170).calibrate(leg_px=400, body_px_height=None)
        assert cal.px_per_cm is None


class TestEngineBoundary:
    def test_analyze_accepts_either_form_and_agrees(self, synth):
        """The dict and the dataclass must produce the same analysis — the
        conversion at analyze()'s boundary is the only place the two forms meet."""
        from gaitlab import analyze

        seq = synth("side-left", fps=60, duration=6, seed=3)
        d = {"sex": "female", "height_cm": 170, "speed_kmh": 12.0}
        from_dict = analyze(seq, "x", d).to_dict()
        from_obj = analyze(seq, "x", RunnerProfile.from_dict(d)).to_dict()
        assert from_dict == from_obj

    def test_unmodelled_keys_are_echoed_back_verbatim(self, synth):
        """POST /api/analyze forwards arbitrary client JSON as the profile; the
        summary echo reports it unchanged even though the engine ignores it."""
        from gaitlab import analyze

        d = {"height_cm": 170, "nickname": "zoom"}
        result = analyze(synth("side-left", fps=60, duration=6), "x", d).to_dict()
        assert result["summary"]["profile"] == d
