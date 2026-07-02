"""Root pytest config: shared fixtures + the requirements-traceability matrix (RTM).

The RTM links each test to the spec requirement(s) it covers via the ``@pytest.mark.covers``
marker, then at the end of the run reports which requirements from ``docs/spec/metrics.yaml``
are covered. With ``--rtm-strict`` (used in CI) a coverage gap fails the run.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import pytest

REPO = Path(__file__).parent
SPEC_PATH = REPO / "docs" / "spec" / "metrics.yaml"


# ---------------------------------------------------------------------------
# Spec loading (shared by RTM here and the conformance tests)
# ---------------------------------------------------------------------------

def load_spec() -> dict:
    """Parse docs/spec/metrics.yaml; return {} if it does not exist yet."""
    if not SPEC_PATH.exists():
        return {}
    import yaml  # dev-only dep
    return yaml.safe_load(SPEC_PATH.read_text()) or {}


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

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
    """Factory → a metric values dict with every scored metric inside its good band.

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


# ---------------------------------------------------------------------------
# Requirements traceability matrix
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--rtm-strict", action="store_true", default=False,
        help="Fail the run if any 'implemented' spec requirement has no covering test.",
    )


class _RTM:
    def __init__(self) -> None:
        # req_id -> list of {"nodeid", "xfail", "outcome"}
        self.by_req: Dict[str, List[dict]] = defaultdict(list)
        self._entry: Dict[str, list] = {}  # nodeid -> list of entry dicts

    def register(self, nodeid: str, reqs, xfail: bool) -> None:
        entries = []
        for r in reqs:
            e = {"nodeid": nodeid, "xfail": xfail, "outcome": "not run"}
            self.by_req[str(r)].append(e)
            entries.append(e)
        self._entry[nodeid] = entries

    def record_outcome(self, nodeid: str, outcome: str) -> None:
        for e in self._entry.get(nodeid, []):
            e["outcome"] = outcome


def pytest_configure(config):
    config._rtm = _RTM()


def pytest_collection_modifyitems(config, items):
    rtm = config._rtm
    for item in items:
        marker = item.get_closest_marker("covers")
        if not marker:
            continue
        xfail = item.get_closest_marker("xfail") is not None
        rtm.register(item.nodeid, marker.args, xfail)


def pytest_runtest_logreport(report):
    if report.when != "call" and not (report.when == "setup" and report.skipped):
        return
    config = getattr(report, "_config", None)
    # report has no config; use the global via the session hook instead
    _RTM_OUTCOMES.append((report.nodeid, report.outcome))


_RTM_OUTCOMES: List = []


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    rtm = config._rtm
    for nodeid, outcome in _RTM_OUTCOMES:
        rtm.record_outcome(nodeid, outcome)

    spec = load_spec()
    requirements: Dict[str, dict] = (spec.get("requirements") or {}) if spec else {}

    tw = terminalreporter
    tw.write_sep("=", "requirements traceability matrix")

    if not requirements:
        tw.write_line("No requirements registry in docs/spec/metrics.yaml yet — RTM skipped.")
        return

    gaps: List[str] = []
    covered = uncovered = pending = 0
    for req_id, meta in sorted(requirements.items()):
        status = (meta or {}).get("status", "implemented")
        entries = rtm.by_req.get(req_id, [])
        real = [e for e in entries if not e["xfail"]]
        xfails = [e for e in entries if e["xfail"]]
        if status == "pending":
            pending += 1
            ok = bool(xfails)
            mark = "PEND" if ok else "GAP "
            if not ok:
                gaps.append(f"{req_id}: pending requirement has no xfail placeholder test")
        else:
            ok = any(e["outcome"] == "passed" for e in real)
            mark = "OK  " if ok else "GAP "
            if ok:
                covered += 1
            else:
                uncovered += 1
                gaps.append(f"{req_id}: no passing test covers this implemented requirement")
        n = len(entries)
        tw.write_line(f"  [{mark}] {req_id:<8} ({status}) — {n} test(s)")

    tw.write_line(f"Covered {covered}, uncovered {uncovered}, pending {pending}.")
    if gaps and config.getoption("--rtm-strict"):
        tw.write_sep("-", "RTM gaps (strict)")
        for g in gaps:
            tw.write_line(f"  ✗ {g}")


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if not config.getoption("--rtm-strict"):
        return
    rtm = getattr(config, "_rtm", None)
    if rtm is None:
        return
    for nodeid, outcome in _RTM_OUTCOMES:
        rtm.record_outcome(nodeid, outcome)
    spec = load_spec()
    requirements = (spec.get("requirements") or {}) if spec else {}
    if not requirements:
        return
    has_gap = False
    for req_id, meta in requirements.items():
        status = (meta or {}).get("status", "implemented")
        entries = rtm.by_req.get(req_id, [])
        if status == "pending":
            if not any(e["xfail"] for e in entries):
                has_gap = True
        else:
            if not any(e["outcome"] == "passed" and not e["xfail"] for e in entries):
                has_gap = True
    if has_gap and exitstatus == 0:
        session.exitstatus = 1
