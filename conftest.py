"""Root pytest config: shared fixtures used across the test suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).parent
SPEC_PATH = REPO / "docs" / "spec" / "metrics.yaml"


def load_spec() -> dict:
    """Parse the generated docs/spec/metrics.yaml; return {} if it doesn't exist yet."""
    if not SPEC_PATH.exists():
        return {}
    import yaml  # dev-only dep
    return yaml.safe_load(SPEC_PATH.read_text()) or {}


@pytest.fixture(scope="session")
def spec() -> dict:
    return load_spec()


@pytest.fixture
def synth():
    """The synthetic pose generator (gaitlab.synthetic.generate)."""
    from gaitlab import synthetic
    return synthetic.generate


@pytest.fixture(scope="session")
def golden_pose():
    """The checked-in golden pose fixture as a PoseSequence."""
    from gaitlab.core.schema import PoseSequence
    p = REPO / "data" / "pose" / "sample_run.pose.json"
    return PoseSequence.from_pose_dict(json.loads(p.read_text()))


def _in_band_value(good) -> float:
    """A value comfortably inside a metric's good band (for building baseline dicts)."""
    lo, hi = good
    if lo is not None and hi is not None:
        return (lo + hi) / 2.0
    if hi is not None:                       # good = (None, hi): stay below hi
        return hi - max(1.0, abs(hi) * 0.25)
    if lo is not None:                       # good = (lo, None): stay above lo
        return lo + max(2.0, abs(lo) * 0.25)
    return 0.0


@pytest.fixture
def make_values():
    """Factory -> a metric values dict with every scored metric inside its good band.

    Pass overrides to push specific metrics out of band, e.g.
        make_values("side-left", overstride=20, hip_extension=4, cadence=150)
    Tests the coaching/composite logic at the feedback.build() boundary directly,
    without fighting synthetic kinematics.
    """
    from gaitlab.metrics.defs import METRIC_DEFS

    def factory(view: str = "side-left", **overrides) -> dict:
        view_str = "side" if view in ("side-left", "side-right") else "rear"
        values: dict = {}
        for key, d in METRIC_DEFS.items():
            if view_str in d.views and (d.good != (None, None)):
                values[key.value] = _in_band_value(d.good)
        # sensible defaults for band-less / boolean metrics that feedback reads
        values.setdefault("foot_strike_angle", 0.0)
        values.setdefault("head_drop", 2.0)
        values.setdefault("head_lateral_sway", 2.0)
        values.setdefault("crossover", False)
        values.setdefault("arm_crossover", False)
        values.update(overrides)
        return values

    return factory
