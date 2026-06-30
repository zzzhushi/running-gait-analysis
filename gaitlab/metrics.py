"""Per-stride and aggregate biomechanical metrics, computed from landmarks + events.

Side-view metrics (sagittal): cadence, trunk lean, knee flexion (contact & midstance),
foot-strike angle, overstride, vertical oscillation, ground-contact time, hip extension.
Rear-view metrics (frontal): cadence, pelvic drop, step width / crossover, trunk sway,
pronation estimate.

Distances are normalized by leg length (median hip->knee->ankle) so they read as
"% of leg" and need no calibration. Angles need none either. If the caller supplies
calibration (standing height in cm and/or treadmill speed in km/h), absolute values are
added too: vertical oscillation in cm, vertical ratio, and stride length.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Dict, List, Optional

from . import geometry as geo
from .events import GaitEvents, detect_events
from .schema import PoseSequence


def _median(xs: List[float]) -> float:
    xs = [x for x in xs if isinstance(x, (int, float)) and x == x]
    return median(xs) if xs else float("nan")


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
    return _median(lens) or 1.0


def _body_px_height(seq: PoseSequence) -> float:
    """Median head-to-foot pixel height across frames (for cm calibration)."""
    hs: List[float] = []
    for f in range(seq.n):
        tops = [seq.pt(f, n)[1] for n in ("nose", "neck") if seq.pt(f, n)[2] > 0.2]
        bots = [seq.pt(f, n)[1] for n in ("l_heel", "r_heel", "l_ankle", "r_ankle", "l_big_toe", "r_big_toe")
                if seq.pt(f, n)[2] > 0.2]
        if tops and bots:
            hs.append(max(bots) - min(tops))
    return _median(hs)


def _calibration(seq: PoseSequence, calibration: Optional[Dict], leg_px: float) -> Dict:
    out = {"px_per_cm": None, "speed_mps": None}
    if not calibration:
        return out
    leg_cm = calibration.get("leg_length_cm")
    h = calibration.get("height_cm")
    if leg_cm and leg_px > 0:           # real leg length is the most reliable scale
        out["px_per_cm"] = leg_px / float(leg_cm)
    elif h:
        bph = _body_px_height(seq)
        if bph and bph > 0:
            out["px_per_cm"] = bph / float(h)
    spd = calibration.get("speed_kmh")
    if spd:
        out["speed_mps"] = float(spd) / 3.6
    return out


def _knee_flexion(seq: PoseSequence, f: int, side: str) -> float:
    ang = geo.angle_3pt(seq.xy(f, f"{side}_hip"),
                        seq.xy(f, f"{side}_knee"),
                        seq.xy(f, f"{side}_ankle"))
    return 180.0 - ang if ang == ang else float("nan")


def _peak_hip_extension(seq: PoseSequence, ev: GaitEvents, side: str, facing: int) -> float:
    """Peak angle the thigh swings *behind* vertical over a stride (deg, +ve = extended)."""
    behind = [-geo.signed_lean(seq.xy(f, f"{side}_hip"), seq.xy(f, f"{side}_knee"), facing)
              for f in range(seq.n)]
    behind = geo.moving_average(behind, 5)
    strikes = ev.strikes[side]
    peaks: List[float] = []
    if len(strikes) >= 2:
        for i in range(len(strikes) - 1):
            seg = [v for v in behind[strikes[i]:strikes[i + 1]] if v == v]
            if seg:
                peaks.append(max(seg))
    else:
        seg = [v for v in behind if v == v]
        if seg:
            peaks.append(max(seg))
    return _median(peaks)


def _pronation(seq: PoseSequence, ev: GaitEvents, side: str) -> float:
    """Rear-view rear-foot roll-in estimate at contact (deg, +ve = pronation). Low confidence."""
    frames = ev.strikes[side] or ev.midstance(side) or list(range(0, seq.n, max(1, seq.n // 8)))
    vals: List[float] = []
    for s in frames:
        ankle = seq.xy(s, f"{side}_ankle")
        heel = seq.xy(s, f"{side}_heel")
        mid = seq.xy(s, "mid_hip")[0]
        dx = ankle[0] - heel[0]
        dy = abs(ankle[1] - heel[1]) + 1e-6
        toward_mid = 1.0 if ankle[0] < mid else -1.0
        vals.append(math.degrees(math.atan2(dx * toward_mid, dy)))
    return _median(vals)


def _step_times(ev: GaitEvents, side: str, fps: float) -> List[float]:
    """Step times for one side: from the preceding opposite-foot strike to each strike."""
    other = "r" if side == "l" else "l"
    s_side, s_other = ev.strikes[side], ev.strikes[other]
    out = []
    for s in s_side:
        prev = [o for o in s_other if o < s]
        if prev:
            out.append((s - prev[-1]) / fps)
    return out


def compute(seq: PoseSequence, events: Optional[GaitEvents] = None,
            calibration: Optional[Dict] = None) -> Dict:
    ev = events or detect_events(seq)
    leg = _leg_length(seq)
    cal = _calibration(seq, calibration, leg)
    res: Dict = {
        "view": seq.view,
        "fps": seq.fps,
        "duration": seq.duration,
        "leg_length": leg,
        "cadence": ev.cadence_spm,
        "events": ev,
        "series": {},
        "frames_of_interest": {},
        "per_side": {},
        "values": {},
        "calibration": cal,
    }
    if seq.is_side():
        _compute_side(seq, ev, leg, cal, res)
    else:
        _compute_rear(seq, ev, leg, cal, res)
    res["values"]["cadence"] = ev.cadence_spm
    return res


def _compute_side(seq, ev: GaitEvents, leg: float, cal: Dict, res: Dict) -> None:
    n = seq.n
    facing = seq.facing_sign()

    trunk = geo.moving_average(
        [geo.signed_lean(seq.xy(f, "mid_hip"), seq.xy(f, "neck"), facing) for f in range(n)], 5)
    kflex_l = geo.moving_average([_knee_flexion(seq, f, "l") for f in range(n)], 3)
    kflex_r = geo.moving_average([_knee_flexion(seq, f, "r") for f in range(n)], 3)
    hip_y = geo.moving_average(seq.series_y("mid_hip"), 3)
    res["series"] = {"trunk_lean": trunk, "knee_flexion_l": kflex_l, "knee_flexion_r": kflex_r, "hip_y": hip_y}
    res["values"]["trunk_lean"] = _median(trunk)

    per_side: Dict[str, Dict[str, float]] = {"l": {}, "r": {}}
    for side, kflex in (("l", kflex_l), ("r", kflex_r)):
        strikes = ev.strikes[side]
        mids = ev.midstance(side)
        per_side[side]["knee_flexion_contact"] = _median([kflex[s] for s in strikes])
        per_side[side]["knee_flexion_midstance"] = _median([kflex[m] for m in mids])

        fs = []
        for s in strikes:
            heel = seq.xy(s, f"{side}_heel")
            toe = seq.xy(s, f"{side}_big_toe")
            dx = (toe[0] - heel[0]) * facing
            dy = toe[1] - heel[1]
            fs.append(math.degrees(math.atan2(-dy, abs(dx) + 1e-6)))
        per_side[side]["foot_strike_angle"] = _median(fs)

        over = []
        for s in strikes:
            ankle = seq.xy(s, f"{side}_ankle")
            hip = seq.xy(s, f"{side}_hip")
            over.append(((ankle[0] - hip[0]) * facing) / leg * 100.0)
        per_side[side]["overstride"] = _median(over)

        per_side[side]["contact_time_ms"] = ev.contact_time.get(side, float("nan")) * 1000.0 \
            if side in ev.contact_time else float("nan")
        per_side[side]["hip_extension"] = _peak_hip_extension(seq, ev, side, facing)

        # P2: knee drive (peak forward thigh in swing), arm posture & swing, duty factor
        thigh_fwd = geo.moving_average(
            [geo.signed_lean(seq.xy(f, f"{side}_hip"), seq.xy(f, f"{side}_knee"), facing) for f in range(n)], 5)
        kd = []
        ss = ev.strikes[side]
        for i in range(len(ss) - 1):
            seg = [v for v in thigh_fwd[ss[i]:ss[i + 1]] if v == v]
            if seg:
                kd.append(max(seg))
        per_side[side]["knee_drive"] = _median(kd) if kd else geo.peak_to_peak(thigh_fwd)
        per_side[side]["elbow_angle"] = _median(
            [geo.angle_3pt(seq.xy(f, f"{side}_shoulder"), seq.xy(f, f"{side}_elbow"), seq.xy(f, f"{side}_wrist"))
             for f in range(n)])
        wrist_rel = [(seq.xy(f, f"{side}_wrist")[0] - seq.xy(f, f"{side}_shoulder")[0]) * facing for f in range(n)]
        per_side[side]["arm_swing"] = geo.peak_to_peak(wrist_rel) / leg * 100.0
        ct_s, stt = ev.contact_time.get(side), ev.stride_time.get(side)
        if ct_s and stt and stt > 0:
            per_side[side]["duty_factor"] = ct_s / stt * 100.0

        # P2 (remaining): heel recovery (vertical heel pickup in swing), per-side step length
        heel_y = geo.moving_average(seq.series_y(f"{side}_heel"), 3)
        hr = []
        for i in range(len(ss) - 1):
            seg = [v for v in heel_y[ss[i]:ss[i + 1]] if v == v]
            if len(seg) > 1:
                hr.append(max(seg) - min(seg))
        per_side[side]["heel_recovery"] = (_median(hr) / leg * 100.0) if hr else float("nan")
        if cal["speed_mps"]:
            steps = _step_times(ev, side, seq.fps)
            if steps:
                per_side[side]["step_length"] = cal["speed_mps"] * _median(steps)

        if cal["speed_mps"] and side in ev.stride_time:
            per_side[side]["stride_length"] = cal["speed_mps"] * ev.stride_time[side]

    res["per_side"] = per_side

    # vertical oscillation: median per-stride peak-to-peak of hip_y (px)
    strides = ev.strikes["l"]
    vo_vals = [max(hip_y[strides[i]:strides[i + 1]]) - min(hip_y[strides[i]:strides[i + 1]])
               for i in range(len(strides) - 1) if hip_y[strides[i]:strides[i + 1]]]
    vo_px = _median(vo_vals) if vo_vals else geo.peak_to_peak(hip_y)
    res["values"]["vertical_oscillation"] = vo_px / leg * 100.0

    res["values"]["knee_flexion_midstance"] = _worst_low(
        per_side["l"]["knee_flexion_midstance"], per_side["r"]["knee_flexion_midstance"])
    res["values"]["overstride"] = _worst_high(per_side["l"]["overstride"], per_side["r"]["overstride"])
    res["values"]["contact_time"] = _worst_high(per_side["l"]["contact_time_ms"], per_side["r"]["contact_time_ms"])
    res["values"]["foot_strike_angle"] = _median([per_side["l"]["foot_strike_angle"], per_side["r"]["foot_strike_angle"]])
    res["values"]["hip_extension"] = _worst_low(per_side["l"]["hip_extension"], per_side["r"]["hip_extension"])
    res["values"]["knee_drive"] = _worst_low(per_side["l"].get("knee_drive"), per_side["r"].get("knee_drive"))
    res["values"]["elbow_angle"] = _median([per_side["l"].get("elbow_angle"), per_side["r"].get("elbow_angle")])
    res["values"]["arm_swing"] = _median([per_side["l"].get("arm_swing"), per_side["r"].get("arm_swing")])
    df = [per_side[s].get("duty_factor") for s in ("l", "r")]
    df = [x for x in df if isinstance(x, (int, float))]
    if df:
        res["values"]["duty_factor"] = max(df)
    res["values"]["heel_recovery"] = _median([per_side["l"].get("heel_recovery"), per_side["r"].get("heel_recovery")])
    ct_vals = [per_side[s].get("contact_time_ms") for s in ("l", "r")]
    ct_vals = [c for c in ct_vals if isinstance(c, (int, float)) and c == c]
    if ev.cadence_spm == ev.cadence_spm and ev.cadence_spm > 0 and ct_vals:
        res["values"]["flight_time"] = max(0.0, 60000.0 / ev.cadence_spm - sum(ct_vals) / len(ct_vals))
    sl_steps = [x for x in (per_side["l"].get("step_length"), per_side["r"].get("step_length"))
                if isinstance(x, (int, float))]
    if sl_steps:
        res["values"]["step_length"] = _median(sl_steps)

    # calibration-derived absolutes
    if cal["px_per_cm"]:
        vo_cm = vo_px / cal["px_per_cm"]
        res["values"]["vertical_oscillation_cm"] = vo_cm
        if cal["speed_mps"] and ev.cadence_spm == ev.cadence_spm and ev.cadence_spm > 0:
            step_time = 60.0 / ev.cadence_spm
            step_len_m = cal["speed_mps"] * step_time
            if step_len_m > 0:
                res["values"]["vertical_ratio"] = (vo_cm / 100.0) / step_len_m * 100.0
    if cal["speed_mps"]:
        sl = [per_side[s].get("stride_length") for s in ("l", "r")]
        res["values"]["stride_length"] = _median([x for x in sl if x is not None])

    if seq.has("head"):
        head_y = geo.moving_average(seq.series_y("head"), 3)
        strides = ev.strikes["l"]
        hd_vals = [max(head_y[strides[i]:strides[i + 1]]) - min(head_y[strides[i]:strides[i + 1]])
                   for i in range(len(strides) - 1) if head_y[strides[i]:strides[i + 1]]]
        head_px = _median(hd_vals) if hd_vals else geo.peak_to_peak(head_y)
        res["values"]["head_drop"] = head_px / leg * 100.0

    foi = res["frames_of_interest"]
    if ev.strikes["l"]:
        foi["l_strike"] = ev.strikes["l"][0]
    if ev.strikes["r"]:
        foi["r_strike"] = ev.strikes["r"][0]
    if ev.midstance("l"):
        foi["l_midstance"] = ev.midstance("l")[0]
    if ev.toeoffs["l"]:
        foi["l_toeoff"] = ev.toeoffs["l"][0]


def _compute_rear(seq, ev: GaitEvents, leg: float, cal: Dict, res: Dict) -> None:
    n = seq.n
    tilt = geo.moving_average([geo.angle_to_horizontal(seq.xy(f, "l_hip"), seq.xy(f, "r_hip")) for f in range(n)], 5)
    neck_x = geo.moving_average(seq.series_x("neck"), 5)
    res["series"] = {"pelvic_tilt": tilt, "neck_x": neck_x}

    per_side: Dict[str, Dict[str, float]] = {"l": {}, "r": {}}
    for side in ("l", "r"):
        mids = ev.midstance(side)
        drops = [abs(tilt[m]) for m in mids] if mids else [abs(t) for t in tilt]
        per_side[side]["pelvic_drop"] = _median(drops)
        per_side[side]["pronation"] = _pronation(seq, ev, side)
        if cal["speed_mps"] and side in ev.stride_time:
            per_side[side]["stride_length"] = cal["speed_mps"] * ev.stride_time[side]
    res["per_side"] = per_side
    res["values"]["pelvic_drop"] = _worst_high(per_side["l"]["pelvic_drop"], per_side["r"]["pelvic_drop"])
    res["values"]["pronation"] = _worst_high(abs_or_nan(per_side["l"]["pronation"]), abs_or_nan(per_side["r"]["pronation"]))

    seps = []
    crossover = False
    for side in ("l", "r"):
        for s in ev.strikes[side]:
            la = seq.xy(s, "l_ankle")
            ra = seq.xy(s, "r_ankle")
            mid = seq.xy(s, "mid_hip")[0]
            seps.append(abs(la[0] - ra[0]) / leg * 100.0)
            if (la[0] - mid) * (ra[0] - mid) > 0:
                crossover = True
    res["values"]["step_width"] = _median(seps) if seps else float("nan")
    res["values"]["crossover"] = crossover
    res["values"]["lateral_trunk_sway"] = geo.peak_to_peak(neck_x) / leg * 100.0
    # arms swinging across the body midline (P2)
    cross = sum(1 for f in range(n)
                if (seq.xy(f, "l_wrist")[0] - seq.xy(f, "mid_hip")[0]) > 0
                or (seq.xy(f, "r_wrist")[0] - seq.xy(f, "mid_hip")[0]) < 0)
    res["values"]["arm_crossover"] = cross > n * 0.25
    # trunk-pelvis counter-rotation proxy (shoulder line vs hip line; low confidence in 2-D)
    sh_ang = geo.moving_average(
        [geo.angle_to_horizontal(seq.xy(f, "l_shoulder"), seq.xy(f, "r_shoulder")) for f in range(n)], 5)
    res["values"]["trunk_pelvis_rotation"] = geo.peak_to_peak([sh_ang[f] - tilt[f] for f in range(n)])
    if cal["speed_mps"]:
        for side in ("l", "r"):
            steps = _step_times(ev, side, seq.fps)
            if steps:
                per_side[side]["step_length"] = cal["speed_mps"] * _median(steps)
        st_sl = [x for x in (per_side["l"].get("step_length"), per_side["r"].get("step_length"))
                 if isinstance(x, (int, float))]
        if st_sl:
            res["values"]["step_length"] = _median(st_sl)
    if cal["speed_mps"]:
        sl = [per_side[s].get("stride_length") for s in ("l", "r")]
        res["values"]["stride_length"] = _median([x for x in sl if x is not None])

    if seq.has("head"):
        head_x = geo.moving_average(seq.series_x("head"), 5)
        res["values"]["head_lateral_sway"] = geo.peak_to_peak(head_x) / leg * 100.0

    foi = res["frames_of_interest"]
    if any(t == t for t in tilt):
        foi["max_pelvic_drop"] = max(range(n), key=lambda i: abs(tilt[i]) if tilt[i] == tilt[i] else -1)


def abs_or_nan(v: float) -> float:
    return abs(v) if v == v else float("nan")


def _worst_high(a: float, b: float) -> float:
    vals = [v for v in (a, b) if isinstance(v, (int, float)) and v == v]
    return max(vals) if vals else float("nan")


def _worst_low(a: float, b: float) -> float:
    vals = [v for v in (a, b) if isinstance(v, (int, float)) and v == v]
    return min(vals) if vals else float("nan")
