"""Per-frame presentation timestamps, shared by every video-based pose extractor.

Only RTMPoseExtractor and MediaPipeExtractor need this — the in-browser
extractor (web/js/pose.js) derives timestamps from a live playthrough instead,
and every downstream consumer just reads `timestamps` off the pose JSON. Kept
inside extractor/ rather than promoted to gaitlab/core/ for that reason: this
is plumbing for the two video extractors, not part of the engine's contract.

Was duplicated verbatim between extract_pose.py and extract_pose_mediapipe.py
before this module existed.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional, Sequence, Tuple


def probe_timestamps(path: str) -> Optional[List[float]]:
    """Real per-frame presentation timestamps (seconds), via ffprobe.

    Reads the container's actual frame PTS — the same clock the browser's
    <video> uses — so the overlay stays aligned even on variable-frame-rate
    phone video, where OpenCV's CAP_PROP_POS_MSEC is unreliable. Returns a list
    sorted ascending (presentation order, matching how OpenCV hands back
    frames), or None if ffprobe is missing / the probe fails.
    """
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "frame=best_effort_timestamp_time",
             "-of", "csv=print_section=0", path],
            capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    vals = []
    for line in out.stdout.splitlines():
        s = line.strip().rstrip(",")
        if not s or s == "N/A":
            continue
        try:
            vals.append(float(s))
        except ValueError:
            continue
    if len(vals) < 2:
        return None
    vals.sort()  # decode order -> presentation order (handles B-frame reordering)
    return vals


def _monotonic_positive(ts: Optional[Sequence[float]]) -> bool:
    return (ts is not None and len(ts) > 1 and ts[-1] > 0
            and all(ts[i] >= ts[i - 1] for i in range(1, len(ts))))


def choose_timestamps(
    probe_ts: Optional[List[float]],
    pos_msec: Sequence[float],
    kept_idx: Sequence[int],
    total_read: int,
) -> Tuple[Optional[List[float]], str]:
    """Pick the best per-frame timestamp source, in priority order:
    ffprobe PTS  >  OpenCV POS_MSEC  >  None (constant frame rate).
    """
    # 1. ffprobe — only if its frame count lines up with what OpenCV decoded, so we
    #    can index the kept frames into it safely.
    if probe_ts is not None and kept_idx and len(probe_ts) >= total_read:
        picked = [probe_ts[i] for i in kept_idx]
        if _monotonic_positive(picked):
            return picked, "ffprobe (real container PTS)"
    # 2. OpenCV POS_MSEC — usable on many files, unreliable on some VFR clips.
    if _monotonic_positive(pos_msec):
        return list(pos_msec), "OpenCV POS_MSEC"
    # 3. nothing trustworthy — the player falls back to f/fps.
    return None, "constant frame rate (f/fps) — overlay may drift on VFR video"
