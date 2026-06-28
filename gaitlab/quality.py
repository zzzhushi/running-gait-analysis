"""Capture-quality checks — flag footage problems that would make the metrics untrustworthy.

Runs on the extracted landmarks, so it works the same for any pose source. Returns a list
of {level, message}; the UI shows warnings (and a single 'looks good' when all pass).
"""

from __future__ import annotations

from statistics import mean
from typing import List

from .metrics import _body_px_height
from .schema import PoseSequence


def _ground_slope(seq: PoseSequence, events):
    """Slope (px-y per px-x) of the line through foot-contact points — a tilt/pan proxy."""
    pts = []
    for side in ("l", "r"):
        for s in events.strikes[side]:
            pts.append(seq.xy(s, f"{side}_ankle"))
    if len(pts) < 4:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if (max(xs) - min(xs)) < (seq.width or 1) * 0.25:
        return None  # contacts cluster (treadmill) — too narrow a baseline to judge tilt
    xm, ym = mean(xs), mean(ys)
    den = sum((x - xm) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / den


def assess(seq: PoseSequence, events) -> List[dict]:
    checks: List[dict] = []

    def warn(m):
        checks.append({"level": "warn", "message": m})

    def info(m):
        checks.append({"level": "info", "message": m})

    n, fps, dur = seq.n, seq.fps or 30.0, seq.duration

    if dur < 2.0 or n < 40:
        warn(f"Short clip ({dur:.1f}s). Film ~4–6s of steady running for stable metrics.")

    total_strikes = len(events.strikes["l"]) + len(events.strikes["r"])
    if total_strikes < 6:
        warn(f"Only {total_strikes} foot-strikes detected — capture more steady strides for reliable numbers.")

    confs = [p[2] for fr in seq.frames for p in fr if p[2] > 0]
    if confs and mean(confs) < 0.45:
        warn("Low tracking confidence. Improve lighting, wear fitted clothing, and fill the frame.")

    bph = _body_px_height(seq)
    if bph and seq.height and bph / seq.height < 0.4:
        warn("You fill little of the frame. Move the camera closer / zoom so you're ~60–80% of frame height.")

    if fps < 120:
        info(f"At {fps:.0f} fps, ground-contact timing is approximate — use 120/240 fps slow-mo for it.")

    if seq.is_side():
        slope = _ground_slope(seq, events)
        if slope is not None and abs(slope) > 0.06:
            warn("The ground line looks tilted — keep the camera level (a tripod helps).")

    hipxs = [seq.xy(f, "mid_hip")[0] for f in range(n)]
    if hipxs and seq.width and (max(hipxs) - min(hipxs)) / seq.width > 0.6:
        info("You travel across the frame (overground/pan). A treadmill + fixed tripod gives steadier data.")

    if not any(c["level"] == "warn" for c in checks):
        checks.insert(0, {"level": "ok", "message": "Capture looks good."})
    return checks
