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


if __name__ == "__main__":
    unittest.main(verbosity=2)
