"""What this clip has to say beyond its ground-truth record.

Cadence, duration and fixture integrity are asserted generically in test_real_clips.py. This
module exists for the one finding the clip produced that a record cannot express: contact time
and duty factor are wrong for a reason that is not a calibration error, and the sweep showing
that is worth keeping next to the assertion.
"""

from __future__ import annotations

import json

import pytest

from tests.integration.clipcase import analyse, load_clips

CLIP = next((c for c in load_clips() if c.name == "female_overstride"), None)
pytestmark = pytest.mark.skipif(CLIP is None, reason="female_overstride fixture not present")

# Remove when contact detection is defined by motion rather than by height. Do not widen a
# band to clear these: the measured truth is 505 +/- 25 ms and the bands are +/-15% already.
uncalibrated_stance = pytest.mark.xfail(
    strict=True,
    reason="ankle-amplitude contact proxy is uncalibrated; see this module's docstring",
)


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


def test_duty_factor_and_flight_time_do_not_contradict_each_other(actual):
    """Double-support duty factor and positive flight time cannot coexist."""
    assert not (actual["duty_factor"] > 50.0 and actual["flight_time"] > 0.0), (
        f"duty factor {actual['duty_factor']:.1f}% says both feet are down at once, but "
        f"flight time is {actual['flight_time']:.0f} ms"
    )


def test_no_spurious_ground_tilt_warning(actual):
    """The tilt check fits a line through ankle positions at detected strikes.

    Scene edges on this clip trace within 2.5 degrees and the belt line within 1.5, both under
    the check's threshold, so a warning here means the strikes are wrong rather than the camera.
    """
    tilt = [f for f in actual["_quality"] if "tilt" in f.get("message", "").lower()]
    assert not tilt, f"spurious ground-tilt warning on a clip measured level: {tilt}"


@uncalibrated_stance
def test_contact_time_is_physiological(actual):
    """Contact time against the clip's own pixel-measured 505 ms.

    LIFT_FRACTION thresholds a fraction of the ankle's peak-to-peak range, and most of that
    range is swing-phase lift. Swept against both real clips at once:

        LIFT_FRACTION   this clip (truth 505 ms / 44%)   male_side (180-320 ms / 25-48%)
        0.15 (current)  394 ms / 34.1%                   241 ms / 34.5%   ok
        0.20            440 ms / 37.7%                   308 ms / 44.0%   ok
        0.30            505 ms / 43.3%   exact           388 ms / 55.4%   impossible

    No value satisfies both. 0.20 clears every band assertion, but by landing inside bands
    rather than matching either measurement, and it moves male_side's duty factor ten points
    on a clip whose contact time was never measured.

    A vertical-velocity threshold was prototyped and fails the same way, so the problem is not
    the choice of signal: the calibration is under-determined with one measured clip.
    """
    assert 430 <= actual["contact_time"] <= 580


@uncalibrated_stance
def test_duty_factor_is_physiological(actual):
    assert 36 <= actual["duty_factor"] <= 50
