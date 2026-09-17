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

    Frequency analysis needs uniform spacing, and PoseSequence supports variable frame rates
    and dropped frames — so the raw series is not safe to autocorrelate directly.
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


# How close a shorter lag must come to the best correlation before it is preferred over it.
SUBHARMONIC_TOLERANCE = 0.85


def dominant_period(values: List[float], min_lag: int, max_lag: int) -> float:
    """Period of the strongest repeat in `values`, in frames, or nan.

    Normalized autocorrelation over `min_lag..max_lag`, returning the lag of the tallest
    local maximum. NaNs are treated as zero deviation from the mean so a dropout weakens
    the correlation rather than poisoning it.

    Measures the period WITHOUT detecting gait events first, which is the whole point: a
    period derived from the peaks cannot judge whether those peaks are real.

    Coarse by construction — a whole number of frames, so a 21.3-frame stride reads as 21.
    Use it to decide which peaks are plausible, never as a timing measurement.
    """
    n = len(values)
    min_lag = max(1, min_lag)
    max_lag = min(max_lag, n - 2)
    if n < 4 or max_lag < min_lag:
        return float("nan")
    finite = [v for v in values if not math.isnan(v)]
    if not finite:
        return float("nan")
    m = sum(finite) / len(finite)
    dev = [0.0 if math.isnan(v) else v - m for v in values]
    total = sum(d * d for d in dev)
    if total <= 0.0:
        return float("nan")
    # r[lag], unbiased for the shrinking overlap so long lags are not penalised.
    r: List[float] = []
    for lag in range(min_lag, max_lag + 1):
        acc = 0.0
        for i in range(n - lag):
            acc += dev[i] * dev[i + lag]
        r.append(acc / (total * (n - lag) / n))
    # Endpoints count as one-sided maxima: min_lag..max_lag is inclusive, so an interior-only
    # scan makes the exact limits unreachable.
    last = len(r) - 1
    peaks = []
    if last >= 1 and r[0] >= r[1]:
        peaks.append((min_lag, r[0]))
    peaks += [(min_lag + i, r[i]) for i in range(1, last)
              if r[i] >= r[i - 1] and r[i] >= r[i + 1]]
    if last >= 1 and r[last] >= r[last - 1]:
        peaks.append((min_lag + last, r[last]))
    if not peaks:
        return float("nan")
    best_r = max(v for _, v in peaks)
    if best_r <= 0.0:
        return float("nan")
    # Prefer the SMALLEST lag correlating about as well as the best: a periodic signal peaks
    # at every multiple of its period, so the tallest is not reliably the fundamental. It
    # cannot run away downward — min_lag is a physiological floor, below which the swing-phase
    # bump this exists to reject already sits.
    for lag, v in peaks:
        if v >= best_r * SUBHARMONIC_TOLERANCE:
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
