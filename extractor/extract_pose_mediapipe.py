#!/usr/bin/env python3
"""OPTIONAL alternative extractor: pose from video using MediaPipe BlazePose.

This exists to demonstrate the **swappable pose source** — it emits the exact same
normalized JSON as the RTMPose extractor, so the GaitLab engine/UI consume it
identically. RTMPose (extract_pose.py) is the default (sharper foot keypoints); this is
a lighter, install-once alternative.

    pip install mediapipe opencv-python
    python extractor/extract_pose_mediapipe.py myrun.mp4 --view side-left -o myrun.pose.json

Thin CLI over MediaPipeExtractor (extractor/blazepose.py) — see that module for the
extraction logic itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractor.blazepose import MediaPipeExtractor  # noqa: E402


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
        seq = MediaPipeExtractor().extract(
            args.video, args.view, every=args.every,
            max_seconds=args.max_seconds, no_ffprobe=args.no_ffprobe,
        )
    except RuntimeError as e:
        sys.exit(str(e))

    path = args.output or (os.path.splitext(args.video)[0] + ".pose.json")
    with open(path, "w") as fh:
        json.dump(seq.to_pose_dict(), fh)
    print(f"\nWrote {seq.n} frames -> {path}", file=sys.stderr)
    print(path)


if __name__ == "__main__":
    main()
