"""End-to-end golden snapshot: analyze(sample_run.pose.json) vs a stored expectation.

Regenerate intentionally with:  GAITLAB_UPDATE_SNAPSHOT=1 pytest tests/test_integration_golden.py
The snapshot captures a curated, stable subset (not the echoed pose/series arrays).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from gaitlab import analyze

SNAP = Path(__file__).parent / "snapshots" / "golden_sample_run.json"
TOL = 1e-2


def _curate(d: dict) -> dict:
    return {
        "summary": {k: d["summary"][k] for k in ("view", "cadence", "overall_score", "grade", "n_findings")},
        "metrics": {c["key"]: {"value": c["value"], "status": c["status"]} for c in d["metrics"]},
        "asymmetry": {str(a["key"]): a["status"] for a in d["asymmetry"]},
        "feedback_titles": sorted(i["title"] for i in d["feedback"]),
        "quality_levels": sorted(c["level"] for c in d["quality"]),
    }


def _diff(exp, act, path=""):
    """Yield human-readable mismatches, treating numbers within TOL as equal."""
    if isinstance(exp, (int, float)) and isinstance(act, (int, float)):
        if abs(exp - act) > TOL + abs(exp) * TOL:
            yield f"{path}: {exp} != {act}"
    elif isinstance(exp, dict) and isinstance(act, dict):
        for k in set(exp) | set(act):
            if k not in exp or k not in act:
                yield f"{path}.{k}: present in only one side"
            else:
                yield from _diff(exp[k], act[k], f"{path}.{k}")
    elif isinstance(exp, list) and isinstance(act, list):
        if len(exp) != len(act):
            yield f"{path}: list length {len(exp)} != {len(act)}"
        else:
            for i, (e, a) in enumerate(zip(exp, act)):
                yield from _diff(e, a, f"{path}[{i}]")
    elif exp != act:
        yield f"{path}: {exp!r} != {act!r}"


def test_golden_snapshot(golden_pose):
    actual = _curate(analyze(golden_pose).validate().to_dict())

    if os.environ.get("GAITLAB_UPDATE_SNAPSHOT") or not SNAP.exists():
        SNAP.parent.mkdir(parents=True, exist_ok=True)
        SNAP.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"snapshot written to {SNAP.relative_to(SNAP.parent.parent)}")

    expected = json.loads(SNAP.read_text())
    diffs = list(_diff(expected, actual, "root"))
    assert not diffs, "golden snapshot drift:\n" + "\n".join(diffs)
