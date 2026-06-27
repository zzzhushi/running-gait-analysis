"""Pure-Python geometry + 1-D signal helpers (stdlib `math` only)."""

from __future__ import annotations

import math
from typing import List, Tuple

XY = Tuple[float, float]


def distance(a: XY, b: XY) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def midpoint(a: XY, b: XY) -> XY:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def angle_3pt(a: XY, b: XY, c: XY) -> float:
    """Interior angle at vertex b in degrees (0..180)."""
    bax, bay = a[0] - b[0], a[1] - b[1]
    bcx, bcy = c[0] - b[0], c[1] - b[1]
    n1 = math.hypot(bax, bay)
    n2 = math.hypot(bcx, bcy)
    if n1 == 0 or n2 == 0:
        return float("nan")
    cos = (bax * bcx + bay * bcy) / (n1 * n2)
    cos = max(-1.0, min(1.0, cos))
    return math.degrees(math.acos(cos))


def angle_to_vertical(a: XY, b: XY) -> float:
    """Unsigned angle (>=0 deg) of segment a->b away from the vertical axis."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return math.degrees(math.atan2(abs(dx), abs(dy)))


def signed_lean(a: XY, b: XY, facing: int = 1) -> float:
    """Signed lean of segment a->b from vertical, in degrees.

    Positive = leaning in the runner's facing/travel direction (forward lean).
    a is the lower point (e.g. hip), b the upper point (e.g. shoulder).
    """
    dx = (b[0] - a[0]) * facing
    dy = abs(b[1] - a[1])
    return math.degrees(math.atan2(dx, dy))


def angle_to_horizontal(a: XY, b: XY) -> float:
    """Signed angle of segment a->b from the horizontal, in degrees (-180..180)."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return math.degrees(math.atan2(dy, dx))


# --- 1-D signal helpers ---------------------------------------------------

def moving_average(values: List[float], window: int) -> List[float]:
    if window <= 1:
        return list(values)
    n = len(values)
    out = [float("nan")] * n
    half = window // 2
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        seg = [v for v in values[lo:hi] if not math.isnan(v)]
        out[i] = sum(seg) / len(seg) if seg else float("nan")
    return out


def smooth_xy(series: List[XY], window: int) -> List[XY]:
    xs = moving_average([p[0] for p in series], window)
    ys = moving_average([p[1] for p in series], window)
    return list(zip(xs, ys))


def derivative(values: List[float], fps: float) -> List[float]:
    """Central-difference first derivative (units per second)."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [0.0]
    out = [0.0] * n
    for i in range(n):
        if i == 0:
            out[i] = (values[1] - values[0]) * fps
        elif i == n - 1:
            out[i] = (values[i] - values[i - 1]) * fps
        else:
            out[i] = (values[i + 1] - values[i - 1]) * 0.5 * fps
    return out


def find_peaks(values: List[float], min_distance: int = 1,
               min_prominence: float = 0.0) -> List[int]:
    """Indices of local maxima, enforcing a minimum spacing and prominence.

    Greedy: keeps the tallest candidate peaks first, then drops any that fall
    within `min_distance` of an already-accepted (taller) peak.
    """
    n = len(values)
    if n < 3:
        return []
    candidates = []
    for i in range(1, n - 1):
        v = values[i]
        if math.isnan(v):
            continue
        left = values[i - 1]
        right = values[i + 1]
        if v >= left and v >= right and (v > left or v > right):
            candidates.append(i)
    if min_prominence > 0.0:
        floor = min(v for v in values if not math.isnan(v))
        candidates = [i for i in candidates if values[i] - floor >= min_prominence]
    candidates.sort(key=lambda i: values[i], reverse=True)
    chosen: List[int] = []
    for i in candidates:
        if all(abs(i - j) >= min_distance for j in chosen):
            chosen.append(i)
    chosen.sort()
    return chosen


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def mean(values: List[float]) -> float:
    vals = [v for v in values if not math.isnan(v)]
    return sum(vals) / len(vals) if vals else float("nan")


def peak_to_peak(values: List[float]) -> float:
    vals = [v for v in values if not math.isnan(v)]
    if not vals:
        return float("nan")
    return max(vals) - min(vals)
