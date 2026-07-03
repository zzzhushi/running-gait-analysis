#!/usr/bin/env python3
"""Emit golden fixtures for the Pyodide==Python parity test.

Each fixture is an input pose (<name>.input.json) + the Python engine's result
(<name>.result.json). The parity test (web/tests/parity.mjs) runs each input through the
SAME engine inside Pyodide and deep-equals the result. Regenerating is a deliberate,
reviewed step: run `python3 scripts/gen_web_fixtures.py` and commit the diff.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gaitlab import analyze, synthetic  # noqa: E402
from gaitlab.core.schema import PoseSequence  # noqa: E402

OUT = ROOT / "web" / "tests" / "fixtures"

# A few scenario cells: clean side, rear w/ injected asymmetry, and a profile-set run.
FIXTURES = [
    {"name": "side_left_clean", "label": "side clean", "profile": None,
     "gen": dict(view="side-left", fps=60, duration=6, cadence=172, seed=1)},
    {"name": "rear_asymmetry", "label": "rear hip drop", "profile": None,
     "gen": dict(view="rear", fps=60, duration=6, cadence=170, asymmetry=0.5, seed=7)},
    {"name": "side_with_profile", "label": "side profiled",
     "profile": {"sex": "female", "height_cm": 170, "speed_kmh": 12.0},
     "gen": dict(view="side-left", fps=60, duration=6, cadence=176, seed=13)},
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in FIXTURES:
        # Round-trip through to_pose_dict() so the fixture is the exact (rounded) input the
        # browser hands the engine — both sides then start from identical bytes.
        pose = synthetic.generate(**f["gen"]).to_pose_dict()
        result = analyze(PoseSequence.from_pose_dict(pose), f["label"], f["profile"]).to_dict()
        (OUT / f"{f['name']}.input.json").write_text(json.dumps(pose))
        (OUT / f"{f['name']}.result.json").write_text(json.dumps(result))
        print(f"wrote {f['name']}  ({len(pose['frames'])} frames)")


if __name__ == "__main__":
    main()
