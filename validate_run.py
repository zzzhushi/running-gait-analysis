#!/usr/bin/env python3
"""Quick end-to-end validation for a real video clip.

Usage:
    # Side view (most common)
    python3 validate_run.py myrun.mp4 --view side-left

    # Rear view
    python3 validate_run.py myrun.mp4 --view rear

    # With your profile for personalized norms + extra metrics
    python3 validate_run.py myrun.mp4 --view side-left \\
        --height 158 --leg 76 --speed 12.5 --sex female

Requires: pip install rtmlib onnxruntime opencv-python
Everything else (engine, server) needs only stdlib.

What it checks:
  - Skeleton confidence per frame (are keypoints tracked?)
  - Gait events (are foot strikes detected?)
  - Key metric plausibility (angles in range, cadence vs what you expect)
  - Any quality warnings (short clip, low confidence, etc.)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── helpers ───────────────────────────────────────────────────────────────────

SIDE_EXPECTED = {
    "cadence":              (160, 210, "spm"),
    "trunk_lean":           (0,   20,  "°"),
    "knee_flexion_midstance": (20, 70, "°"),
    "overstride":           (0,   40,  "%leg"),
    "hip_extension":        (0,   35,  "°"),
    "knee_drive":           (5,   50,  "°"),
    "elbow_angle":          (60,  140, "°"),
    "duty_factor":          (20,  65,  "%"),
    "contact_time_ms":      (100, 500, "ms"),
    "vertical_oscillation": (2,   20,  "%leg"),
    "flight_time":          (0,   400, "ms"),
    "heel_recovery":        (5,   80,  "%leg"),
}
REAR_EXPECTED = {
    "cadence":              (160, 210, "spm"),
    "pelvic_drop":          (0,   20,  "°"),
    "step_width":           (-5,  25,  "%leg"),
    "lateral_trunk_sway":   (0,   20,  "%leg"),
    "trunk_pelvis_rotation":(0,   30,  "°"),
}

ANSI_OK   = "\033[92m✓\033[0m"
ANSI_WARN = "\033[93m⚠\033[0m"
ANSI_BAD  = "\033[91m✗\033[0m"
ANSI_INFO = "\033[94m·\033[0m"


def _sym(ok, warn=False):
    if ok is None:
        return ANSI_INFO
    return ANSI_OK if ok else (ANSI_WARN if warn else ANSI_BAD)


def _check(val, lo, hi):
    """Return (in_range, border_warn)."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None, False
    margin = (hi - lo) * 0.15
    return lo <= val <= hi, not (lo + margin <= val <= hi - margin)


def _hr():
    print("─" * 60)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="End-to-end GaitLab pipeline validation.")
    ap.add_argument("video", help="path to the running video (MP4 / MOV / etc.)")
    ap.add_argument("--view", default="side-left",
                    choices=["side-left", "side-right", "rear", "front"],
                    help="camera angle (default: side-left)")
    ap.add_argument("--model", default="body26", choices=["body26", "wholebody"],
                    help="RTMPose model (body26 = faster; wholebody = 133-kpt)")
    ap.add_argument("--height",  type=float, default=None, metavar="CM",
                    help="your height in cm (enables VO-cm, vertical ratio)")
    ap.add_argument("--leg",     type=float, default=None, metavar="CM",
                    help="leg length in cm (greater trochanter → floor)")
    ap.add_argument("--speed",   type=float, default=None, metavar="KMH",
                    help="treadmill speed in km/h (enables step/stride length)")
    ap.add_argument("--sex",     default=None, choices=["female", "male"],
                    help="sex for personalized pelvic-drop norms")
    ap.add_argument("--pose-json", default=None, metavar="PATH",
                    help="skip extraction: load this pre-built pose JSON directly")
    ap.add_argument("--keep-json", action="store_true",
                    help="keep the extracted pose JSON after the run")
    args = ap.parse_args()

    # ── 1. Extract (or load) pose JSON ───────────────────────────────────────
    if args.pose_json:
        pose_path = args.pose_json
        print(f"{ANSI_INFO} Using existing pose JSON: {pose_path}")
    else:
        if not os.path.exists(args.video):
            sys.exit(f"Video not found: {args.video}")
        if args.keep_json:
            pose_path = os.path.splitext(args.video)[0] + ".pose.json"
        else:
            pose_path = tempfile.mktemp(suffix=".pose.json")

        print(f"\n{ANSI_INFO} Step 1/3 — extracting pose (RTMPose {args.model})…")
        extractor = os.path.join(os.path.dirname(__file__), "extractor", "extract_pose.py")
        cmd = [sys.executable, extractor, args.video,
               "--view", args.view, "--model", args.model, "-o", pose_path]
        ret = subprocess.run(cmd)
        if ret.returncode != 0:
            sys.exit("Pose extraction failed. Is rtmlib installed? pip install rtmlib onnxruntime opencv-python")
        print()

    # ── 2. Load pose JSON ────────────────────────────────────────────────────
    print(f"{ANSI_INFO} Step 2/3 — loading pose JSON…")
    with open(pose_path) as fh:
        pose = json.load(fh)

    frames = pose["frames"]
    fps    = pose["fps"]
    n      = len(frames)
    view   = pose.get("view", args.view)
    knames = pose.get("keypoint_names", [])

    # Per-frame confidence check
    conf_scores = []
    for fr in frames:
        scores = [pt[2] for pt in fr if len(pt) == 3]
        conf_scores.append(sum(scores) / max(1, len(scores)))
    avg_conf   = sum(conf_scores) / max(1, n)
    low_conf_f = sum(1 for c in conf_scores if c < 0.45)

    print(f"  {n} frames · {fps:.0f} fps · {n/fps:.1f}s · view={view}")
    conf_ok = avg_conf >= 0.5
    print(f"  avg keypoint confidence: {avg_conf:.2f}  "
          f"{'(good)' if conf_ok else '(LOW — tracking may be unreliable)'}")
    if low_conf_f:
        print(f"  {ANSI_WARN} {low_conf_f}/{n} frames below 0.45 confidence")
    if n < 40:
        print(f"  {ANSI_BAD} Short clip ({n} frames < 40) — too few gait cycles for reliable analysis")
    print()

    # ── 3. Analyze ───────────────────────────────────────────────────────────
    print(f"{ANSI_INFO} Step 3/3 — running gaitlab engine…")
    from gaitlab.schema import PoseSequence
    from gaitlab import analyze

    profile = {}
    if args.height:  profile["height_cm"]    = args.height
    if args.leg:     profile["leg_length_cm"] = args.leg
    if args.speed:   profile["speed_kmh"]     = args.speed
    if args.sex:     profile["sex"]           = args.sex

    seq    = PoseSequence(**{k: pose[k] for k in ("fps","width","height","view","keypoint_names","frames")})
    result = analyze(seq, label=os.path.basename(args.video), profile=profile or None).to_dict()
    print()

    # ── Report ───────────────────────────────────────────────────────────────
    summary = result["summary"]
    _hr()
    print(f"  GaitLab validation — {summary['label']}")
    print(f"  View: {summary['view']}   Grade: {summary['grade']}   Score: {summary['overall_score']:.0f}/100")
    _hr()

    # Quality checks
    if result.get("quality"):
        print("QUALITY CHECKS")
        for q in result["quality"]:
            sym = ANSI_OK if q["level"] == "ok" else (ANSI_WARN if q["level"] == "warn" else ANSI_BAD)
            print(f"  {sym}  {q['message']}")
        print()

    # Gait events
    from gaitlab.events import detect_events
    ev = detect_events(seq)
    n_l = len(ev.strikes.get("l", []))
    n_r = len(ev.strikes.get("r", []))
    events_ok = n_l >= 4 and n_r >= 4
    print("GAIT EVENTS")
    print(f"  {_sym(events_ok, n_l < 6 or n_r < 6)}  "
          f"Left strikes: {n_l}   Right strikes: {n_r}   "
          f"Cadence: {ev.cadence_spm:.1f} spm")
    if not events_ok:
        print(f"  {ANSI_BAD} Too few strikes — is the runner visible in the frame?")
    print()

    # Metric plausibility
    vals     = {m["key"]: m["value"] for m in result.get("metrics", []) if m.get("value") is not None}
    # also check summary for cadence
    if "cadence" not in vals and result["summary"].get("cadence"):
        vals["cadence"] = result["summary"]["cadence"]
    expected = SIDE_EXPECTED if "side" in view else REAR_EXPECTED
    all_ok   = True
    out_of_range = []
    print("METRIC PLAUSIBILITY")
    for key, (lo, hi, unit) in expected.items():
        val = vals.get(key)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            print(f"  {ANSI_INFO}  {key}: not computed (may need calibration or different view)")
            continue
        ok, border = _check(val, lo, hi)
        sym = _sym(ok, warn=border)
        flag = "" if ok else f"  ← expected {lo}–{hi} {unit}"
        print(f"  {sym}  {key}: {val:.1f} {unit}{flag}")
        if not ok:
            all_ok = False
            out_of_range.append(key)
    print()

    # Asymmetry summary
    asym = result.get("asymmetry", [])
    if asym:
        flagged = [a for a in asym if a["status"] in ("warn", "bad")]
        print("ASYMMETRY")
        if flagged:
            for a in flagged[:5]:
                sym = ANSI_WARN if a["status"] == "warn" else ANSI_BAD
                print(f"  {sym}  {a['label']}: L={a['left']:.1f} R={a['right']:.1f}  "
                      f"diff={a['diff_pct']:.0f}%  (worse: {a['worse_side']})")
        else:
            print(f"  {ANSI_OK}  No major asymmetries (< 10%)")
        print()

    # Top findings
    feedback = result.get("feedback", [])
    if feedback:
        print("TOP FINDINGS")
        for f in feedback[:5]:
            sev = {"bad": ANSI_BAD, "warn": ANSI_WARN}.get(f.get("severity","info"), ANSI_INFO)
            print(f"  {sev}  {f['title']}: {f['cue']}")
        print()

    # ── Final verdict ─────────────────────────────────────────────────────────
    _hr()
    if all_ok and events_ok and avg_conf >= 0.5:
        print(f"  {ANSI_OK}  Pipeline looks good — real-video metrics are plausible.")
        print("     Next: open http://localhost:8000 and upload this pose JSON")
        print("     to view the full report + skeleton overlay in the browser.")
    else:
        print(f"  {ANSI_WARN}  Some checks failed — see above.")
        if not events_ok:
            print("     • Too few gait events: is the runner centred in frame?")
        if avg_conf < 0.5:
            print("     • Low confidence: try better lighting or a contrasting background.")
        if out_of_range:
            print(f"     • Out-of-range metrics: {', '.join(out_of_range)}")
            print("       Could be correct for your body — compare with a known reference frame.")
    _hr()

    if not args.keep_json and not args.pose_json and os.path.exists(pose_path):
        os.unlink(pose_path)
    elif args.keep_json:
        print(f"\n  Pose JSON saved: {pose_path}")
        print(f"  Upload it at http://localhost:8000 for the full interactive report.\n")


if __name__ == "__main__":
    main()
