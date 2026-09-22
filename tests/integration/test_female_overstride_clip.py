"""What this clip has to say beyond its ground-truth record.

Cadence, duration and fixture integrity are asserted generically in test_real_clips.py. This
module holds two findings specific to this clip that a record cannot express.
"""

from __future__ import annotations

import json

import pytest

from tests.integration.clipcase import analyse, load_clips

CLIP = next((c for c in load_clips() if c.name == "female_overstride"), None)
pytestmark = pytest.mark.skipif(CLIP is None, reason="female_overstride fixture not present")


@pytest.fixture(scope="module")
def actual():
    return analyse(CLIP)


def test_engine_reads_the_real_frame_rate():
    """Asserted so no failure here can be blamed on the timebase.

    The clip is 120 fps with real container timestamps, and gait-event detection broke on it
    anyway — the bug it was added for is frame-rate independent.
    """
    from gaitlab.core.schema import PoseSequence

    seq = PoseSequence.from_pose_dict(json.loads(CLIP.pose_path.read_text()))
    assert seq.effective_fps == pytest.approx(119.9, abs=0.5)


def test_no_spurious_ground_tilt_warning(actual):
    """The tilt check fits a line through ankle positions at detected strikes.

    Scene edges on this clip trace within 2.5 degrees and the belt line within 1.5, both under
    the check's threshold, so a warning here means the strikes are wrong rather than the camera.
    """
    tilt = [f for f in actual["_quality"] if "tilt" in f.get("message", "").lower()]
    assert not tilt, f"spurious ground-tilt warning on a clip measured level: {tilt}"


def test_reach_artifact_is_inspectable_on_the_committed_clip():
    """The curve reports what the recorded pose contains, not a transformed copy."""
    from gaitlab.core.events import detect_events
    from gaitlab.core.schema import PoseSequence
    from gaitlab.metrics.ctx import Ctx, median
    from gaitlab.metrics.defs import METRIC_DEFS
    from gaitlab.metrics.keys import MetricKey

    seq = PoseSequence.from_pose_dict(json.loads(CLIP.pose_path.read_text())).validate()
    ctx = Ctx(seq, detect_events(seq), None)

    for side in ("l", "r"):
        curve = ctx.reach_curve(side)
        assert len(curve) == seq.n
        assert [sample.frame for sample in curve] == list(range(seq.n))
        assert [sample.t for sample in curve] == [seq.time_at(frame) for frame in range(seq.n)]
        assert {sample.side for sample in curve} == {side}
        assert {sample.processing for sample in curve} == {"raw"}

        sample = curve[ctx.ev.strikes[side][0]]
        assert sample.hip == seq.pt(sample.frame, f"{side}_hip")
        assert sample.ankle == seq.pt(sample.frame, f"{side}_ankle")
        assert sample.heel == seq.pt(sample.frame, f"{side}_heel")
        assert sample.toe == seq.pt(sample.frame, f"{side}_big_toe")
        assert sample.denominator is ctx.denominator

        source = sample.denominator.samples[0]
        assert source.hip == seq.pt(source.frame, f"{source.side}_hip")
        assert source.knee == seq.pt(source.frame, f"{source.side}_knee")
        assert source.ankle == seq.pt(source.frame, f"{source.side}_ankle")

        sampled = [curve[frame].ankle_reach.pct for frame in ctx.ev.strikes[side]]
        assert METRIC_DEFS[MetricKey.OVERSTRIDE].compute(ctx, side) == median(sampled)
