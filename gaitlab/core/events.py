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
# ground, as a fraction of its peak-to-peak range. Symmetric, so stance stays centred on
# midstance.
#
# WRONG MODEL, not just a wrong value: most of that range is swing-phase lift, and the ankle
# keeps moving through stance as the foot rolls. No constant fits both real clips — contact
# time and duty factor are approximate until contact is defined by motion instead. Sweep and
# failed alternatives: tests/integration/test_female_overstride_clip.py.
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

    Trim to gaps near a reference, then average what survives: a median alone is quantized
    onto a coarse cadence grid, a mean alone is wrecked by one spurious event.

    Pass `expect` whenever the caller knows the interval independently of these gaps. The
    median is a poor stand-in for it — it breaks down at 50% contamination, which is what one
    spurious event per stride produces, and then the trim discards the correct gaps rather
    than the wrong ones. An independent reference also earns a tighter window.
    """
    if not gaps:
        return float("nan")
    anchor = expect if (expect == expect and expect > 0) else median(gaps)
    if anchor <= 0:
        return float("nan")
    lo, hi = ((0.8, 1.2) if (expect == expect and expect > 0) else (0.6, 1.6))
    kept = [g for g in gaps if lo * anchor <= g <= hi * anchor]
    if kept:
        return mean(kept)
    # Nothing observed supports the reference, so say we do not know rather than report a
    # period no gap is near. Without a reference the median IS an observation, so that path
    # keeps its fallback.
    return float("nan") if (expect == expect and expect > 0) else median(gaps)


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


def _stride_seconds(ankle_y: List[float], seq: PoseSequence, fps: float) -> float:
    """Stride period in SECONDS, measured from the ankle-y signal alone.

    Resampled onto a uniform TIME grid first: reading the lag in frame indices and dividing
    by one average fps assumes evenly spaced frames, which dropped-frame input is not.
    """
    ts = seq.timestamps
    if ts is not None and len(ts) == len(ankle_y) and len(ankle_y) > 3:
        span = ts[-1] - ts[0]
        if span > 0:
            count = len(ankle_y)
            dt = span / (count - 1)
            grid = geo.resample_uniform(ankle_y, ts, count)
            lag = geo.dominant_period(grid, max(1, int(MIN_STRIDE_S / dt)),
                                      int(MAX_STRIDE_S / dt))
            return lag * dt if lag == lag else float("nan")
    lag = geo.dominant_period(ankle_y, max(1, int(MIN_STRIDE_S * fps)),
                              int(MAX_STRIDE_S * fps))
    return lag / fps if lag == lag else float("nan")


def detect_events(seq: PoseSequence) -> GaitEvents:
    ev = GaitEvents()
    # Use the real presentation clock when available. Container FPS is only metadata on
    # variable-frame-rate recordings and becomes wrong as soon as extraction drops frames.
    fps = seq.effective_fps or 30.0
    n = seq.n
    if n < 4:
        return ev

    # Same-foot peaks are a STRIDE apart, with a swing-phase bump between each real pair at
    # ~0.4 of the stride. The floor must scale to the stride: an absolute one rejects that
    # bump at some cadences and not others. Fallback is only for a clip too short or flat to
    # measure a period from.
    fallback_min_dist = max(3, int(fps * 0.35))
    stride_s: Dict[str, float] = {}

    for side in ("l", "r"):
        ankle_y = geo.moving_average(seq.series_y(f"{side}_ankle"), 3)
        amp = geo.peak_to_peak(ankle_y)
        if amp != amp or amp <= 0:
            continue
        # Stride period straight from the ankle-y signal, independent of the peaks below —
        # a period derived from those peaks could not be used to judge whether they are real.
        period = _stride_seconds(ankle_y, seq, fps)
        if period == period:
            stride_s[side] = period
            min_dist = max(3, int(period * fps * PEAK_SPACING_FRACTION))
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

    # Cadence from the merged (either-foot) step interval: twice the samples, and L/R phase
    # jitter averages out. Merging is also why the trim is anchored on half the measured
    # stride — one spurious peak on either foot injects a near-zero gap into this list.
    all_mid = sorted(ev.midstances["l"] + ev.midstances["r"])
    steps = [seq.elapsed(all_mid[i], all_mid[i + 1]) for i in range(len(all_mid) - 1)]
    measured = [v for v in stride_s.values() if v == v and v > 0]
    expect_step = (sum(measured) / len(measured) / 2.0) if measured else float("nan")
    step_s = _robust_period(steps, expect_step)
    if step_s == step_s and step_s > 0:
        ev.cadence_spm = 60.0 / step_s
    return ev
