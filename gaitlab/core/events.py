"""Gait-event detection from the canonical pose schema.

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

The confidence-aware outputs merged from the metric-correctness work (per-stride
series, step/flight/duty factor, sample counts, warnings) are layered on top of this
anchoring rather than in place of it: they describe the events found here instead of
re-deriving them from the raw peaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, median
from typing import Dict, List, Optional, Tuple

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
# What it is NOT is verified against a reference. At 30 fps a whole stance is only ~7
# frames, so every candidate anchor argues over 2-3 frames and none can be resolved from
# this clip alone. Pinning it down needs one 120/240 fps clip (any modern phone's slow-mo)
# where contact is unambiguous. Until then, treat contact time and duty factor as
# approximate — which is what metrics/quality.py already warns about at 30 fps.
LIFT_FRACTION = 0.15


MIN_STANCE_SPACING_S = 0.35


def _stance_peaks(seq: PoseSequence, signal: List[float], amp: float) -> List[int]:
    """One peak per stance, spaced by elapsed time rather than by a frame count.

    Peaks are found per foot, so consecutive peaks on one side are a STRIDE apart, not a
    step. The old 0.22 s floor was a step-sized bound, and at 30 fps it let a secondary
    low in the swing phase through as an extra contact: at 150 spm the detector found 25
    peaks instead of 13 (gaps alternating 18, 6, 18, 6 frames) and reported 300 spm.

    Even a 220 spm sprint cadence is a 0.545 s stride, so 0.35 s cannot merge two real
    contacts while comfortably rejecting the ~0.2 s spurious bump. Anything in 0.28-0.45 s
    behaves identically across a 140-220 spm x 30/60/120 fps sweep, so this sits in the
    middle of a flat region rather than on a knife edge.

    The spacing is measured with seq.elapsed rather than converted to a frame count via
    fps. Converting made the bound depend on the declared rate while the frame-domain peak
    structure did not: relabeling a 60 fps clip's timestamps as 30 fps halved the bound
    from 21 frames to 10, admitted four swing-phase bumps (9 peaks -> 13), and the extra
    contacts cancelled the doubled step interval, so cadence reported 170 spm where the
    relabeled clock makes the truth 86. Greedy tallest-first, mirroring geo.find_peaks, so
    the strongest stance evidence still wins.
    """
    candidates = geo.find_peaks(signal, min_distance=1, min_prominence=amp * 0.12)
    chosen: List[int] = []
    for frame in sorted(candidates, key=lambda i: signal[i], reverse=True):
        if all(abs(seq.elapsed(other, frame)) >= MIN_STANCE_SPACING_S for other in chosen):
            chosen.append(frame)
    chosen.sort()
    return chosen


def _robust_period(gaps: List[float]) -> float:
    """Typical interval from a list of elapsed-time gaps.

    A plain median is robust to spurious events but quantized when timestamps are unavailable:
    at 30 fps a ~10.7-frame step can only ever report as 10 or 11. That lands on a coarse
    cadence grid — 150 / 156.5 / 163.6 / 171.4 / 180 spm — and on the real-clip fixture it
    put a true 168.6 spm at 163.6 (-2.9%), far enough below the 170 spm target band to
    manufacture a "raise your cadence" finding the runner did not warrant.

    A plain mean recovers the sub-frame value but is wrecked by the occasional spurious
    contact: on that same clip 7 of 116 gaps were fragments (2-8 frames) from double-
    detected events, dragging the mean to 176.2 spm (+4.5%).

    So: trim to gaps near the median, then average what survives. Robust and unquantized —
    169.7 spm on the fixture (+0.7%).
    """
    if not gaps:
        return float("nan")
    m = median(gaps)
    if m <= 0:
        return float("nan")
    kept = [g for g in gaps if 0.6 * m <= g <= 1.6 * m]
    return mean(kept) if kept else m


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
    # Aggregates are robust periods (see _robust_period), never plain medians.
    stride_time: Dict[str, float] = field(default_factory=dict)
    step_time: Dict[str, float] = field(default_factory=dict)
    contact_time: Dict[str, float] = field(default_factory=dict)
    flight_time: Dict[str, float] = field(default_factory=dict)
    duty_factor: Dict[str, float] = field(default_factory=dict)
    # Per-stride series behind those aggregates, for variability and evidence counts.
    stride_times: Dict[str, List[float]] = field(default_factory=lambda: {"l": [], "r": []})
    step_times: Dict[str, List[float]] = field(default_factory=lambda: {"l": [], "r": []})
    contact_times: Dict[str, List[float]] = field(default_factory=lambda: {"l": [], "r": []})
    flight_times: Dict[str, List[float]] = field(default_factory=lambda: {"l": [], "r": []})
    sample_count: Dict[str, int] = field(default_factory=dict)
    alternation_ratio: float = 0.0
    confidence: str = "low"
    warnings: List[str] = field(default_factory=list)

    def midstance(self, side: str) -> List[int]:
        return list(self.midstances[side])

    def event_frames(self) -> List[int]:
        return sorted({f for side in ("l", "r") for f in self.strikes[side] + self.toeoffs[side]})


def _preceding_opposite(strikes: Dict[str, List[int]], side: str, frame: int) -> Optional[int]:
    other = "r" if side == "l" else "l"
    prior = [f for f in strikes[other] if f < frame]
    return prior[-1] if prior else None


def _alternation_ratio(strikes: Dict[str, List[int]]) -> float:
    """Fraction of consecutive contacts that change side.

    Measured on the contacts actually detected, so it stays a diagnostic rather than a
    filter: a run of same-side detections (one foot occluded, or a swing-phase bump
    accepted as a contact) shows up here and downgrades confidence, instead of being
    silently repaired. Repairing it by dropping events would also destroy the evidence
    that the clip is unreliable.
    """
    merged = sorted((frame, side) for side in ("l", "r") for frame in strikes[side])
    transitions = len(merged) - 1
    if transitions <= 0:
        return 0.0
    return sum(1 for a, b in zip(merged, merged[1:]) if a[1] != b[1]) / transitions


def detect_events(seq: PoseSequence) -> GaitEvents:
    ev = GaitEvents()
    # Use the real presentation clock when available. Container FPS is only metadata on
    # variable-frame-rate recordings and becomes wrong as soon as extraction drops frames.
    fps = seq.effective_fps or 30.0
    n = seq.n
    if n < 4:
        ev.warnings.append("clip_too_short")
        return ev

    for side in ("l", "r"):
        ankle_y = geo.moving_average(seq.series_y(f"{side}_ankle"), 3)
        amp = geo.peak_to_peak(ankle_y)
        if amp != amp or amp <= 0:
            continue
        # One peak per stance — midstance, the middle of the foot-down plateau.
        midstances = _stance_peaks(seq, ankle_y, amp)

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
        ev.stride_times[side] = same_foot
        if same_foot:
            ev.stride_time[side] = _robust_period(same_foot)
        contacts = [seq.elapsed(s, to) for (s, to) in stance]
        ev.contact_times[side] = contacts
        if contacts:
            ev.contact_time[side] = _robust_period(contacts)
        if ev.stride_time.get(side) and ev.contact_time.get(side):
            ev.duty_factor[side] = ev.contact_time[side] / ev.stride_time[side] * 100.0

    # Step and flight need both feet, so they run once both sides are populated.
    for side in ("l", "r"):
        steps_side = []
        for strike in ev.strikes[side]:
            previous = _preceding_opposite(ev.strikes, side, strike)
            if previous is not None:
                steps_side.append(seq.elapsed(previous, strike))
        ev.step_times[side] = steps_side
        if steps_side:
            ev.step_time[side] = _robust_period(steps_side)

        other = "r" if side == "l" else "l"
        flights = []
        for toeoff in ev.toeoffs[side]:
            later = [s for s in ev.strikes[other] if s > toeoff]
            if later:
                flights.append(seq.elapsed(toeoff, later[0]))
        ev.flight_times[side] = flights
        if flights:
            ev.flight_time[side] = _robust_period(flights)

    # cadence from the merged (either-foot) step interval — robust to edge effects
    all_mid = sorted(ev.midstances["l"] + ev.midstances["r"])
    steps = [seq.elapsed(all_mid[i], all_mid[i + 1]) for i in range(len(all_mid) - 1)]
    step_s = _robust_period(steps)
    if step_s == step_s and step_s > 0:
        ev.cadence_spm = 60.0 / step_s

    ev.alternation_ratio = _alternation_ratio(ev.strikes)
    stances = len(ev.stance["l"]) + len(ev.stance["r"])
    ev.sample_count = {
        "strikes": len(ev.strikes["l"]) + len(ev.strikes["r"]),
        "strides_l": max(0, len(ev.midstances["l"]) - 1),
        "strides_r": max(0, len(ev.midstances["r"]) - 1),
        "complete_stances_l": len(ev.stance["l"]),
        "complete_stances_r": len(ev.stance["r"]),
    }

    if ev.alternation_ratio < 0.8:
        ev.warnings.append("inconsistent_left_right_alternation")
    if stances < 4:
        ev.warnings.append("too_few_complete_stances")
    if not (ev.cadence_spm == ev.cadence_spm and 100 <= ev.cadence_spm <= 260):
        ev.warnings.append("implausible_or_missing_cadence")
    # Running has no double-support phase, so a duty factor at or above 50% means both
    # feet are down at once — impossible, and the signature of stance being measured from
    # the wrong anchor. Bounding it here is what makes that class of regression visible in
    # the report rather than only in the real-clip integration test.
    duties = [d for d in ev.duty_factor.values() if d == d]
    if duties and not all(15.0 <= d <= 50.0 for d in duties):
        ev.warnings.append("implausible_duty_factor")

    if not ev.warnings and stances >= 8 and ev.alternation_ratio >= 0.9:
        ev.confidence = "high"
    elif stances >= 4 and ev.alternation_ratio >= 0.75 and ev.cadence_spm == ev.cadence_spm:
        ev.confidence = "moderate"
    else:
        ev.confidence = "low"
    return ev
