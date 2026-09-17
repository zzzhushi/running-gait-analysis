#!/usr/bin/env python3
"""Measure a clip's true cadence from raw pixels — no pose model, no gaitlab engine.

This exists so the numbers in tests/data/*.groundtruth.json can be re-derived by anyone,
rather than being magic constants someone once eyeballed. Cadence regressions in this
project have historically been "fixed" against intuition; an independent measurement is
what makes a real-video test trustworthy.

The answer comes from COUNTING steps, not from a frequency estimate. Frequency analysis
cannot distinguish a step rate from twice or half that rate: a signal with energy at f and
2f fits both readings equally well, and two frequency methods agreeing proves only that
they chose the same reading. A count of discrete events has no harmonic to lock onto.

Three stages, each able to invalidate the answer:

  1. COUNT — the topmost row of the subject rises and falls once per step. Apexes of that
     trace are counted; cadence is intervals over elapsed time. This is the measurement.
  2. TIMEBASE — a clip shot in slow-motion mode reports a frame rate that is not the rate
     it was captured at, so every per-second figure derived from it is wrong by that
     factor. At a flight apex the body is in free fall, so its vertical acceleration in
     px/frame^2 against a known body scale gives the capture rate independently.
  3. CROSS-CHECK — leg motion energy and the head trace are read spectrally. These can
     only raise doubt; they never supply the answer.

    python3 scripts/measure_cadence_groundtruth.py tests/data/male_side.mp4

Assumes one person, filmed from a fixed camera, whole body in frame. Requires ffmpeg and
ffprobe on PATH. Everything else is stdlib.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from collections import deque
from typing import List, Optional, Tuple

# Downscale used throughout. Small enough for pure-Python arithmetic over a whole clip,
# large enough to keep the limbs several pixels wide.
W, H = 90, 160
LEG_BAND = (100, 160)      # rows spanning hips -> feet at this scale

# Gray levels below the per-pixel bright reference that count as subject rather than scene.
DARK_MARGIN = 35
# Columns in a row that must be dark before the row counts as occupied, which rejects
# single-pixel noise and thin scene edges.
DARK_RUN = 3

# Step periods the search will consider, in seconds. The low end must reach a slow gait
# seen through a slow-motion container, where the apparent rate is a fraction of the real one.
MIN_STEP_S, MAX_STEP_S = 0.20, 2.50
# Apex spacing floor as a fraction of the measured step period. A real apex sits at 1.0 and
# any secondary bump well below it.
APEX_SPACING_FRAC = 0.6
# How close a shorter lag must come to the best correlation before it is preferred. A
# periodic signal correlates at every multiple of its period, so the tallest peak is not
# reliably the fundamental.
SUBHARMONIC_TOLERANCE = 0.85

# Frames per step below which the free-fall fit has too few samples to be meaningful. The
# check is reported as unavailable rather than guessed at.
MIN_FRAMES_PER_STEP_FOR_TIMEBASE = 20
# Stature only sets the pixel scale, and the implied rate varies as its square root, so a
# rough value still separates a 1x timebase from a 2x or 4x one.
DEFAULT_STATURE_M = 1.70
GRAVITY = 9.81
# Relative gap at which the free-fall estimate is reported as contradicting the assumed
# capture rate. Wide, because the estimate is only precise enough to separate whole factors.
TIMEBASE_TOLERANCE = 0.5

# Relative gap above which a cross-check is treated as contradicting the count.
CROSSCHECK_TOLERANCE = 0.08


def probe(path: str) -> Tuple[float, float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True)
    d = json.loads(out.stdout)
    num, den = d["streams"][0]["r_frame_rate"].split("/")
    return float(num) / float(den), float(d["format"]["duration"])


def gray_frames(path: str) -> bytes:
    """Whole clip as raw W*H grayscale bytes."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H},format=gray",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True)
    return out.stdout


def movavg(xs: List[float], k: int) -> List[float]:
    if k < 2:
        return list(xs)
    out: List[float] = []
    q: deque = deque()
    acc = 0.0
    for v in xs:
        q.append(v)
        acc += v
        if len(q) > k:
            acc -= q.popleft()
        out.append(acc / len(q))
    return out


def detrend(xs: List[float], fps: float, seconds: float = 2.0) -> List[float]:
    """Remove drift slower than `seconds`, expressed in time so the cutoff is frame-rate
    independent."""
    base = movavg(xs, max(3, int(seconds * fps) | 1))
    return [a - b for a, b in zip(xs, base)]


# --- subject outline -------------------------------------------------------

def bright_reference(raw: bytes, n: int) -> bytearray:
    """Per-pixel 90th percentile over time: the scene without the subject in front of it.

    A percentile rather than a median because a treadmill runner is stationary, so the
    median of a pixel she occupies is her, not the scene behind her.
    """
    fsz = W * H
    sample = list(range(0, n, max(1, n // 60)))
    ref = bytearray(fsz)
    for p in range(fsz):
        vals = sorted(raw[f * fsz + p] for f in sample)
        ref[p] = vals[int(0.9 * (len(vals) - 1))]
    return ref


def outline_rows(raw: bytes, n: int, ref: bytearray) -> Tuple[List[float], List[float]]:
    """Topmost and bottommost occupied row per frame."""
    fsz = W * H
    top: List[float] = []
    bot: List[float] = []
    last_t = last_b = 0.0
    for f in range(n):
        off = f * fsz
        hi = lo = None
        for r in range(H):
            base, rbase = off + r * W, r * W
            hits = 0
            for c in range(W):
                if ref[rbase + c] - raw[base + c] > DARK_MARGIN:
                    hits += 1
                    if hits >= DARK_RUN:
                        break
            if hits >= DARK_RUN:
                if hi is None:
                    hi = r
                lo = r
        if hi is not None:
            last_t, last_b = float(hi), float(lo)
        top.append(last_t)
        bot.append(last_b)
    return top, bot


# --- period and counting ---------------------------------------------------

def dominant_lag(xs: List[float], min_lag: int, max_lag: int) -> float:
    """Lag of the strongest repeat, in frames, or nan.

    Prefers the smallest lag correlating about as well as the best, so a multiple of the
    period cannot win over the period itself.
    """
    n = len(xs)
    min_lag = max(1, min_lag)
    max_lag = min(max_lag, n - 2)
    if n < 4 or max_lag < min_lag:
        return float("nan")
    m = sum(xs) / n
    dev = [v - m for v in xs]
    total = sum(d * d for d in dev)
    if total <= 0.0:
        return float("nan")
    r: List[float] = []
    for lag in range(min_lag, max_lag + 1):
        acc = 0.0
        for i in range(n - lag):
            acc += dev[i] * dev[i + lag]
        r.append(acc / (total * (n - lag) / n))
    # Every signal correlates with itself at short lags regardless of period, so the shortest
    # lags are the skirt of the zero-lag lobe rather than evidence of repetition. Start after
    # the correlation first goes negative, which is past that lobe.
    start = next((i for i, v in enumerate(r) if v < 0.0), 0)
    last = len(r) - 1
    peaks: List[Tuple[int, float]] = [
        (min_lag + i, r[i]) for i in range(max(start, 1), last)
        if r[i] >= r[i - 1] and r[i] >= r[i + 1]]
    # The top of the range is a legitimate period, so it counts as a one-sided maximum.
    if last > start and r[last] >= r[last - 1]:
        peaks.append((min_lag + last, r[last]))
    if not peaks:
        return float("nan")
    best_lag, best = max(peaks, key=lambda t: t[1])
    if best <= 0.0:
        return float("nan")
    # A harmonic sits at an integer multiple of the period, so only a lag that divides the
    # strongest one can be the fundamental it was a multiple of. Without that constraint any
    # short-lag noise peak qualifies, and smoothing makes nearby samples correlate.
    for lag, v in peaks:
        if lag >= best_lag:
            break
        ratio = best_lag / lag
        if abs(ratio - round(ratio)) <= 0.1 and v >= best * SUBHARMONIC_TOLERANCE:
            return float(lag)
    return float(best_lag)


def apex_frames(head: List[float], period_frames: float) -> List[int]:
    """Frames where the subject is at its highest, one per step."""
    up = [-v for v in head]
    span = max(up) - min(up)
    if span <= 0:
        return []
    cand = [i for i in range(1, len(up) - 1)
            if up[i] >= up[i - 1] and up[i] >= up[i + 1]
            and (up[i] > up[i - 1] or up[i] > up[i + 1])]
    cand.sort(key=lambda i: up[i], reverse=True)
    gap = max(2, int(period_frames * APEX_SPACING_FRAC))
    chosen: List[int] = []
    for i in cand:
        if all(abs(i - j) >= gap for j in chosen):
            chosen.append(i)
    chosen.sort()
    return chosen


# --- timebase --------------------------------------------------------------

def implied_capture_fps(head: List[float], apexes: List[int], px_per_m: float,
                        half_window: int) -> float:
    """Capture rate implied by free fall at each apex, or nan.

    The subject is unsupported at the top of a flight phase, so the apex traces a parabola
    whose curvature is gravity expressed in px/frame^2. Solving that against a known pixel
    scale gives the rate the frames were taken at, which a slow-motion container does not
    report.
    """
    accs: List[float] = []
    for i in apexes:
        if i - half_window < 0 or i + half_window >= len(head):
            continue
        ys = head[i - half_window:i + half_window + 1]
        xs = list(range(-half_window, half_window + 1))
        sxx = sum(x * x for x in xs)
        sxxxx = sum(x ** 4 for x in xs)
        n = len(xs)
        sy = sum(ys)
        sxxy = sum(x * x * y for x, y in zip(xs, ys))
        den = n * sxxxx - sxx * sxx
        if den == 0:
            continue
        a = (n * sxxy - sxx * sy) / den          # quadratic coefficient
        if a > 0:                                 # rows grow downward, so falling is positive
            accs.append(2 * a)
    if len(accs) < 3:
        return float("nan")
    accs.sort()
    a = accs[len(accs) // 2]
    return math.sqrt(GRAVITY * px_per_m / a)


# --- cross-checks ----------------------------------------------------------

def dft_mag(xs: List[float], f_hz: float, fps: float) -> float:
    w = 2 * math.pi * f_hz / fps
    re = im = 0.0
    for n, v in enumerate(xs):
        re += v * math.cos(w * n)
        im -= v * math.sin(w * n)
    return math.hypot(re, im) / len(xs)


def peak_freq(xs: List[float], fps: float, lo: float, hi: float, step: float = 0.002) -> float:
    best_f, best_m = 0.0, -1.0
    f = lo
    while f <= hi:
        m = dft_mag(xs, f, fps)
        if m > best_m:
            best_f, best_m = f, m
        f += step
    return best_f


def motion_energy(raw: bytes, n: int) -> List[float]:
    fsz = W * H
    r0, r1 = LEG_BAND
    energy: List[float] = []
    prev = raw[r0 * W:r1 * W]
    for f in range(1, n):
        off = f * fsz
        cur = raw[off + r0 * W: off + r1 * W]
        s = 0
        for a, b in zip(cur, prev):
            d = a - b
            s += d if d >= 0 else -d
        energy.append(s / len(cur))
        prev = cur
    return energy


def main() -> Optional[int]:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--stature-m", type=float, default=DEFAULT_STATURE_M,
                    help="subject height in metres, for the timebase check only")
    ap.add_argument("--capture-fps", type=float, default=None,
                    help="rate the clip was RECORDED at, when that differs from the rate the "
                         "container plays it at (slow-motion mode). Defaults to the container "
                         "rate; the free-fall check warns when that looks wrong.")
    ap.add_argument("--json", action="store_true", help="emit the measurement as JSON")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found on PATH")

    container_fps, container_dur = probe(args.video)
    raw = gray_frames(args.video)
    n = len(raw) // (W * H)
    if n < 30:
        sys.exit("clip too short to measure")

    ref = bright_reference(raw, n)
    top, bottom = outline_rows(raw, n, ref)

    head = movavg(top, max(1, int(container_fps / 40)))
    wave = detrend(head, container_fps)
    period_frames = dominant_lag(wave, int(MIN_STEP_S * container_fps),
                                 int(MAX_STEP_S * container_fps))
    if period_frames != period_frames:
        sys.exit("no periodic vertical motion found; is one whole person in frame?")

    apexes = apex_frames(wave, period_frames)
    if len(apexes) < 4:
        sys.exit("too few steps to measure")
    steps = len(apexes) - 1
    span_frames = apexes[-1] - apexes[0]
    frames_per_step = span_frames / steps
    cadence_container = 60.0 * container_fps / frames_per_step

    heights = sorted(b - t for t, b in zip(top, bottom) if b > t)
    px_per_m = (heights[len(heights) // 2] / args.stature_m) if heights else float("nan")

    capture_fps = float("nan")
    if frames_per_step >= MIN_FRAMES_PER_STEP_FOR_TIMEBASE and px_per_m == px_per_m:
        capture_fps = implied_capture_fps(
            head, apexes, px_per_m, max(3, min(8, int(frames_per_step * 0.12))))

    # Correcting the timebase automatically would mean choosing a whole factor from an
    # estimate that cannot reliably separate 3 from 4, and a wrong factor is worse than an
    # uncorrected container rate. So the caller supplies the capture rate and the estimate
    # only contradicts it.
    real_fps = args.capture_fps or container_fps
    factor = real_fps / container_fps
    cadence = cadence_container * factor
    duration = n / real_fps

    timebase_warning = ""
    if capture_fps != capture_fps:
        timebase_note = (f"NOT CHECKED — {frames_per_step:.0f} frames per step is too few for "
                         f"a free-fall fit")
    elif abs(capture_fps - real_fps) > real_fps * TIMEBASE_TOLERANCE:
        timebase_note = (f"CONTRADICTED — free fall implies {capture_fps:.0f} fps capture, not "
                         f"the {real_fps:.0f} fps assumed")
        timebase_warning = (f"Re-run with --capture-fps near {capture_fps:.0f} if this clip was "
                            f"shot in slow motion; every per-second figure below is wrong by "
                            f"that factor if so.")
    else:
        timebase_note = f"consistent — free fall implies {capture_fps:.0f} fps capture"

    energy = detrend(motion_energy(raw, n), container_fps)
    f_energy = peak_freq(energy, container_fps, 1.0 / MAX_STEP_S, 1.0 / MIN_STEP_S)
    f_head = peak_freq(wave, container_fps, 1.0 / MAX_STEP_S, 1.0 / MIN_STEP_S)
    checks = {"leg motion energy": f_energy * 60.0 * factor,
              "head bounce spectrum": f_head * 60.0 * factor}
    disagree = [k for k, v in checks.items()
                if abs(v - cadence) > cadence * CROSSCHECK_TOLERANCE]

    if args.json:
        print(json.dumps({
            "cadence_spm": round(cadence, 2),
            "steps_counted": steps + 1,
            "duration_s": round(duration, 3),
            "container_fps": round(container_fps, 3),
            "capture_fps_estimate": None if capture_fps != capture_fps else round(capture_fps, 1),
            "capture_fps_assumed": round(real_fps, 3),
            "timebase_note": timebase_note,
            "crosschecks_spm": {k: round(v, 2) for k, v in checks.items()},
            "crosschecks_disagreeing": disagree,
        }, indent=2))
        return 0

    print(f"clip           : {args.video}")
    print(f"                 {n} frames · container {container_fps:.3f} fps · {container_dur:.2f} s")
    print()
    print(f"steps counted  : {steps + 1} apexes over {span_frames / container_fps:.2f} s of container time")
    print(f"timebase       : {timebase_note}")
    if timebase_warning:
        print(f"                 {timebase_warning}")
    print()
    for name, value in checks.items():
        mark = "differs" if name in disagree else "ok"
        print(f"  cross-check {name:22s} {value:7.2f} spm   [{mark}]")
    print()
    print(f"DURATION       : {duration:.2f} s of real time")
    print(f"CADENCE        : {cadence:.2f} spm")
    if timebase_warning:
        return 1
    if disagree:
        print("NOTE           : a cross-check disagrees with the count. The count is the "
              "measurement, but look at the clip before trusting this.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
