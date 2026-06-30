#!/usr/bin/env python3
"""OPTIONAL alternative extractor: pose from video using MediaPipe BlazePose.

This exists to demonstrate the **swappable pose source** — it emits the exact same
normalized JSON as the RTMPose extractor, so the GaitLab engine/UI consume it
identically. RTMPose (extract_pose.py) is the default (sharper foot keypoints); this is
a lighter, install-once alternative.

    pip install mediapipe opencv-python
    python extractor/extract_pose_mediapipe.py myrun.mp4 --view side-left -o myrun.pose.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gaitlab.schema import KEYPOINTS, SCHEMA_VERSION  # noqa: E402


def probe_timestamps(path):
    """Real per-frame presentation timestamps (seconds), via ffprobe.

    Reads the container's actual frame PTS — the same clock the browser's <video>
    uses — so the overlay stays aligned even on variable-frame-rate phone video,
    where OpenCV's CAP_PROP_POS_MSEC is unreliable. Returns a list sorted ascending
    (presentation order), or None if ffprobe is missing / the probe fails.
    """
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "frame=best_effort_timestamp_time",
             "-of", "csv=print_section=0", path],
            capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    vals = []
    for line in out.stdout.splitlines():
        s = line.strip().rstrip(",")
        if not s or s == "N/A":
            continue
        try:
            vals.append(float(s))
        except ValueError:
            continue
    if len(vals) < 2:
        return None
    vals.sort()
    return vals


def _monotonic_positive(ts):
    return (ts is not None and len(ts) > 1 and ts[-1] > 0
            and all(ts[i] >= ts[i - 1] for i in range(1, len(ts))))


def _choose_timestamps(probe_ts, pos_msec, kept_idx, total_read):
    """Pick the best per-frame timestamp source: ffprobe PTS > OpenCV POS_MSEC > None."""
    if probe_ts is not None and kept_idx and len(probe_ts) >= total_read:
        picked = [probe_ts[i] for i in kept_idx]
        if _monotonic_positive(picked):
            return picked, "ffprobe (real container PTS)"
    if _monotonic_positive(pos_msec):
        return pos_msec, "OpenCV POS_MSEC"
    return None, "constant frame rate (f/fps) — overlay may drift on VFR video"

# MediaPipe BlazePose 33-landmark indices -> canonical names. BlazePose has no neck /
# pelvis / small-toe, so neck & mid_hip are derived and small toes are left absent.
BLAZEPOSE = {
    "nose": 0,
    "l_shoulder": 11, "r_shoulder": 12, "l_elbow": 13, "r_elbow": 14, "l_wrist": 15, "r_wrist": 16,
    "l_hip": 23, "r_hip": 24, "l_knee": 25, "r_knee": 26, "l_ankle": 27, "r_ankle": 28,
    "l_heel": 29, "r_heel": 30, "l_big_toe": 31, "r_big_toe": 32,
}


def to_canonical(lm, w: int, h: int):
    def P(i):
        return [lm[i].x * w, lm[i].y * h, float(getattr(lm[i], "visibility", 1.0))]

    frame = []
    for name in KEYPOINTS:
        if name in BLAZEPOSE:
            frame.append(P(BLAZEPOSE[name]))
        elif name == "neck":
            a, b = P(11), P(12)
            frame.append([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, min(a[2], b[2])])
        elif name == "mid_hip":
            a, b = P(23), P(24)
            frame.append([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, min(a[2], b[2])])
        else:
            frame.append([0.0, 0.0, 0.0])
    return frame


def main():
    ap = argparse.ArgumentParser(description="Extract MediaPipe BlazePose landmarks to gaitlab pose JSON.")
    ap.add_argument("video")
    ap.add_argument("--view", default="side-left", choices=["side-left", "side-right", "rear", "front"])
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--no-ffprobe", action="store_true",
                    help="skip ffprobe PTS probe (use OpenCV timestamps / constant rate)")
    args = ap.parse_args()

    try:
        import cv2
        import mediapipe as mp
    except ImportError:
        sys.exit("Needs MediaPipe. Run:\n  pip install mediapipe opencv-python")

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit("could not open video: " + args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    pose = mp.solutions.pose.Pose(model_complexity=2, min_detection_confidence=0.5)
    print(f"Running MediaPipe BlazePose on {args.video} ({width}x{height} @ {fps:.0f}fps)…", file=sys.stderr)

    probe_ts = None if args.no_ffprobe else probe_timestamps(args.video)

    frames = []
    pos_msec = []
    kept_idx = []
    read_i = 0
    max_frames = int(args.max_seconds * fps) if args.max_seconds else None
    while True:
        t_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
        ok, img = cap.read()
        if not ok:
            break
        if read_i % args.every == 0:
            res = pose.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            if res.pose_landmarks:
                frames.append(to_canonical(res.pose_landmarks.landmark, width, height))
            else:
                frames.append([[0.0, 0.0, 0.0] for _ in KEYPOINTS])
            pos_msec.append(t_msec / 1000.0)
            kept_idx.append(read_i)
            if len(frames) % 15 == 0:
                print(f"\r  {len(frames)} frames analyzed…", end="", file=sys.stderr)
        read_i += 1
        if max_frames and read_i >= max_frames:
            break
    cap.release()

    timestamps, ts_src = _choose_timestamps(probe_ts, pos_msec, kept_idx, read_i)
    print(f"\n  timestamp source: {ts_src}", file=sys.stderr)

    out = {
        "schema": SCHEMA_VERSION, "source": "mediapipe-blazepose", "view": args.view,
        "fps": fps / args.every, "width": width, "height": height,
        "keypoint_names": list(KEYPOINTS),
        "frames": [[[round(v, 3) for v in p] for p in fr] for fr in frames],
    }
    if timestamps is not None:
        out["timestamps"] = [round(t, 4) for t in timestamps]
    path = args.output or (os.path.splitext(args.video)[0] + ".pose.json")
    with open(path, "w") as fh:
        json.dump(out, fh)
    print(f"\nWrote {len(frames)} frames -> {path}", file=sys.stderr)
    print(path)


if __name__ == "__main__":
    main()
