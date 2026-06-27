#!/usr/bin/env python3
"""Extract normalized pose landmarks from a running video using RTMPose (via rtmlib).

This is the ONE piece of GaitLab that needs third-party packages:

    pip install rtmlib onnxruntime opencv-python

It runs RTMPose locally (CPU is fine) and writes a pose .json in the gaitlab
normalized format. The GaitLab app (server.py + browser UI) then analyzes that
file — it needs no model and no extra installs.

    python extractor/extract_pose.py myrun.mp4 --view side-left -o myrun.pose.json

The pose source is swappable: anything that emits this same JSON (e.g. a MediaPipe
extractor) can feed the identical analysis engine.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Share the exact canonical keypoint order with the analysis engine.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gaitlab.schema import KEYPOINTS, SCHEMA_VERSION  # noqa: E402

# RTMPose body+feet (Halpe26). Has the 6 foot keypoints we care about.
HALPE26 = {
    "nose": 0, "neck": 18, "mid_hip": 19,
    "l_shoulder": 5, "r_shoulder": 6, "l_elbow": 7, "r_elbow": 8, "l_wrist": 9, "r_wrist": 10,
    "l_hip": 11, "r_hip": 12, "l_knee": 13, "r_knee": 14, "l_ankle": 15, "r_ankle": 16,
    "l_heel": 24, "r_heel": 25, "l_big_toe": 20, "r_big_toe": 21, "l_small_toe": 22, "r_small_toe": 23,
}
# RTMPose whole-body (COCO-WholeBody 133). neck / mid_hip are derived from shoulders / hips.
WHOLEBODY = {
    "nose": 0,
    "l_shoulder": 5, "r_shoulder": 6, "l_elbow": 7, "r_elbow": 8, "l_wrist": 9, "r_wrist": 10,
    "l_hip": 11, "r_hip": 12, "l_knee": 13, "r_knee": 14, "l_ankle": 15, "r_ankle": 16,
    "l_big_toe": 17, "l_small_toe": 18, "l_heel": 19, "r_big_toe": 20, "r_small_toe": 21, "r_heel": 22,
}


def build_model(kind: str):
    try:
        from rtmlib import BodyWithFeet, Wholebody
    except ImportError:
        sys.exit("rtmlib is not installed. Run:\n  pip install rtmlib onnxruntime opencv-python")
    if kind == "wholebody":
        return Wholebody(mode="balanced", backend="onnxruntime", device="cpu"), WHOLEBODY, "rtmpose-wholebody"
    return BodyWithFeet(mode="balanced", backend="onnxruntime", device="cpu"), HALPE26, "rtmpose-halpe26"


def pick_person(keypoints, scores):
    """Choose the most confident detected person (assume one runner)."""
    if keypoints is None or len(keypoints) == 0:
        return None, None
    best = max(range(len(scores)), key=lambda i: float(scores[i].mean()))
    return keypoints[best], scores[best]


def to_canonical(kp, sc, idxmap):
    frame = []
    for name in KEYPOINTS:
        if name in idxmap:
            i = idxmap[name]
            frame.append([float(kp[i][0]), float(kp[i][1]), float(sc[i])])
        elif name == "neck" and "l_shoulder" in idxmap:
            a, b = idxmap["l_shoulder"], idxmap["r_shoulder"]
            frame.append([float((kp[a][0] + kp[b][0]) / 2), float((kp[a][1] + kp[b][1]) / 2), float(min(sc[a], sc[b]))])
        elif name == "mid_hip" and "l_hip" in idxmap:
            a, b = idxmap["l_hip"], idxmap["r_hip"]
            frame.append([float((kp[a][0] + kp[b][0]) / 2), float((kp[a][1] + kp[b][1]) / 2), float(min(sc[a], sc[b]))])
        else:
            frame.append([0.0, 0.0, 0.0])
    return frame


def main():
    ap = argparse.ArgumentParser(description="Extract RTMPose landmarks to gaitlab pose JSON.")
    ap.add_argument("video", help="path to the running video")
    ap.add_argument("--view", default="side-left", choices=["side-left", "side-right", "rear", "front"])
    ap.add_argument("-o", "--output", default=None, help="output .json (default: <video>.pose.json)")
    ap.add_argument("--model", default="body26", choices=["body26", "wholebody"])
    ap.add_argument("--every", type=int, default=1, help="process every Nth frame (downsample)")
    ap.add_argument("--max-seconds", type=float, default=None, help="stop after N seconds of video")
    args = ap.parse_args()

    try:
        import cv2
    except ImportError:
        sys.exit("opencv is not installed. Run:\n  pip install rtmlib onnxruntime opencv-python")

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit("could not open video: " + args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    model, idxmap, source = build_model(args.model)
    print(f"Running {source} on {args.video} ({width}x{height} @ {fps:.0f}fps)…", file=sys.stderr)

    frames = []
    read_i = 0
    max_frames = int(args.max_seconds * fps) if args.max_seconds else None
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if read_i % args.every == 0:
            kps, scs = model(img)
            kp, sc = pick_person(kps, scs)
            frames.append(to_canonical(kp, sc, idxmap) if kp is not None
                          else [[0.0, 0.0, 0.0] for _ in KEYPOINTS])
            if len(frames) % 15 == 0:
                print(f"\r  {len(frames)} frames analyzed…", end="", file=sys.stderr)
        read_i += 1
        if max_frames and read_i >= max_frames:
            break
    cap.release()

    out = {
        "schema": SCHEMA_VERSION,
        "source": source,
        "view": args.view,
        "fps": fps / args.every,
        "width": width,
        "height": height,
        "keypoint_names": list(KEYPOINTS),
        "frames": [[[round(v, 3) for v in p] for p in fr] for fr in frames],
    }
    path = args.output or (os.path.splitext(args.video)[0] + ".pose.json")
    with open(path, "w") as fh:
        json.dump(out, fh)
    print(f"\nWrote {len(frames)} frames -> {path}", file=sys.stderr)
    print(path)


if __name__ == "__main__":
    main()
