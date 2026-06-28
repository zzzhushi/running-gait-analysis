"""Unit tests for the gaitlab analysis engine (stdlib unittest, no deps)."""

import json
import math
import unittest

from gaitlab import analyze, synthetic
from gaitlab import geometry as geo
from gaitlab.events import detect_events
from gaitlab.metrics import compute as compute_metrics


class TestGeometry(unittest.TestCase):
    def test_angle_3pt_right_angle(self):
        self.assertAlmostEqual(geo.angle_3pt((0, 1), (0, 0), (1, 0)), 90.0, places=4)

    def test_angle_3pt_straight(self):
        self.assertAlmostEqual(geo.angle_3pt((-1, 0), (0, 0), (1, 0)), 180.0, places=4)

    def test_signed_lean_forward(self):
        # hip at origin, shoulder up-and-forward -> positive lean
        self.assertGreater(geo.signed_lean((0, 10), (2, 0), facing=1), 0)
        self.assertLess(geo.signed_lean((0, 10), (2, 0), facing=-1), 0)

    def test_find_peaks_on_sine(self):
        vals = [math.sin(i * 2 * math.pi / 20) for i in range(100)]
        peaks = geo.find_peaks(vals, min_distance=10, min_prominence=0.5)
        # ~5 full periods -> ~5 maxima
        self.assertTrue(4 <= len(peaks) <= 6, peaks)


class TestEvents(unittest.TestCase):
    def test_cadence_matches_synthetic(self):
        seq = synthetic.generate("side-left", fps=60, duration=6, cadence=172, seed=1)
        ev = detect_events(seq)
        self.assertFalse(math.isnan(ev.cadence_spm))
        self.assertAlmostEqual(ev.cadence_spm, 172, delta=172 * 0.15)

    def test_detects_strikes_each_foot(self):
        seq = synthetic.generate("side-left", fps=60, duration=6, cadence=170, seed=2)
        ev = detect_events(seq)
        # ~7 strides over 6 s -> several strikes per foot
        self.assertGreaterEqual(len(ev.strikes["l"]), 4)
        self.assertGreaterEqual(len(ev.strikes["r"]), 4)
        for side in ("l", "r"):
            self.assertTrue(all(t > s for (s, t) in ev.stance[side]))


class TestMetrics(unittest.TestCase):
    def test_symmetric_run_has_balanced_knees(self):
        seq = synthetic.generate("side-left", fps=60, duration=6, cadence=176, asymmetry=0.0, seed=3)
        m = compute_metrics(seq)
        l = m["per_side"]["l"]["knee_flexion_midstance"]
        r = m["per_side"]["r"]["knee_flexion_midstance"]
        self.assertFalse(math.isnan(l) or math.isnan(r))
        rel = abs(l - r) / ((abs(l) + abs(r)) / 2) * 100
        self.assertLess(rel, 12, f"L={l:.1f} R={r:.1f}")

    def test_trunk_lean_recovered(self):
        seq = synthetic.generate("side-left", fps=60, duration=5, cadence=176, seed=4)
        m = compute_metrics(seq)
        self.assertAlmostEqual(m["values"]["trunk_lean"], 8.0, delta=4.0)

    def test_midstance_knee_flexion_plausible(self):
        seq = synthetic.generate("side-left", fps=60, duration=6, cadence=176, seed=5)
        m = compute_metrics(seq)
        kf = m["values"]["knee_flexion_midstance"]
        self.assertTrue(20 < kf < 70, kf)


class TestAsymmetryAndAnalyze(unittest.TestCase):
    def test_injected_asymmetry_is_flagged(self):
        seq = synthetic.generate("side-left", fps=60, duration=6, cadence=170, asymmetry=0.3, seed=6)
        result = analyze(seq).to_dict()
        flagged = [a for a in result["asymmetry"] if a["status"] in ("warn", "bad")]
        self.assertTrue(flagged, result["asymmetry"])

    def test_rear_hip_drop_detected(self):
        seq = synthetic.generate("rear", fps=60, duration=6, cadence=170, asymmetry=0.6, seed=7)
        result = analyze(seq).to_dict()
        pd = result["metrics"][1]
        self.assertEqual(pd["key"], "pelvic_drop")
        self.assertIsNotNone(pd["value"])
        titles = " ".join(i["title"] for i in result["feedback"])
        self.assertIn("Hip drop", titles)

    def test_result_is_strict_json(self):
        seq = synthetic.generate("side-left", fps=60, duration=5, cadence=160, asymmetry=0.2, seed=8)
        result = analyze(seq, label="demo").to_dict()
        # strict: must not contain NaN/Infinity
        text = json.dumps(result, allow_nan=False)
        self.assertIn("\"summary\"", text)
        self.assertIn("\"pose\"", text)
        self.assertEqual(result["summary"]["label"], "demo")
        self.assertTrue(0 <= result["summary"]["overall_score"] <= 100)

    def test_low_cadence_produces_finding(self):
        seq = synthetic.generate("side-left", fps=60, duration=6, cadence=150, seed=9)
        result = analyze(seq).to_dict()
        titles = " ".join(i["title"] for i in result["feedback"])
        self.assertIn("cadence", titles.lower())


class TestM5Metrics(unittest.TestCase):
    def test_hip_extension_present_and_plausible(self):
        seq = synthetic.generate("side-left", fps=60, duration=6, cadence=176, seed=11)
        he = compute_metrics(seq)["values"]["hip_extension"]
        self.assertTrue(5 < he < 45, he)

    def test_pronation_rear_asymmetric(self):
        seq = synthetic.generate("rear", fps=60, duration=6, cadence=170, asymmetry=0.6, seed=12)
        ps = compute_metrics(seq)["per_side"]
        self.assertGreater(abs(ps["r"]["pronation"]), abs(ps["l"]["pronation"]))

    def test_calibration_adds_absolutes(self):
        seq = synthetic.generate("side-left", fps=60, duration=6, cadence=176, seed=13)
        base = compute_metrics(seq)["values"]
        self.assertNotIn("vertical_oscillation_cm", base)
        cal = compute_metrics(seq, calibration={"height_cm": 175, "speed_kmh": 12})["values"]
        self.assertIn("vertical_oscillation_cm", cal)
        self.assertIn("vertical_ratio", cal)
        self.assertTrue(0.5 < cal["stride_length"] < 4.0, cal.get("stride_length"))

    def test_calibration_flows_through_analyze(self):
        seq = synthetic.generate("side-left", fps=60, duration=5, cadence=170, seed=14)
        result = analyze(seq, profile={"height_cm": 180, "speed_kmh": 11}).to_dict()
        keys = [c["key"] for c in result["metrics"]]
        self.assertIn("hip_extension", keys)
        self.assertIn("vertical_oscillation_cm", keys)
        self.assertIn("stride_length", keys)
        self.assertEqual(result["summary"]["profile"]["height_cm"], 180)
        import json
        json.dumps(result, allow_nan=False)


class TestM6(unittest.TestCase):
    def test_personalized_cadence_higher_for_short_runner(self):
        from gaitlab.targets import personalize
        short = personalize({"height_cm": 155})["cadence"].good
        tall = personalize({"height_cm": 188})["cadence"].good
        self.assertGreater(sum(short) / 2, sum(tall) / 2)

    def test_female_pelvic_drop_band_wider(self):
        from gaitlab.targets import personalize, TARGETS
        self.assertGreater(personalize({"sex": "female"})["pelvic_drop"].good[1],
                           TARGETS["pelvic_drop"].good[1])

    def test_plan_built_from_findings(self):
        seq = synthetic.generate("side-left", fps=60, duration=6, cadence=150, asymmetry=0.25, seed=21)
        plan = analyze(seq).to_dict()["plan"]
        self.assertTrue(plan)
        self.assertIn("name", plan[0]["exercises"][0])
        self.assertIn("dose", plan[0]["exercises"][0])

    def test_quality_checks_present_and_short_clip_flagged(self):
        good = analyze(synthetic.generate("side-left", fps=60, duration=6, cadence=176, seed=22)).to_dict()
        self.assertTrue(all("level" in c and "message" in c for c in good["quality"]))
        short = analyze(synthetic.generate("side-left", fps=60, duration=1.0, cadence=176, seed=23)).to_dict()
        self.assertIn("Short clip", " ".join(c["message"] for c in short["quality"]))

    def test_leg_length_calibration(self):
        r = analyze(synthetic.generate("side-left", fps=60, duration=6, cadence=176, seed=24),
                    profile={"leg_length_cm": 78, "speed_kmh": 12}).to_dict()
        keys = [c["key"] for c in r["metrics"]]
        self.assertIn("vertical_oscillation_cm", keys)
        self.assertIn("stride_length", keys)


class TestM7Metrics(unittest.TestCase):
    def test_knee_drive_and_arms_side(self):
        v = compute_metrics(synthetic.generate("side-left", fps=60, duration=6, cadence=176, seed=31))["values"]
        self.assertTrue(10 < v["knee_drive"] < 50, v["knee_drive"])
        self.assertTrue(70 < v["elbow_angle"] < 120, v["elbow_angle"])
        self.assertIn("duty_factor", v)

    def test_p2_cards_present(self):
        keys = [c["key"] for c in analyze(synthetic.generate("side-left", fps=60, duration=6, cadence=176, seed=32)).to_dict()["metrics"]]
        for k in ("knee_drive", "elbow_angle", "arm_swing", "duty_factor"):
            self.assertIn(k, keys)

    def test_arm_crossover_not_false_positive(self):
        v = compute_metrics(synthetic.generate("rear", fps=60, duration=6, cadence=170, seed=33))["values"]
        self.assertFalse(v["arm_crossover"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
