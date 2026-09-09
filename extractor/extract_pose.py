#!/usr/bin/env python3
"""Extract normalized pose landmarks from a running video using RTMPose (via rtmlib).

This is the ONE piece of GaitLab that needs third-party packages:

    pip install rtmlib onnxruntime opencv-python

It runs RTMPose locally (CPU is fine) and writes a pose .json to data/pose/.
The GaitLab app (server.py + browser UI) then analyzes that file — it needs no
model and no extra installs.

Simple usage (video already in data/video/):

    python extractor/extract_pose.py sample_run --view rear
    # reads  data/video/sample_run.mov  (or .mp4, etc.)
    # writes data/pose/sample_run.pose.json

Or with an explicit path and custom output:

    python extractor/extract_pose.py /path/to/myrun.mp4 --view side-left -o myrun.pose.json

The pose source is swappable: anything that emits this same JSON (e.g. a MediaPipe
extractor) can feed the identical analysis engine. This file is a thin CLI over
RTMPoseExtractor (extractor/rtmpose.py) — the extraction logic itself lives there so
it can be imported and swapped, which this script alone never allowed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Share the exact canonical keypoint order with the analysis engine, and make the
# extractor package importable below.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractor.rtmpose import RTMPoseExtractor  # noqa: E402


def _resolve_video(given: str) -> str:
    """Return an absolute video path, searching data/video/ if the given path doesn't exist."""
    if os.path.isfile(given):
        return given
    # Try resolving relative to the project data/video/ directory.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    video_dir = os.path.join(project_root, "data", "video")
    # Accept stem or full filename (e.g. "sample_run" or "sample_run.mov").
    stem = os.path.splitext(os.path.basename(given))[0]
    for entry in sorted(os.listdir(video_dir)) if os.path.isdir(video_dir) else []:
        if os.path.splitext(entry)[0] == stem:
            return os.path.join(video_dir, entry)
    sys.exit(f"video not found: {given!r}\n  (also searched {video_dir})")


def main():
    ap = argparse.ArgumentParser(description="Extract RTMPose landmarks to gaitlab pose JSON.")
    ap.add_argument("video", help="video filename in data/video/ (stem or full name), or an explicit path")
    ap.add_argument("--view", default="side-left", choices=["side-left", "side-right", "rear", "front"])
    ap.add_argument("-o", "--output", default=None,
                    help="output .json path (default: data/pose/<stem>.pose.json)")
    ap.add_argument("--model", default="body26", choices=["body26", "wholebody"])
    ap.add_argument("--mode", default="balanced", choices=["performance", "lightweight", "balanced"],
                    help="rtmlib speed/accuracy preset (default: balanced)")
    ap.add_argument("--accurate", action="store_true",
                    help="shortcut for --mode performance (slower, more precise keypoints)")
    ap.add_argument("--no-ffprobe", action="store_true",
                    help="skip ffprobe PTS probe (use OpenCV timestamps / constant rate)")
    ap.add_argument("--every", type=int, default=1, help="process every Nth frame (downsample)")
    ap.add_argument("--max-seconds", type=float, default=None, help="stop after N seconds of video")
    args = ap.parse_args()

    video_path = _resolve_video(args.video)
    mode = "performance" if args.accurate else args.mode

    try:
        seq = RTMPoseExtractor(model=args.model, mode=mode).extract(
            video_path, args.view, every=args.every,
            max_seconds=args.max_seconds, no_ffprobe=args.no_ffprobe,
        )
    except RuntimeError as e:
        sys.exit(str(e))

    if args.output:
        path = args.output
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pose_dir = os.path.join(project_root, "data", "pose")
        os.makedirs(pose_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(video_path))[0]
        path = os.path.join(pose_dir, stem + ".pose.json")
    with open(path, "w") as fh:
        json.dump(seq.to_pose_dict(), fh)
    print(f"\nWrote {seq.n} frames -> {path}", file=sys.stderr)
    print(path)


if __name__ == "__main__":
    main()
