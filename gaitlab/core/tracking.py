"""Per-frame tracking trust for one limb's hip/knee/ankle chain.

A tracker can report high confidence for a landmark it has assigned to the wrong body
part -- most commonly the near and far leg swapping during an occlusion -- so reported
confidence alone cannot catch that failure mode. A fixed camera keeps a limb's
hip-knee and knee-ankle pixel lengths close to constant (modulo perspective) across a
clip, so a frame whose segment lengths break sharply from the clip's own scale is
untrustworthy regardless of its reported confidence.
"""

from __future__ import annotations

from statistics import median
from typing import List

from . import geometry as geo
from .schema import PoseSequence

# An occluded far limb on a side view normally runs its confidence in the 0.2-0.5 range
# (see tests/data's real-clip fixtures) without being mistracked, so this sits below that
# noise floor and only catches a genuine dropout, not routine occlusion.
# TODO: calibrate against a labeled tracking-failure clip rather than the noise floor alone.
MIN_CONFIDENCE = 0.15

# A genuinely mistracked limb (e.g. a near/far leg swap) typically reports a segment
# length far outside this band; normal perspective and pose noise stay well within it.
SEGMENT_RATIO_BAND = (0.5, 1.7)

# Below this many confidently-tracked frames, a per-clip segment-length median is
# itself too noisy to judge plausibility against.
MIN_FRAMES_FOR_SEGMENT_CHECK = 5


def leg_trust(seq: PoseSequence, side: str, min_confidence: float = MIN_CONFIDENCE) -> List[bool]:
    """Per-frame trust for `side`'s hip-knee-ankle chain."""
    hip_i, knee_i, ankle_i = (seq.idx(f"{side}_hip"), seq.idx(f"{side}_knee"), seq.idx(f"{side}_ankle"))
    confident = [min(fr[hip_i][2], fr[knee_i][2], fr[ankle_i][2]) >= min_confidence
                 for fr in seq.frames]

    thighs = [geo.distance(fr[hip_i][:2], fr[knee_i][:2]) for fr, ok in zip(seq.frames, confident) if ok]
    shanks = [geo.distance(fr[knee_i][:2], fr[ankle_i][:2]) for fr, ok in zip(seq.frames, confident) if ok]
    if len(thighs) < MIN_FRAMES_FOR_SEGMENT_CHECK or len(shanks) < MIN_FRAMES_FOR_SEGMENT_CHECK:
        return confident

    med_thigh, med_shank = median(thighs), median(shanks)
    lo, hi = SEGMENT_RATIO_BAND
    trust: List[bool] = []
    for fr, ok in zip(seq.frames, confident):
        if not ok:
            trust.append(False)
            continue
        thigh = geo.distance(fr[hip_i][:2], fr[knee_i][:2])
        shank = geo.distance(fr[knee_i][:2], fr[ankle_i][:2])
        trust.append(lo * med_thigh <= thigh <= hi * med_thigh and
                     lo * med_shank <= shank <= hi * med_shank)
    return trust
