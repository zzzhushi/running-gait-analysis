"""Compute context: everything a metric's `compute(ctx, side)` formula needs,
plus memoized shared series so metrics that read the same underlying signal
(e.g. knee flexion at contact vs. at midstance) don't recompute it twice.

This is the only per-metric-formula plumbing that is genuinely shared — the
formulas themselves live in each metric's own module under definitions/.
"""

from __future__ import annotations

import math
from statistics import median as _median
from typing import Dict, List, Optional

from ..core import geometry as geo
from ..core import reach as reach_mod
from ..core.events import GaitEvents
from ..core.profile import Calibration, RunnerProfile
from ..core.reach import Denominator, DenominatorSample, ReachSample
from ..core.schema import PoseSequence


def median(xs: List[float]) -> float:
    """Median after dropping non-numeric/NaN values; NaN if none remain."""
    xs = [x for x in xs if isinstance(x, (int, float)) and x == x]
    return _median(xs) if xs else float("nan")


def per_stride_max(series: List[float], strikes: List[int]) -> float:
    """Median of the per-stride maxima of `series`, segmented by `strikes`."""
    peaks: List[float] = []
    if len(strikes) >= 2:
        for i in range(len(strikes) - 1):
            seg = [v for v in series[strikes[i]:strikes[i + 1]] if v == v]
            if seg:
                peaks.append(max(seg))
    else:
        seg = [v for v in series if v == v]
        if seg:
            peaks.append(max(seg))
    return median(peaks) if peaks else geo.peak_to_peak(series)


def step_times(ev: GaitEvents, side: str, seq: PoseSequence) -> List[float]:
    """Step times for one side: from the preceding opposite-foot strike to each strike."""
    other = "r" if side == "l" else "l"
    s_side, s_other = ev.strikes[side], ev.strikes[other]
    out = []
    for s in s_side:
        prev = [o for o in s_other if o < s]
        if prev:
            out.append(seq.elapsed(prev[-1], s))
    return out


def knee_flexion_at(seq: PoseSequence, f: int, side: str) -> float:
    ang = geo.angle_3pt(seq.xy(f, f"{side}_hip"), seq.xy(f, f"{side}_knee"), seq.xy(f, f"{side}_ankle"))
    return 180.0 - ang if ang == ang else float("nan")


def leg_length_samples(seq: PoseSequence) -> List[DenominatorSample]:
    """Every limb-length observation behind the denominator.

    Pooled over both sides and all frames, so each observation retains its frame and raw
    points and a normalized value can be traced past the scalar.
    """
    out: List[DenominatorSample] = []
    for f in range(seq.n):
        for side in ("l", "r"):
            hip = seq.pt(f, f"{side}_hip")
            knee = seq.pt(f, f"{side}_knee")
            ankle = seq.pt(f, f"{side}_ankle")
            # Confidence zero is the schema's not-tracked sentinel; its placeholder
            # coordinates are not geometry. No higher threshold is applied.
            if min(hip[2], knee[2], ankle[2]) <= 0:
                continue
            thigh = geo.distance(hip[:2], knee[:2])
            shank = geo.distance(knee[:2], ankle[:2])
            if thigh + shank > 0:
                out.append(DenominatorSample(
                    frame=f, t=seq.time_at(f), side=side,
                    hip=hip, knee=knee, ankle=ankle,
                    thigh_px=thigh, shank_px=shank,
                    total_px=thigh + shank,
                    min_confidence=min(hip[2], knee[2], ankle[2]),
                ))
    return out


def leg_denominator(seq: PoseSequence) -> Denominator:
    """The current overstride denominator, carrying the observations that produced it."""
    samples = leg_length_samples(seq)
    if not samples:
        return Denominator(
            px=float("nan"),
            method="median of thigh+shank, pooled over both sides and all frames",
            source_unavailable="no frames have tracked hip, knee, and ankle landmarks",
        )
    return Denominator(
        px=median([s.total_px for s in samples]),
        method="median of thigh+shank, pooled over both sides and all frames",
        samples=tuple(samples),
    )


def _leg_length(seq: PoseSequence) -> float:
    return leg_denominator(seq).px


def _body_px_height(seq: PoseSequence) -> float:
    """Median head-to-foot pixel height across frames (for cm calibration)."""
    hs: List[float] = []
    for f in range(seq.n):
        tops = [seq.pt(f, n)[1] for n in ("nose", "neck") if seq.pt(f, n)[2] > 0.2]
        bots = [seq.pt(f, n)[1] for n in ("l_heel", "r_heel", "l_ankle", "r_ankle", "l_big_toe", "r_big_toe")
                if seq.pt(f, n)[2] > 0.2]
        if tops and bots:
            hs.append(max(bots) - min(tops))
    return median(hs)


def _calibration(seq: PoseSequence, calibration, leg_px: float) -> Calibration:
    """Resolve a profile (or the legacy dict form) into the derived Calibration.

    The scale rules live on RunnerProfile; this only supplies the two pixel
    measurements they need, and computes the height-based one lazily so a
    leg-length profile never pays for the median-height scan.
    """
    profile = calibration if isinstance(calibration, RunnerProfile) else RunnerProfile.from_dict(calibration)
    if not profile:
        return Calibration()
    body_px = None if profile.leg_length_cm else _body_px_height(seq)
    return profile.calibrate(leg_px, body_px)


class Ctx:
    """Per-analysis compute context, shared by every metric's compute() call.

    Exposes the raw pose/events/leg-length/calibration plus a handful of
    *memoized* smoothed series that more than one metric formula reads, so the
    smoothing/windowing is applied exactly once regardless of how many metrics
    consume it.
    """

    def __init__(self, seq: PoseSequence, ev: GaitEvents, calibration: Optional[Dict] = None):
        self.seq = seq
        self.ev = ev
        self.n = seq.n
        self.facing = seq.facing_sign()
        self.denominator = leg_denominator(seq)
        self.leg = self.denominator.px
        self.cal = _calibration(seq, calibration, self.leg)
        self._cache: Dict[str, object] = {}

    def _memo(self, key: str, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    # --- side-view shared series -----------------------------------------

    def trunk_lean_series(self) -> List[float]:
        return self._memo("trunk_lean", lambda: geo.moving_average(
            [geo.signed_lean(self.seq.xy(f, "mid_hip"), self.seq.xy(f, "neck"), self.facing)
             for f in range(self.n)], 5))

    def knee_flexion_series(self, side: str) -> List[float]:
        return self._memo(f"kflex_{side}", lambda: geo.moving_average(
            [knee_flexion_at(self.seq, f, side) for f in range(self.n)], 3))

    def hip_y_series(self) -> List[float]:
        return self._memo("hip_y", lambda: geo.moving_average(self.seq.series_y("mid_hip"), 3))

    def thigh_lean_series(self, side: str) -> List[float]:
        """Raw signed_lean(hip, knee, facing): + = forward, - = behind vertical."""
        return self._memo(f"thigh_lean_{side}", lambda: geo.moving_average(
            [geo.signed_lean(self.seq.xy(f, f"{side}_hip"), self.seq.xy(f, f"{side}_knee"), self.facing)
             for f in range(self.n)], 5))

    def heel_y_series(self, side: str) -> List[float]:
        return self._memo(f"heel_y_{side}", lambda: geo.moving_average(
            self.seq.series_y(f"{side}_heel"), 3))

    def vertical_oscillation_px(self) -> float:
        """Median per-stride peak-to-peak of hip_y (px), strides bounded by left strikes."""
        def calc():
            hip_y = self.hip_y_series()
            strides = self.ev.strikes["l"]
            vals = [max(hip_y[strides[i]:strides[i + 1]]) - min(hip_y[strides[i]:strides[i + 1]])
                    for i in range(len(strides) - 1) if hip_y[strides[i]:strides[i + 1]]]
            return median(vals) if vals else geo.peak_to_peak(hip_y)
        return self._memo("vo_px", calc)

    def head_y_series(self) -> Optional[List[float]]:
        if not self.seq.has("head"):
            return None
        return self._memo("head_y", lambda: geo.moving_average(self.seq.series_y("head"), 3))

    # --- rear-view shared series -------------------------------------------

    def pelvic_tilt_series(self) -> List[float]:
        return self._memo("pelvic_tilt", lambda: geo.moving_average(
            [geo.angle_to_horizontal(self.seq.xy(f, "l_hip"), self.seq.xy(f, "r_hip")) for f in range(self.n)], 5))

    def neck_x_series(self) -> List[float]:
        return self._memo("neck_x", lambda: geo.moving_average(self.seq.series_x("neck"), 5))

    def shoulder_angle_series(self) -> List[float]:
        return self._memo("shoulder_angle", lambda: geo.moving_average(
            [geo.angle_to_horizontal(self.seq.xy(f, "l_shoulder"), self.seq.xy(f, "r_shoulder"))
             for f in range(self.n)], 5))

    def step_width_and_crossover(self):
        """(median step width %leg, whether the feet ever cross the midline) — one
        shared loop over both sides' strikes, since step_width and crossover are
        two readings off the same per-strike ankle separation."""
        # Require both margin and repetition so one noisy near-midline strike does not
        # count as crossover gait.
        CROSS_MARGIN = 3.0   # %leg the inner foot must clear the midline by
        MIN_CROSS_STRIKES = 2
        def calc():
            seps: List[float] = []
            cross_strikes = 0
            for side in ("l", "r"):
                for s in self.ev.strikes[side]:
                    la = self.seq.xy(s, "l_ankle")
                    ra = self.seq.xy(s, "r_ankle")
                    mid = self.seq.xy(s, "mid_hip")[0]
                    seps.append(abs(la[0] - ra[0]) / self.leg * 100.0)
                    if (la[0] - mid) * (ra[0] - mid) > 0:  # both ankles same side of midline
                        depth = min(abs(la[0] - mid), abs(ra[0] - mid)) / self.leg * 100.0
                        if depth > CROSS_MARGIN:
                            cross_strikes += 1
            crossover = cross_strikes >= MIN_CROSS_STRIKES
            return (median(seps) if seps else float("nan")), crossover
        return self._memo("step_width_crossover", calc)

    def head_x_series(self) -> Optional[List[float]]:
        if not self.seq.has("head"):
            return None
        return self._memo("head_x", lambda: geo.moving_average(self.seq.series_x("head"), 5))

    def reach_curve(self, side: str) -> List[ReachSample]:
        """Hip-relative foot position for `side`, one sample per frame.

        Normalized by the projected thigh+shank median, which the measurement contract
        records as an open choice rather than a validated one.
        """
        return self._memo(f"reach_curve_{side}",
                           lambda: reach_mod.reach_curve(self.seq, side, self.denominator, self.facing))
