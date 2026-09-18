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

Downstream metrics depend on these anchors, so midstance must not be reported as initial
contact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, median
from typing import Dict, List, Tuple

from . import geometry as geo
from .schema import PoseSequence

# Fraction of ankle vertical range used to estimate stance boundaries. Ankle motion during
# stance varies by runner, so contact time and duty factor remain approximate.
LIFT_FRACTION = 0.15

# Peak spacing floor, as a fraction of the measured stride. The swing-phase bump sits near
# 0.4 of a stride and a real peak at 1.0.
PEAK_SPACING_FRACTION = 0.6

# Ankle-y smoothing window, as a fraction of the measured stride. A fixed sample count is a
# different amount of time at every frame rate — 3 samples is 100ms at 30fps but 25ms at
# 120fps — while ground contact stays a roughly fixed fraction of the stride at any frame
# rate. Too little smoothing leaves the flat plateau at each stance riddled with tied or
# near-tied local maxima, and which one is tallest is then decided by pose-estimation noise
# rather than by gait.
SMOOTH_STRIDE_FRACTION = 0.10
# Stride periods the search will consider, in seconds: 240 spm down to 60 spm.
MIN_STRIDE_S = 0.5
MAX_STRIDE_S = 2.0


def _robust_period(gaps: List[float], expect: float = float("nan")) -> float:
    """Return the mean of gaps consistent with a reference period.

    When `expect` is absent, the sample median supplies the reference. An external reference
    permits tighter filtering and returns NaN when no observation supports it.
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
    # Do not turn an unsupported external reference into an observed period.
    return float("nan") if (expect == expect and expect > 0) else median(gaps)


@dataclass
class GaitEvents:
    strikes: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    toeoffs: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    stance: Dict[str, List[Tuple[int, int]]] = field(default_factory=lambda: {"l": [], "r": []})
    # Stable extrema used for cadence and stride timing; contact boundaries are noisier
    # threshold crossings.
    midstances: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    cadence_spm: float = float("nan")
    stride_time: Dict[str, float] = field(default_factory=dict)   # seconds, median
    contact_time: Dict[str, float] = field(default_factory=dict)  # seconds, median

    def midstance(self, side: str) -> List[int]:
        return list(self.midstances[side])


def _stride_seconds(ankle_y: List[float], seq: PoseSequence, fps: float) -> float:
    """Estimate stride seconds from the ankle-y signal alone.

    Timestamped input is resampled because autocorrelation lags assume uniform spacing.
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

    # Same-foot peaks are one stride apart; a secondary swing-phase peak occurs near 0.4 of
    # that interval. Scale the spacing floor with stride so it works across cadences.
    fallback_min_dist = max(3, int(fps * 0.35))
    stride_s: Dict[str, float] = {}

    for side in ("l", "r"):
        raw_y = seq.series_y(f"{side}_ankle")
        # A rough pass gives a stride estimate to size the real smoothing window against;
        # 3 samples is arbitrary but the peak-finding below never sees this pass.
        rough_y = geo.moving_average(raw_y, 3)
        rough_amp = geo.peak_to_peak(rough_y)
        if rough_amp != rough_amp or rough_amp <= 0:
            continue
        rough_period = _stride_seconds(rough_y, seq, fps)
        smooth_win = (max(3, int(round(rough_period * fps * SMOOTH_STRIDE_FRACTION)) | 1)
                     if rough_period == rough_period else 3)
        ankle_y = geo.moving_average(raw_y, smooth_win)
        amp = geo.peak_to_peak(ankle_y)
        # From the signal, not from the peaks below: a period derived from those peaks cannot
        # judge whether they are real.
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

        # Extrema provide more stable timing than contact-threshold crossings.
        same_foot = [seq.elapsed(midstances[i], midstances[i + 1])
                     for i in range(len(midstances) - 1)]
        if same_foot:
            ev.stride_time[side] = _robust_period(same_foot, stride_s.get(side, float("nan")))
        contacts = [seq.elapsed(s, to) for (s, to) in stance]
        if contacts:
            ev.contact_time[side] = _robust_period(contacts)

    # Merge both feet for cadence; anchor filtering on half-stride so a spurious peak from
    # either side cannot dominate the interval distribution.
    all_mid = sorted(ev.midstances["l"] + ev.midstances["r"])
    steps = [seq.elapsed(all_mid[i], all_mid[i + 1]) for i in range(len(all_mid) - 1)]
    measured = [v for v in stride_s.values() if v == v and v > 0]
    expect_step = (sum(measured) / len(measured) / 2.0) if measured else float("nan")
    step_s = _robust_period(steps, expect_step)
    if step_s == step_s and step_s > 0:
        ev.cadence_spm = 60.0 / step_s
    return ev
