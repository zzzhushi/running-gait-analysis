"""Per-frame presentation timestamps shared by Python video extractors.

The browser derives its own timestamps; downstream consumers read the normalized values
from `PoseSequence`.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional, Sequence, Tuple

from gaitlab.core.schema import ASSUMED_TIMEBASE


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
    """True when every frame carries a distinct, advancing instant.

    Strict: a repeated timestamp makes two frame indices name the same moment, which
    breaks the index-to-instant mapping every timing-derived metric assumes.
    """
    return (ts is not None and len(ts) > 1
            and all(ts[i] > ts[i - 1] for i in range(1, len(ts))))


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
    # 3. nothing trustworthy — frame times are derived from the nominal rate, which
    #    drifts against the real clock on variable-frame-rate video.
    return None, ASSUMED_TIMEBASE


# One unreadable frame at the tail is a known decoder edge effect; loss beyond that is
# judged as a fraction of the container's own count, so a short clip gets no larger
# proportional allowance than a long one. Heuristic thresholds; not derived from a
# measured failure rate.
TRAILING_FRAME_ALLOWANCE = 1
DROPPED_FRAME_FRACTION = 0.01


def check_frame_count(expected: Optional[int], actual: int) -> Tuple[Optional[str], bool]:
    """Compare frames OpenCV actually decoded against the container's own count.

    `expected` is the container's frame count (e.g. `len(probe_timestamps(...))`), or
    None when it could not be determined. Returns `(note, severe)`: `note` is None when
    the counts agree, more frames were decoded than expected, or `expected` is None.
    `severe` means the loss beyond `TRAILING_FRAME_ALLOWANCE` exceeds
    `DROPPED_FRAME_FRACTION` of `expected`, and the caller should refuse rather than
    silently return a shorter sequence.
    """
    if expected is None or actual >= expected:
        return None, False
    deficit = expected - actual
    note = f"decoded {actual} of {expected} container frames ({deficit} dropped)"
    beyond_edge = deficit - TRAILING_FRAME_ALLOWANCE
    severe = beyond_edge > expected * DROPPED_FRAME_FRACTION
    return note, severe
