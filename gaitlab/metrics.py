"""Per-stride and aggregate biomechanical metrics, computed from landmarks + events.

Side-view metrics (sagittal): cadence, trunk lean, knee flexion (contact & midstance),
foot-strike angle, overstride, vertical oscillation, ground-contact time.
Rear-view metrics (frontal): cadence, pelvic drop, step width / crossover, trunk sway.

Distances are normalized by leg length (median hip->knee->ankle) so they read as
"% of leg" and don't need real-world calibration. Angles need no calibration at all.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Dict, List, Optional

from . import geometry as geo
from .events import GaitEvents, detect_events
from .schema import PoseSequence


def _median(xs: List[float]) -> float:
    xs = [x for x in xs if x == x]
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


def _knee_flexion(seq: PoseSequence, f: int, side: str) -> float:
    ang = geo.angle_3pt(seq.xy(f, f"{side}_hip"),
                        seq.xy(f, f"{side}_knee"),
                        seq.xy(f, f"{side}_ankle"))
    return 180.0 - ang if ang == ang else float("nan")


def compute(seq: PoseSequence, events: Optional[GaitEvents] = None) -> Dict:
    ev = events or detect_events(seq)
    leg = _leg_length(seq)
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
    }
    if seq.is_side():
        _compute_side(seq, ev, leg, res)
    else:
        _compute_rear(seq, ev, leg, res)
    res["values"]["cadence"] = ev.cadence_spm
    return res


def _compute_side(seq, ev: GaitEvents, leg: float, res: Dict) -> None:
    n = seq.n
    facing = seq.facing_sign()

    # --- per-frame series (for the live readout / overlay) ---
    trunk = [geo.signed_lean(seq.xy(f, "mid_hip"), seq.xy(f, "neck"), facing) for f in range(n)]
    trunk = geo.moving_average(trunk, 5)
    kflex_l = geo.moving_average([_knee_flexion(seq, f, "l") for f in range(n)], 3)
    kflex_r = geo.moving_average([_knee_flexion(seq, f, "r") for f in range(n)], 3)
    hip_y = geo.moving_average(seq.series_y("mid_hip"), 3)
    res["series"] = {
        "trunk_lean": trunk,
        "knee_flexion_l": kflex_l,
        "knee_flexion_r": kflex_r,
        "hip_y": hip_y,
    }

    res["values"]["trunk_lean"] = _median(trunk)

    per_side: Dict[str, Dict[str, float]] = {"l": {}, "r": {}}
    for side, kflex in (("l", kflex_l), ("r", kflex_r)):
        strikes = ev.strikes[side]
        mids = ev.midstance(side)
        per_side[side]["knee_flexion_contact"] = _median([kflex[s] for s in strikes])
        per_side[side]["knee_flexion_midstance"] = _median([kflex[m] for m in mids])

        # foot-strike angle: toe-up (heel strike) positive
        fs = []
        for s in strikes:
            heel = seq.xy(s, f"{side}_heel")
            toe = seq.xy(s, f"{side}_big_toe")
            dx = (toe[0] - heel[0]) * facing
            dy = toe[1] - heel[1]
            fs.append(math.degrees(math.atan2(-dy, abs(dx) + 1e-6)))
        per_side[side]["foot_strike_angle"] = _median(fs)

        # overstride: how far the ankle lands ahead of the hip, % of leg length
        over = []
        for s in strikes:
            ankle = seq.xy(s, f"{side}_ankle")
            hip = seq.xy(s, f"{side}_hip")
            over.append(((ankle[0] - hip[0]) * facing) / leg * 100.0)
        per_side[side]["overstride"] = _median(over)

        per_side[side]["contact_time_ms"] = ev.contact_time.get(side, float("nan")) * 1000.0 \
            if side in ev.contact_time else float("nan")

    res["per_side"] = per_side

    # vertical oscillation: median per-stride peak-to-peak of hip_y, % of leg
    strides = ev.strikes["l"]
    vo_vals = []
    for i in range(len(strides) - 1):
        seg = hip_y[strides[i]:strides[i + 1]]
        if seg:
            vo_vals.append(max(seg) - min(seg))
    vo = _median(vo_vals) if vo_vals else geo.peak_to_peak(hip_y)
    res["values"]["vertical_oscillation"] = vo / leg * 100.0

    # aggregate (worse of the two sides drives the headline number)
    res["values"]["knee_flexion_midstance"] = _worst_low(
        per_side["l"]["knee_flexion_midstance"], per_side["r"]["knee_flexion_midstance"])
    res["values"]["overstride"] = _worst_high(
        per_side["l"]["overstride"], per_side["r"]["overstride"])
    res["values"]["contact_time"] = _worst_high(
        per_side["l"]["contact_time_ms"], per_side["r"]["contact_time_ms"])
    res["values"]["foot_strike_angle"] = _median(
        [per_side["l"]["foot_strike_angle"], per_side["r"]["foot_strike_angle"]])

    foi = res["frames_of_interest"]
    if ev.strikes["l"]:
        foi["l_strike"] = ev.strikes["l"][0]
    if ev.strikes["r"]:
        foi["r_strike"] = ev.strikes["r"][0]
    if ev.midstance("l"):
        foi["l_midstance"] = ev.midstance("l")[0]


def _compute_rear(seq, ev: GaitEvents, leg: float, res: Dict) -> None:
    n = seq.n
    # hip-line tilt per frame (deg from horizontal, signed)
    tilt = [geo.angle_to_horizontal(seq.xy(f, "l_hip"), seq.xy(f, "r_hip")) for f in range(n)]
    tilt = geo.moving_average(tilt, 5)
    neck_x = geo.moving_average(seq.series_x("neck"), 5)
    res["series"] = {"pelvic_tilt": tilt, "neck_x": neck_x}

    per_side: Dict[str, Dict[str, float]] = {"l": {}, "r": {}}
    # during one foot's stance, the opposite hip drops; report peak |tilt| per stance side
    for side in ("l", "r"):
        mids = ev.midstance(side)
        drops = [abs(tilt[m]) for m in mids] if mids else [abs(t) for t in tilt]
        per_side[side]["pelvic_drop"] = _median(drops)
    res["per_side"] = per_side
    res["values"]["pelvic_drop"] = _worst_high(
        per_side["l"]["pelvic_drop"], per_side["r"]["pelvic_drop"])

    # step width / crossover: lateral foot separation at contacts, % of leg
    seps = []
    crossover = False
    for side in ("l", "r"):
        for s in ev.strikes[side]:
            la = seq.xy(s, "l_ankle")
            ra = seq.xy(s, "r_ankle")
            mid = seq.xy(s, "mid_hip")[0]
            seps.append(abs(la[0] - ra[0]) / leg * 100.0)
            if (la[0] - mid) * (ra[0] - mid) > 0:  # both feet same side of midline
                crossover = True
    res["values"]["step_width"] = _median(seps) if seps else float("nan")
    res["values"]["crossover"] = crossover

    # lateral trunk sway: side-to-side neck travel, % of leg
    res["values"]["lateral_trunk_sway"] = geo.peak_to_peak(neck_x) / leg * 100.0

    foi = res["frames_of_interest"]
    if any(t == t for t in tilt):
        worst = max(range(n), key=lambda i: abs(tilt[i]) if tilt[i] == tilt[i] else -1)
        foi["max_pelvic_drop"] = worst


def _worst_high(a: float, b: float) -> float:
    """The larger (worse) of two 'lower is better' values, ignoring NaN."""
    vals = [v for v in (a, b) if v == v]
    return max(vals) if vals else float("nan")


def _worst_low(a: float, b: float) -> float:
    """The smaller (worse) of two 'higher is better' values, ignoring NaN."""
    vals = [v for v in (a, b) if v == v]
    return min(vals) if vals else float("nan")
