"""Generic per-metric compute dispatch.

This module has no per-metric knowledge at all — it loops the metric registry
(populated by importing gaitlab/metrics/definitions) and calls each metric's
own `compute(ctx, side)`. To add or change a metric's formula, edit its module
under definitions/; nothing here needs to change.
"""

from __future__ import annotations

from typing import Dict, Optional

from . import definitions  # noqa: F401  (import side effect: registers every metric)
from . import spec as registry
from .ctx import Ctx, med
from ..core.events import GaitEvents, detect_events
from ..core.schema import PoseSequence


def _valid(v) -> bool:
    return v is not None and isinstance(v, (int, float)) and v == v


def _aggregate(mode: str, l, r):
    vals = [v for v in (l, r) if _valid(v)]
    if not vals:
        return None
    if mode == "worst_high":
        return max(vals)
    if mode == "worst_low":
        return min(vals)
    if mode == "worst_high_abs":
        return max(abs(v) for v in vals)
    if mode == "max":
        return max(vals)
    return med(vals)  # "median" (default)


def compute(seq: PoseSequence, events: Optional[GaitEvents] = None,
            calibration: Optional[Dict] = None) -> Dict:
    ev = events or detect_events(seq)
    ctx = Ctx(seq, ev, calibration)
    view_str = "side" if seq.is_side() else "rear"

    res: Dict = {
        "view": seq.view,
        "fps": seq.fps,
        "duration": seq.duration,
        "leg_length": ctx.leg,
        "cadence": ev.cadence_spm,
        "events": ev,
        "series": {},
        "frames_of_interest": {},
        "per_side": {"l": {}, "r": {}},
        "values": {},
        "calibration": ctx.cal,
    }
    per_side = res["per_side"]
    values = res["values"]

    for defn in registry.all_metrics().values():
        if defn.compute is None or view_str not in defn.views:
            continue
        key = defn.key.value

        if defn.per_side_compute:
            raw_l = defn.compute(ctx, "l")
            raw_r = defn.compute(ctx, "r")
            if raw_l is not None:
                per_side["l"][key] = raw_l
            if raw_r is not None:
                per_side["r"][key] = raw_r
            headline = _aggregate(defn.aggregate, raw_l, raw_r)
            if headline is not None:
                values[key] = headline
            elif defn.card_visibility != "conditional":
                values[key] = float("nan")
        else:
            raw = defn.compute(ctx, None)
            if raw is not None:
                values[key] = raw
            elif defn.card_visibility != "conditional":
                values[key] = float("nan")

    values["cadence"] = ev.cadence_spm

    # frames_of_interest: generic, event-derived anchors the overlay/report point to.
    foi = res["frames_of_interest"]
    if view_str == "side":
        if ev.strikes["l"]:
            foi["l_strike"] = ev.strikes["l"][0]
        if ev.strikes["r"]:
            foi["r_strike"] = ev.strikes["r"][0]
        if ev.midstance("l"):
            foi["l_midstance"] = ev.midstance("l")[0]
        if ev.toeoffs["l"]:
            foi["l_toeoff"] = ev.toeoffs["l"][0]
        res["series"] = {
            "trunk_lean": ctx.trunk_lean_series(),
            "knee_flexion_l": ctx.knee_flexion_series("l"),
            "knee_flexion_r": ctx.knee_flexion_series("r"),
            "hip_y": ctx.hip_y_series(),
        }
    else:
        tilt = ctx.pelvic_tilt_series()
        if any(t == t for t in tilt):
            foi["max_pelvic_drop"] = max(range(ctx.n), key=lambda i: abs(tilt[i]) if tilt[i] == tilt[i] else -1)
        res["series"] = {"pelvic_tilt": tilt, "neck_x": ctx.neck_x_series()}

    return res
