"""Compute context: everything a metric's `compute(ctx, side)` formula needs,
plus memoized shared series so metrics that read the same underlying signal
(e.g. knee flexion at contact vs. at midstance) don't recompute it twice.

This is the only per-metric-formula plumbing that is genuinely shared — the
formulas themselves live in each metric's own module under definitions/.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Dict, List, Optional

from ..core import geometry as geo
from ..core.events import GaitEvents
from ..core.schema import PoseSequence


def med(xs: List[float]) -> float:
    xs = [x for x in xs if isinstance(x, (int, float)) and x == x]
    return median(xs) if xs else float("nan")


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
    return med(peaks) if peaks else geo.peak_to_peak(series)


def per_stride_range(series: List[float], strikes: List[int]) -> float:
    """Median peak-to-peak range across complete strides."""
    values = []
    for start, end in zip(strikes, strikes[1:]):
        segment = [v for v in series[start:end] if v == v]
        if segment:
            values.append(max(segment) - min(segment))
    return med(values) if values else float("nan")


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


def _leg_length(seq: PoseSequence) -> float:
    lens: List[float] = []
    for f in range(seq.n):
        for side in ("l", "r"):
            hip = seq.xy(f, f"{side}_hip")
            knee = seq.xy(f, f"{side}_knee")
            ankle = seq.xy(f, f"{side}_ankle")
            d = geo.distance(hip, knee) + geo.distance(knee, ankle)
            if d > 0:
                lens.append(d)
    result = med(lens)
    return result if math.isfinite(result) and result > 0 else 1.0


def _body_px_height(seq: PoseSequence) -> float:
    """Median head-to-foot pixel height across frames (for cm calibration)."""
    hs: List[float] = []
    threshold = max(0.35, seq.analysis_min_confidence)
    for f in range(seq.n):
        tops = [seq.pt(f, name)[1] for name in ("nose", "neck")
                if seq.pt(f, name)[2] >= threshold]
        bots = [seq.pt(f, name)[1] for name in
                ("l_heel", "r_heel", "l_ankle", "r_ankle", "l_big_toe", "r_big_toe")
                if seq.pt(f, name)[2] >= threshold]
        if tops and bots:
            hs.append(max(bots) - min(tops))
    return med(hs)


def _positive_number(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _calibration(seq: PoseSequence, calibration: Optional[Dict], leg_px: float) -> Dict:
    out = {"px_per_cm": None, "speed_mps": None}
    if not calibration:
        return out
    leg_cm = _positive_number(calibration.get("leg_length_cm"))
    h = _positive_number(calibration.get("height_cm"))
    if leg_cm and leg_px > 0:           # real leg length is the most reliable scale
        out["px_per_cm"] = leg_px / leg_cm
    elif h:
        bph = _body_px_height(seq)
        if bph and bph > 0:
            out["px_per_cm"] = bph / h
    spd = _positive_number(calibration.get("speed_kmh"))
    if spd:
        out["speed_mps"] = spd / 3.6
    return out


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
        self.leg = _leg_length(seq)
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

    def hip_flexion_series(self, side: str) -> List[float]:
        """Sagittal thigh angle relative to the trunk; flexion is positive."""
        return self._memo(f"hip_flex_{side}", lambda: [
            thigh - trunk
            for thigh, trunk in zip(self.thigh_lean_series(side), self.trunk_lean_series())
        ])

    def heel_y_series(self, side: str) -> List[float]:
        # Relative-to-pelvis motion removes whole-body vertical oscillation.
        return self._memo(f"heel_y_{side}", lambda: geo.moving_average([
            self.seq.xy(f, f"{side}_heel")[1] - self.seq.xy(f, "mid_hip")[1]
            for f in range(self.n)
        ], 3))

    def vertical_oscillation_px(self) -> float:
        """Median per-stride peak-to-peak of hip_y (px), strides bounded by left strikes."""
        def calc():
            hip_y = self.hip_y_series()
            strides = self.ev.strikes["l"]
            vals = []
            for start, end in zip(strides, strides[1:]):
                segment = [value for value in hip_y[start:end] if math.isfinite(value)]
                if segment:
                    vals.append(max(segment) - min(segment))
            return med(vals) if vals else geo.peak_to_peak(hip_y)
        return self._memo("vo_px", calc)

    def head_y_series(self) -> Optional[List[float]]:
        if not self.seq.has("head") or not any(
            math.isfinite(self.seq.xy(f, "head")[1]) for f in range(self.n)
        ):
            return None
        return self._memo("head_y", lambda: geo.moving_average(self.seq.series_y("head"), 3))

    # --- rear-view shared series -------------------------------------------

    @staticmethod
    def _anatomical_frontal_angle(left, right) -> float:
        """Angle of an anatomical left-to-right segment, invariant to image mirroring.

        The vertical sign is retained (positive means the right landmark is lower
        in image coordinates), while the horizontal component is made positive so
        a mirrored recording cannot introduce a roughly 180-degree discontinuity.
        """
        return math.degrees(math.atan2(right[1] - left[1], abs(right[0] - left[0])))

    def pelvic_tilt_series(self) -> List[float]:
        return self._memo("pelvic_tilt", lambda: geo.moving_average(
            [self._anatomical_frontal_angle(
                self.seq.xy(f, "l_hip"), self.seq.xy(f, "r_hip")
            ) for f in range(self.n)], 5))

    def neck_x_series(self) -> List[float]:
        # Trunk position relative to the pelvis, not whole-clip camera translation.
        return self._memo("neck_x", lambda: geo.moving_average([
            self.seq.xy(f, "neck")[0] - self.seq.xy(f, "mid_hip")[0]
            for f in range(self.n)
        ], 5))

    def shoulder_angle_series(self) -> List[float]:
        return self._memo("shoulder_angle", lambda: geo.moving_average(
            [self._anatomical_frontal_angle(
                self.seq.xy(f, "l_shoulder"), self.seq.xy(f, "r_shoulder")
            )
             for f in range(self.n)], 5))

    def step_width_and_crossover(self):
        """Base of gait from successive foot placements in fixed-camera coordinates.

        Unlike simultaneous ankle separation, this compares the striking foot at
        its own contact with the next contralateral contact, which is the 2-D rear
        view analogue of successive foot-placement width. A fixed camera is required.
        """
        CROSS_MARGIN = 3.0
        MIN_CROSS_PAIRS = 2
        def calc():
            hip_order = med([
                self.seq.xy(f, "r_hip")[0] - self.seq.xy(f, "l_hip")[0]
                for f in range(self.n)
            ])
            image_orientation = -1.0 if hip_order == hip_order and hip_order < 0 else 1.0
            placements = []
            for side in ("l", "r"):
                for strike in self.ev.strikes[side]:
                    foot_x = self.seq.xy(strike, f"{side}_ankle")[0]
                    if foot_x == foot_x:
                        placements.append((strike, side, foot_x))
            placements.sort()
            widths: List[float] = []
            cross_pairs = 0
            for a, b in zip(placements, placements[1:]):
                if a[1] == b[1]:
                    continue
                left = a[2] if a[1] == "l" else b[2]
                right = a[2] if a[1] == "r" else b[2]
                # Convert image-left/right to anatomical left/right. This keeps
                # both width and crossover classification invariant to mirroring.
                signed_width = (right - left) * image_orientation / self.leg * 100.0
                widths.append(abs(signed_width))
                if signed_width < -CROSS_MARGIN:
                    cross_pairs += 1
            crossover = cross_pairs >= MIN_CROSS_PAIRS
            return (med(widths) if widths else float("nan")), crossover
        return self._memo("step_width_crossover", calc)

    def head_x_series(self) -> Optional[List[float]]:
        if not self.seq.has("head") or not any(
            math.isfinite(self.seq.xy(f, "head")[0]) for f in range(self.n)
        ):
            return None
        return self._memo("head_x", lambda: geo.moving_average([
            self.seq.xy(f, "head")[0] - self.seq.xy(f, "mid_hip")[0]
            for f in range(self.n)
        ], 5))

    def stride_observations(self) -> List[Dict[str, float]]:
        """Event-synchronised rows used only for descriptive pattern detection."""
        rows: List[Dict[str, float]] = []
        for side in ("l", "r"):
            hip_flex = self.hip_flexion_series(side)
            knee = self.knee_flexion_series(side)
            trunk = self.trunk_lean_series()
            for strike, toeoff in self.ev.stance[side]:
                mid = int((strike + toeoff) / 2)
                next_strikes = [s for s in self.ev.strikes[side] if s > strike]
                stride_end = next_strikes[0] if next_strikes else None
                ankle = self.seq.xy(strike, f"{side}_ankle")
                hip = self.seq.xy(strike, f"{side}_hip")
                heel = self.seq.xy(strike, f"{side}_heel")
                toe = self.seq.xy(strike, f"{side}_big_toe")
                foot_angle = math.degrees(math.atan2(-(toe[1] - heel[1]), abs(toe[0] - heel[0]) + 1e-6))
                row = {
                    "side": side,
                    "strike": strike,
                    "toeoff": toeoff,
                    "midstance": mid,
                    "cadence": self.ev.cadence_spm,
                    "overstride": ((ankle[0] - hip[0]) * self.facing) / self.leg * 100.0,
                    "knee_flexion_midstance": knee[mid],
                    "trunk_lean": trunk[mid],
                    "foot_strike_angle": foot_angle,
                }
                stance_knee = [v for v in knee[strike:toeoff + 1] if math.isfinite(v)]
                if stance_knee:
                    row["knee_flexion_excursion"] = max(stance_knee) - min(stance_knee)
                if stride_end:
                    stride_hip = [v for v in hip_flex[strike:stride_end] if math.isfinite(v)]
                    stride_knee = [v for v in knee[strike:stride_end] if math.isfinite(v)]
                    if stride_hip:
                        row["hip_extension"] = max(-v for v in stride_hip)
                        row["hip_flexion_peak"] = max(stride_hip)
                    if stride_knee:
                        row["knee_flexion_peak"] = max(stride_knee)
                    hip_y = [v for v in self.hip_y_series()[strike:stride_end] if math.isfinite(v)]
                    if hip_y:
                        row["vertical_oscillation"] = geo.peak_to_peak(hip_y) / self.leg * 100.0
                rows.append(row)
        return rows
