"""Display-rotation handling in the WebCodecs extraction path.

VideoDecoder decodes coded (pre-rotation) pixels only; it does not apply a container's
display-rotation matrix the way <video> playback does for free. web/js/pose.js has to
read and apply that transform itself (rotationFromMatrix / canvasTransformFor), or a
portrait phone clip decodes sideways -- reintroducing #62 for exactly the footage that
bug was originally about, this time through the new extraction path.

rotated_male_side.mp4 is a lossless remux of the already-consented tests/data/male_side.mp4
(-c copy, no re-encode -- identical pixels) with a 90-degree display-rotation tag added via
`ffmpeg -display_rotation:v:0 90 -i ... -c copy`. It needs no separate consent: same footage,
same person, same license, only the container's rotation metadata differs.

Dimensions and detection rate alone do not prove the rotation direction is correct: two
transforms 180 degrees apart both swap width/height, and BlazePose can often still find a
person in a merely-mirrored frame, so a test that only checked those two properties would
pass under either the right transform or its mirror image. (Confirmed by mutation testing
canvasTransformFor's 90/270 cases against each other -- both keep this file's detection
rate near 0% undetected.) `test_rotation_direction_matches_the_declared_transform` below
is the check that actually distinguishes them, using the one piece of independent ground
truth available without a pixel-rendering harness: the coded-space reference extraction
already committed for this footage.

male_side.mp4's tkhd carries no rotation (rotationFromMatrix returns the identity case),
so tests/data/male_side.pose.blazepose.json's landmarks are in the *coded* frame. This
file's matrix declares a transform whose (a, b, c, d) are exactly canvasTransformFor's
case-270 coefficients (display_x = coded_y, i.e. a person's coded-space vertical bob
becomes horizontal motion in +x after correction). That sign is specific to this one
transform: the alternative 90-degree case produces display_x = codedHeight - coded_y,
the opposite sign. Comparing the reference's coded mid_hip.y trajectory against this
extraction's display mid_hip.x trajectory, frame for frame -- both are the identical
underlying footage, so they must correlate -- catches exactly the case-90/case-270
mutation dimensions and detection rate cannot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaitlab.core.schema import PoseSequence

DATA = Path(__file__).resolve().parents[1] / "data"
CLIP = "rotated_male_side.mp4"
REFERENCE = "male_side.pose.blazepose.json"

# Same footage, same license, only the tkhd display matrix differs: a genuine mirror
# flip (determinant -1: a=-1, b=0, c=0, d=1), via `ffmpeg -display_hflip:v:0 -i ... -c
# copy` -- one of the "shear, perspective, an unrecognised flip" cases
# rotationFromMatrix's own comment names but nothing exercised until this test.
MIRRORED_CLIP = "mirrored_male_side.mp4"

# The source file's coded (pre-rotation) dimensions.
CODED_WIDTH, CODED_HEIGHT = 720, 1280

MID_HIP = "mid_hip"

# tests/data/male_side.pose.blazepose.json detects a pose in every frame; an unrotated
# (broken) decode of this file should detect close to none.
MAX_UNDETECTED_FRACTION = 0.05

# This file's declared transform predicts a strong *positive* correlation between coded
# mid_hip.y (reference) and display mid_hip.x (this extraction) -- see module docstring.
# The threshold is well below what real running motion produces (checked empirically to
# be > 0.9) but far above what an unrelated or sign-flipped mapping would produce.
MIN_DIRECTIONAL_CORRELATION = 0.5

_EXTRACT = """
async ([url, view]) => {
  const { extract } = await import('/web/js/pose.js');
  return await extract(url, view, () => {});
}
"""


def _undetected_fraction(pose: dict) -> float:
    blank = sum(1 for fr in pose["frames"] if all(p[2] == 0.0 for p in fr))
    return blank / len(pose["frames"])


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return cov / (vx * vy) ** 0.5 if vx > 0 and vy > 0 else 0.0


def _extract_rotated(page, site) -> dict:
    url = f"{site}/tests/browser/{CLIP}"
    return page.evaluate(_EXTRACT, [url, "side-left"])


def test_rotated_clip_decodes_in_display_orientation(page, site):
    pose = _extract_rotated(page, site)

    # A 90-degree rotation swaps coded into display dimensions; if this reads as the
    # coded 720x1280 instead, the rotation was not detected or not applied.
    assert (pose["width"], pose["height"]) == (CODED_HEIGHT, CODED_WIDTH), (
        f"pose is {pose['width']}x{pose['height']}, expected the rotation-swapped "
        f"{CODED_HEIGHT}x{CODED_WIDTH} -- rotation was likely not applied"
    )

    undetected = _undetected_fraction(pose)
    assert undetected <= MAX_UNDETECTED_FRACTION, (
        f"{undetected:.0%} of frames have no detected pose (unrotated reference: 0%); "
        f"MediaPipe cannot find a person in this frame, consistent with the decode "
        f"still being sideways"
    )

    seq = PoseSequence.from_pose_dict(pose).validate()
    assert seq.width == CODED_HEIGHT and seq.height == CODED_WIDTH


def test_rotation_direction_matches_the_declared_transform(page, site):
    """A 180-degree-wrong rotation direction still swaps dimensions and still lets
    MediaPipe find a person, so it survives the checks above undetected. This checks
    the one property that does distinguish it: see the module docstring for the sign
    derivation.
    """
    pose = _extract_rotated(page, site)
    reference = json.loads((DATA / REFERENCE).read_text())
    assert len(pose["frames"]) == len(reference["frames"]), (
        "frame counts differ between the rotated derivative and its source reference; "
        "the correlation below assumes frame-for-frame identical underlying footage"
    )

    ref_idx = reference["keypoint_names"].index(MID_HIP)
    my_idx = pose["keypoint_names"].index(MID_HIP)
    ref_y = [fr[ref_idx][1] for fr in reference["frames"]]
    my_x = [fr[my_idx][0] for fr in pose["frames"]]

    r = _pearson(ref_y, my_x)
    assert r >= MIN_DIRECTIONAL_CORRELATION, (
        f"correlation between reference coded mid_hip.y and this extraction's display "
        f"mid_hip.x is {r:+.2f}, expected >= {MIN_DIRECTIONAL_CORRELATION:+.2f}; a "
        f"transform swapped for its 180-degree-opposite would produce a negative or "
        f"near-zero value here even though dimensions and detection rate still pass"
    )


def test_unsupported_transform_rejects_before_inference(page, site):
    """rotationFromMatrix() returning null is not enough on its own -- a prior version
    of this codebase computed that value and then discarded it with a `|| identity`
    fallback at the one call site, silently scoring a mirrored frame as if it were
    upright. This exercises the caller, not just the helper: extract() itself must
    reject a file it cannot orient, before any frame reaches the pose model.
    """
    url = f"{site}/tests/browser/{MIRRORED_CLIP}"
    with pytest.raises(Exception, match="[Oo]rientation"):
        page.evaluate(_EXTRACT, [url, "side-left"])
