#!/usr/bin/env python3
"""Generate the synthetic "golden" pose fixture used by the test suite.

tests/fixtures/golden_pose.json stands in for a real running clip in a handful
of tests that want something messier than perfectly-clean synthetic data (real
pose estimators produce positional noise and variable per-keypoint tracking
confidence; the plain synthetic generator does neither). It is entirely
synthetic — no real video or person's movement data — deterministic (fixed
seed), and safe to commit.

Run this again (and re-run `GAITLAB_UPDATE_SNAPSHOT=1 pytest
tests/test_integration_golden.py`) if you intentionally change the parameters
below.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "tests" / "fixtures" / "golden_pose.json"

import sys
sys.path.insert(0, str(REPO))

from gaitlab import synthetic
from gaitlab.core.schema import KEYPOINTS

# Keypoints that real pose estimators most often lose track of (occlusion by
# the opposite limb, motion blur at foot contact) — degraded on a subset of
# frames below so the confidence-propagation logic has something real to do.
FLAKY_KEYPOINTS = ["l_heel", "r_heel", "l_ankle", "r_ankle"]


def build() -> dict:
    seq = synthetic.generate(
        view="rear", fps=30.0, duration=9.0, cadence=168.0,
        asymmetry=0.4, noise=2.0, seed=42,
    )
    rng = random.Random(7)
    frames = [list(fr) for fr in seq.frames]
    for f in range(len(frames)):
        if rng.random() < 0.15:  # ~15% of frames get a degraded keypoint
            name = rng.choice(FLAKY_KEYPOINTS)
            x, y, _conf = frames[f][KEYPOINTS.index(name)]
            frames[f][KEYPOINTS.index(name)] = (x, y, rng.uniform(0.15, 0.45))
    seq.frames = frames
    return seq.to_pose_dict()


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"Wrote {OUT_PATH.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
