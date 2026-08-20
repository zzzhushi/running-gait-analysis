#!/usr/bin/env python3
"""Measure a clip's true cadence from raw pixels — no pose model, no gaitlab engine.

This exists so the numbers in tests/data/*.groundtruth.json can be re-derived by anyone,
rather than being magic constants someone once eyeballed. Cadence regressions in this
project have historically been "fixed" against intuition (165 -> 200 -> 163.6 spm); an
independent measurement is what makes a real-video test trustworthy.

Two independent signals, which should agree to well under 1 spm:

  A. Leg-band motion energy — mean absolute frame-to-frame difference over the lower part
     of the frame. The legs are the only large periodic motion there, and they produce one
     burst per STEP.
  B. Silhouette bounce — subtract a temporal-median background (valid for a static camera),
     take the runner's silhouette centroid, and track its vertical position. The body
     bounces once per step.

Both are then evaluated with a fine-grid DFT over the plausible step-frequency band, so the
resolution is not limited by the FFT bin width.

    python3 scripts/measure_cadence_groundtruth.py tests/data/male_side.mp4

Requires ffmpeg/ffprobe on PATH. Everything else is stdlib.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from collections import deque
from typing import List, Optional

# Downscale used for both methods. Small enough for pure-Python arithmetic over a whole
# clip, large enough to keep the limbs several pixels wide.
W, H = 90, 160
LEG_BAND = (100, 160)      # rows spanning hips -> feet at this scale
SILHOUETTE_BAND = (60, 160)  # torso + legs; excludes ceiling/background clutter
# A runner is somewhere between a slow jog and a sprint cadence.
STEP_HZ = (2.0, 3.9)       # 120 - 234 spm


def probe(path: str) -> tuple:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate,nb_frames", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True)
    d = json.loads(out.stdout)
    st = d["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    duration = float(d["format"]["duration"])
    return fps, duration


def gray_frames(path: str) -> bytes:
    """Whole clip as raw W*H grayscale bytes."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H},format=gray",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True)
    return out.stdout


def movavg(xs: List[float], k: int) -> List[float]:
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


def detrend(xs: List[float], k: int = 61) -> List[float]:
    base = movavg(xs, k)
    return [a - b for a, b in zip(xs, base)]


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


def silhouette_centroid_y(raw: bytes, n: int, thresh: int = 28) -> List[float]:
    fsz = W * H
    r0, r1 = SILHOUETTE_BAND
    # temporal median background, sampled to keep this cheap
    sample = list(range(0, n, 7))
    bg = bytearray(fsz)
    for p in range(fsz):
        vals = sorted(raw[f * fsz + p] for f in sample)
        bg[p] = vals[len(vals) // 2]

    cy: List[float] = []
    for f in range(n):
        off = f * fsz
        num = den = 0.0
        for r in range(r0, r1):
            base, bbase = off + r * W, r * W
            row = 0
            for c in range(W):
                d = raw[base + c] - bg[bbase + c]
                if d < 0:
                    d = -d
                if d > thresh:
                    row += 1
            num += row * r
            den += row
        cy.append(num / den if den > 0 else float("nan"))
    finite = [v for v in cy if v == v]
    fill = sum(finite) / len(finite) if finite else 0.0
    return [v if v == v else fill for v in cy]


def windows(xs: List[float], fps: float, seconds: float = 8.0) -> List[tuple]:
    out = []
    size = int(seconds * fps)
    for i in range(0, len(xs) - size + 1, size):
        out.append((i / fps, (i + size) / fps, xs[i:i + size]))
    return out


def main() -> Optional[int]:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--json", action="store_true", help="emit just the measured value as JSON")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found on PATH")

    fps, duration = probe(args.video)
    raw = gray_frames(args.video)
    n = len(raw) // (W * H)

    energy = detrend(motion_energy(raw, n))
    f_a = peak_freq(energy, fps, *STEP_HZ)

    centroid = detrend(silhouette_centroid_y(raw, n))
    f_b = peak_freq(centroid, fps, *STEP_HZ)

    # The stride harmonic is an internal consistency check: it must be half the step
    # frequency. If it isn't, one of the peaks locked onto a harmonic and the result
    # should not be trusted.
    f_a_stride = peak_freq(energy, fps, STEP_HZ[0] / 2, STEP_HZ[1] / 2)

    cadence = (f_a + f_b) / 2 * 60.0
    spread = abs(f_a - f_b) * 60.0

    if args.json:
        print(json.dumps({"cadence_spm": round(cadence, 2),
                          "method_spread_spm": round(spread, 2)}, indent=2))
        return 0

    print(f"clip           : {args.video}")
    print(f"                 {n} frames · {fps:.3f} fps · {duration:.2f} s")
    print()
    print(f"A motion energy: {f_a:.4f} Hz  ->  {f_a * 60:7.2f} spm")
    print(f"B silhouette   : {f_b:.4f} Hz  ->  {f_b * 60:7.2f} spm")
    print(f"  stride harmonic (A): {f_a_stride:.4f} Hz -> {f_a_stride * 120:7.2f} spm "
          f"[{'consistent' if abs(f_a_stride * 2 - f_a) < 0.05 else 'INCONSISTENT — do not trust'}]")
    print()
    print("per 8 s window (drift check):")
    for t0, t1, seg in windows(energy, fps):
        print(f"  {t0:5.1f}-{t1:5.1f}s   {peak_freq(seg, fps, *STEP_HZ) * 60:7.2f} spm")
    print()
    print(f"CADENCE        : {cadence:.2f} spm   (methods differ by {spread:.2f} spm)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
