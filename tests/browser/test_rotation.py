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

There is no independent pixel-level ground truth for this derivative, so correctness is
checked the way a broken rotation would actually manifest: MediaPipe cannot find a person
in a sideways video. The unrotated reference (tests/data/male_side.pose.blazepose.json)
detects a pose in 100% of frames; a rotation-handling regression would collapse that
fraction, not shift it slightly.
"""

from __future__ import annotations

import json
from pathlib import Path

from gaitlab.core.schema import PoseSequence

DATA = Path(__file__).resolve().parents[1] / "data"
CLIP = "rotated_male_side.mp4"

# The source file's coded (pre-rotation) dimensions.
CODED_WIDTH, CODED_HEIGHT = 720, 1280

# tests/data/male_side.pose.blazepose.json detects a pose in every frame; an unrotated
# (broken) decode of this file should detect close to none.
MAX_UNDETECTED_FRACTION = 0.05

_EXTRACT = """
async ([url, view]) => {
  const { extract } = await import('/web/js/pose.js');
  return await extract(url, view, () => {});
}
"""


def _undetected_fraction(pose: dict) -> float:
    blank = sum(1 for fr in pose["frames"] if all(p[2] == 0.0 for p in fr))
    return blank / len(pose["frames"])


def test_rotated_clip_decodes_in_display_orientation(page, site):
    url = f"{site}/tests/browser/{CLIP}"
    pose = page.evaluate(_EXTRACT, [url, "side-left"])

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
