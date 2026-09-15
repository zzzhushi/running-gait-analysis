"""Gait-event detection from normalized landmarks.

A foot is on the ground while its ankle sits near its lowest point in the image (largest
y). Over one stance phase that traces a plateau in the ankle-y signal, not a spike: the
foot touches down, stays down while the body passes over it, then lifts.

We locate each stance with a peak of the (smoothed) ankle-y signal — robust, one per step
— but the peak sits in the *middle* of that plateau, so it is midstance, not contact.
Initial contact is the plateau's leading edge and toe-off its trailing edge, so both are
found by walking outward from the peak until the foot has lifted `LIFT_FRACTION` of its
vertical range. Using the same threshold on both sides keeps stance symmetric about
midstance.

This matters because it is the anchor for everything downstream. Reporting the peak itself
as the strike put every contact-time metric about half a step late: measured on a real
30 fps clip the peak lagged true touchdown by ~5 frames (167 ms, roughly half a step),
which halved ground contact time (133 ms, physiological ~200-300) and duty factor (19%,
physiological ~30-40), and moved overstride — defined as the foot's position *at contact*
— from a large positive value to roughly zero. See tests/integration/test_male_side_clip.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, median
from typing import Dict, List, Tuple

from . import geometry as geo
from .schema import PoseSequence

# How far the ankle must rise from its midstance low before the foot counts as off the
# ground. Used symmetrically for initial contact and toe-off, so stance stays centred on
# midstance.
#
# PROVISIONAL — this value is bounded, not calibrated. Running has no double-support
# phase, so duty factor must stay under 50%; on the real-clip fixture 0.25 gives 52%
# (physically impossible, both feet down at once) and 0.20 gives 48% with measurable
# left/right stance overlap. 0.15 gives 233 ms contact / 33% duty, which is physiological
# for a recreational runner at ~168 spm, with essentially no overlap.
#
# It is now verified against a reference, and the answer is that it is UNFITTABLE, not
# merely uncalibrated. tests/data/female_overstride.mp4 is the 120 fps clip this comment
# used to ask for, with a contact time measured from pixels at 505 +/- 25 ms. Swept against
# both real clips at once:
#
#     LIFT_FRACTION   female_overstride (truth 505 ms / 44%)   male_side (180-320 ms / 25-48%)
#     0.15            394 ms / 34.1%                           241 ms / 34.5%   ok
#     0.20            440 ms / 37.7%                           308 ms / 44.0%   ok
#     0.30            505 ms / 43.3%  exact                    388 ms / 55.4%   impossible
#
# No single value satisfies both. 0.15 is kept because it is the only one that leaves
# male_side comfortably inside its bands, and because moving it would be tuning to a test:
# 0.20 clears every band assertion but matches neither clip's measurement.
#
# The reason a constant cannot work is structural. This thresholds a fraction of the ankle's
# peak-to-peak range over the whole clip, and most of that range is swing-phase lift, which
# has nothing to do with the ground. The ankle is also not the sole — it keeps moving through
# stance as the foot rolls — so the ankle-y plateau is systematically shorter than true
# foot-ground contact by an amount that depends on strike pattern. A fixed fraction of an
# amplitude is not a definition of "the foot is loading the ground"; foot velocity matching
# ground velocity is. Until that lands, treat contact time and duty factor as approximate —
# which is what metrics/quality.py already warns about.
LIFT_FRACTION = 0.15

# Peak spacing floor, as a fraction of the measured stride. The spurious swing-phase peak
# sits near 0.4 of the stride and a real one at 1.0, so 0.6 separates them with margin on
# both sides.
PEAK_SPACING_FRACTION = 0.6
# Stride periods the search will consider, in seconds: 240 spm down to 60 spm.
MIN_STRIDE_S = 0.5
MAX_STRIDE_S = 2.0


def _robust_period(gaps: List[float], expect: float = float("nan")) -> float:
    """Typical interval from a list of elapsed-time gaps.

    A plain median is robust to spurious events but quantized when timestamps are unavailable:
    at 30 fps a ~10.7-frame step can only ever report as 10 or 11. That lands on a coarse
    cadence grid — 150 / 156.5 / 163.6 / 171.4 / 180 spm — and on the real-clip fixture it
    put a true 168.6 spm at 163.6 (-2.9%), far enough below the 170 spm target band to
    manufacture a "raise your cadence" finding the runner did not warrant.

    A plain mean recovers the sub-frame value but is wrecked by the occasional spurious
    contact: on that same clip 7 of 116 gaps were fragments (2-8 frames) from double-
    detected events, dragging the mean to 176.2 spm (+4.5%).

    So: trim to gaps near a reference, then average what survives. Robust and unquantized —
    169.7 spm on the fixture (+0.7%).

    `expect` is that reference when the caller already knows roughly what the interval should
    be, measured independently of these gaps. Prefer it. The median is only a stand-in for a
    reference, and it is not a robust one: it breaks down at 50% contamination, which is
    exactly what a spurious event *per stride* produces. On the female_overstride fixture the
    merged step gaps had a median of 0.358 s, so the window came out [0.215, 0.573] while the
    true step period was 0.5837 s — the one correct gap in the list was trimmed away and the
    result looked plausible at 126.9 spm. A reference that does not come from the contaminated
    sample cannot fail that way, so it also earns a tighter window.
    """
    if not gaps:
        return float("nan")
    anchor = expect if (expect == expect and expect > 0) else median(gaps)
    if anchor <= 0:
        return float("nan")
    lo, hi = ((0.8, 1.2) if (expect == expect and expect > 0) else (0.6, 1.6))
    kept = [g for g in gaps if lo * anchor <= g <= hi * anchor]
    return mean(kept) if kept else anchor


@dataclass
class GaitEvents:
    strikes: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    toeoffs: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    stance: Dict[str, List[Tuple[int, int]]] = field(default_factory=lambda: {"l": [], "r": []})
    # The ankle-y peaks themselves: one per stance, the most sharply-defined event the
    # signal offers. Timing-only quantities (cadence, stride time) are derived from these
    # rather than from the refined contact frames — see the note in detect_events.
    midstances: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    cadence_spm: float = float("nan")
    stride_time: Dict[str, float] = field(default_factory=dict)   # seconds, median
    contact_time: Dict[str, float] = field(default_factory=dict)  # seconds, median

    def midstance(self, side: str) -> List[int]:
        return list(self.midstances[side])


def detect_events(seq: PoseSequence) -> GaitEvents:
    ev = GaitEvents()
    # Use the real presentation clock when available. Container FPS is only metadata on
    # variable-frame-rate recordings and becomes wrong as soon as extraction drops frames.
    fps = seq.effective_fps or 30.0
    n = seq.n
    if n < 4:
        return ev

    # Peaks are found per foot, so consecutive peaks on one side are a STRIDE apart, not a
    # step, and the swing phase puts a secondary low between each pair of real ones.
    # Rejecting that bump needs a spacing floor — but the bump sits at a roughly fixed
    # FRACTION of the stride (~0.4), not at a fixed number of seconds, so an absolute-time
    # floor cannot do it. `fps * 0.35` held at 168.9 spm (stride 0.71 s, bump 0.28 s out)
    # and failed at 102.8 spm (stride 1.17 s, bump 0.47 s out), reporting 126.9 spm and
    # twice the true number of contacts. No constant fixes that: rejecting a 100 spm
    # runner's bump needs >0.5 s, admitting a 220 spm sprint stride needs <0.545 s.
    #
    # So measure the stride from the signal and scale the floor to it. 0.6 sits between the
    # bump at ~0.4 and a real stride at 1.0 — the middle of a flat region, not a knife edge.
    # See tests/integration/test_female_overstride_clip.py.
    fallback_min_dist = max(3, int(fps * 0.35))
    stride_s: Dict[str, float] = {}

    for side in ("l", "r"):
        ankle_y = geo.moving_average(seq.series_y(f"{side}_ankle"), 3)
        amp = geo.peak_to_peak(ankle_y)
        if amp != amp or amp <= 0:
            continue
        # Stride period straight from the ankle-y signal, independent of the peaks below —
        # a period derived from those peaks could not be used to judge whether they are real.
        period = geo.dominant_period(ankle_y, int(MIN_STRIDE_S * fps), int(MAX_STRIDE_S * fps))
        if period == period:
            stride_s[side] = period / fps
            min_dist = max(3, int(period * PEAK_SPACING_FRACTION))
        else:
            min_dist = fallback_min_dist
        # One peak per stance — midstance, the middle of the foot-down plateau.
        midstances = geo.find_peaks(ankle_y, min_distance=min_dist, min_prominence=amp * 0.12)

        # Contact and toe-off are the plateau's edges: walk outward from midstance until
        # the foot has lifted LIFT_FRACTION of its vertical range.
        lift_thresh = amp * LIFT_FRACTION
        strikes: List[int] = []
        toeoffs: List[int] = []
        stance: List[Tuple[int, int]] = []
        for k, mid in enumerate(midstances):
            top = ankle_y[mid]

            # backwards to initial contact, not past the previous stance
            prev_mid = midstances[k - 1] if k else -1
            s = mid
            while s - 1 > prev_mid and top - ankle_y[s - 1] < lift_thresh:
                s -= 1

            # forwards to toe-off, not past the next stance
            next_mid = midstances[k + 1] if k + 1 < len(midstances) else n
            to = None
            for i in range(mid + 1, next_mid):
                if top - ankle_y[i] >= lift_thresh:
                    to = i
                    break
            if to is None:
                to = min(next_mid - 1, mid + int(fps * 0.20))

            strikes.append(s)
            toeoffs.append(to)
            stance.append((s, to))
        ev.strikes[side] = strikes
        ev.toeoffs[side] = toeoffs
        ev.stance[side] = stance
        ev.midstances[side] = midstances

        # Stride/step timing comes from the PEAKS, not the refined contacts. The peak is a
        # single well-defined extremum; the contact frame is a threshold crossing on a
        # rounded shoulder, so it carries a frame or two of jitter. That jitter is
        # irrelevant to stance duration (both edges move together) but it lands directly in
        # the step intervals, and cadence is the most-read number in the report. Measured
        # on the real-clip fixture, deriving cadence from refined contacts moved it from
        # 163.6 to 180 spm against a measured truth of 168.6.
        same_foot = [seq.elapsed(midstances[i], midstances[i + 1])
                     for i in range(len(midstances) - 1)]
        if same_foot:
            ev.stride_time[side] = _robust_period(same_foot, stride_s.get(side, float("nan")))
        contacts = [seq.elapsed(s, to) for (s, to) in stance]
        if contacts:
            ev.contact_time[side] = _robust_period(contacts)

    # Cadence from the merged (either-foot) step interval. Merging is what makes this
    # accurate — twice the samples, and the left/right phase jitter averages out — but it is
    # also what makes it fragile, because one spurious peak on either foot lands next to a
    # real one on the other and injects a near-zero gap. So anchor the trim on half the
    # measured stride rather than on these gaps' own median.
    all_mid = sorted(ev.midstances["l"] + ev.midstances["r"])
    steps = [seq.elapsed(all_mid[i], all_mid[i + 1]) for i in range(len(all_mid) - 1)]
    measured = [v for v in stride_s.values() if v == v and v > 0]
    expect_step = (sum(measured) / len(measured) / 2.0) if measured else float("nan")
    step_s = _robust_period(steps, expect_step)
    if step_s == step_s and step_s > 0:
        ev.cadence_spm = 60.0 / step_s
    return ev
