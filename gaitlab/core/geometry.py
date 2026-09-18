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
    # Normalize first: multiplying the two magnitudes can underflow to zero for
    # valid subnormal vectors (or overflow for very large coordinates).
    cos = (bax / n1) * (bcx / n2) + (bay / n1) * (bcy / n2)
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

    Here `min_prominence` means height above the signal's global minimum. It is
    not topographic prominence, which uses each peak's surrounding contour.
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
        non_nan = [v for v in values if not math.isnan(v)]
        if not non_nan:
            return []
        floor = min(non_nan)
        candidates = [i for i in candidates if values[i] - floor >= min_prominence]
    candidates.sort(key=lambda i: values[i], reverse=True)
    chosen: List[int] = []
    for i in candidates:
        if all(abs(i - j) >= min_distance for j in chosen):
            chosen.append(i)
    chosen.sort()
    return chosen


def resample_uniform(values: List[float], times: List[float], count: int) -> List[float]:
    """`values` sampled at `times` (ascending), linearly interpolated onto `count` points
    evenly spaced over the same span.

    Use before frequency analysis, which assumes uniform sample spacing.
    """
    n = len(values)
    if n < 2 or len(times) != n or count < 2:
        return list(values)
    span = times[-1] - times[0]
    if span <= 0:
        return list(values)
    step = span / (count - 1)
    out: List[float] = []
    j = 0
    for k in range(count):
        t = times[0] + k * step
        while j + 2 < n and times[j + 1] < t:
            j += 1
        t0, t1 = times[j], times[j + 1]
        v0, v1 = values[j], values[j + 1]
        if math.isnan(v0) or math.isnan(v1) or t1 <= t0:
            out.append(v0)
        else:
            f = (t - t0) / (t1 - t0)
            out.append(v0 + (v1 - v0) * f)
    return out


# Heuristic near-tie ratio for preferring a shorter autocorrelation lag over a harmonic.
# TODO: calibrate against the real-video corpus.
SUBHARMONIC_TOLERANCE = 0.85


def normalized_autocorrelation(values: List[float], max_lag: int) -> List[float]:
    """Normalized autocorrelation of `values` at lags 0..max_lag, inclusive.

    NaNs contribute zero deviation from the mean. Unbiased for the shrinking overlap at each
    lag, so a longer lag is not penalised just for having fewer terms to sum.
    """
    n = len(values)
    max_lag = min(max_lag, n - 1)
    if n < 2 or max_lag < 0:
        return []
    finite = [v for v in values if not math.isnan(v)]
    if not finite:
        return []
    m = sum(finite) / len(finite)
    dev = [0.0 if math.isnan(v) else v - m for v in values]
    total = sum(d * d for d in dev)
    if total <= 0.0:
        return []
    out: List[float] = []
    for lag in range(0, max_lag + 1):
        acc = 0.0
        for i in range(n - lag):
            acc += dev[i] * dev[i + lag]
        out.append(acc / (total * (n - lag) / n))
    return out


def local_maxima(values: List[float], lo: int, hi: int) -> List[Tuple[int, float]]:
    """Indices in [lo, hi] (clamped to the array) that are local maxima, as (index, value).

    Compares each index against its real neighbours in `values`, not against the edges of
    [lo, hi]: a search window that starts or ends inside the array still gets a correct
    comparison at its boundary, using whatever sits just outside the window rather than
    treating the boundary as if nothing were there.
    """
    n = len(values)
    lo = max(0, lo)
    hi = min(hi, n - 1)
    out: List[Tuple[int, float]] = []
    for i in range(lo, hi + 1):
        if i > 0 and values[i] < values[i - 1]:
            continue
        if i < n - 1 and values[i] < values[i + 1]:
            continue
        out.append((i, values[i]))
    return out


def dominant_period(values: List[float], min_lag: int, max_lag: int) -> float:
    """Period of the strongest repeat in `values`, in samples, or nan.

    Searches normalized autocorrelation over the inclusive lag bounds and prefers the
    smallest peak within SUBHARMONIC_TOLERANCE of the best, since a periodic signal also
    correlates at every multiple of its true period.
    """
    n = len(values)
    min_lag = max(1, min_lag)
    max_lag = min(max_lag, n - 2)
    if n < 4 or max_lag < min_lag:
        return float("nan")
    corr = normalized_autocorrelation(values, max_lag)
    if not corr:
        return float("nan")
    # A short clip can collapse the valid range to one lag. There is then no competing
    # candidate to compare against, so retain it whenever the observed correlation is positive.
    if min_lag == max_lag:
        return float(min_lag) if corr[min_lag] > 0.0 else float("nan")
    peaks = local_maxima(corr, min_lag, max_lag)
    if not peaks:
        return float("nan")
    best = max(v for _, v in peaks)
    if best <= 0.0:
        return float("nan")
    for lag, v in peaks:
        if v >= best * SUBHARMONIC_TOLERANCE:
            return float(lag)
    return float("nan")


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
