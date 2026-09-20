"""Completeness of a pose sequence's sampling grid.

An extractor that samples only some of a clip's frames still reports a self-consistent
frame rate, because that rate is derived from the frames it kept. The loss survives in
the gaps: they become whole multiples of the source's frame interval. Recovering that
interval yields the frame count the file actually had, from the timestamps alone.

Sparse grids matter because event timing is quantised to them, and irregular ones carry
timing jitter that displaces the extrema the gait metrics are measured from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

# Frame intervals are recovered from gaps up to this multiple of the sample median; beyond
# it, a clip sampled this sparsely is not measurable anyway.
MAX_DROPPED_RUN = 8

# Share of gaps that must sit near a whole multiple of a candidate interval for it to be
# accepted, leaving room for a tail of seeks and stalls that fit no grid.
GRID_QUORUM = 0.9

# Half a frame of slack: beyond it, a gap is closer to another multiple.
GRID_TOLERANCE = 0.15


@dataclass(frozen=True)
class GridHealth:
    """How much of the source's frame grid a pose sequence actually carries."""

    captured: int
    implied: int
    interval: float
    irregularity: float

    @property
    def captured_fraction(self) -> float:
        return self.captured / self.implied if self.implied else 0.0


def frame_interval(timestamps: Sequence[float]) -> Optional[float]:
    """Return the source's frame interval in seconds, or None if it cannot be recovered.

    The largest candidate under which nearly every gap is a whole multiple; with no frames
    missing that is the median gap itself.
    """
    gaps = sorted(b - a for a, b in zip(timestamps, timestamps[1:]) if b > a)
    if not gaps:
        return None
    median = gaps[len(gaps) // 2]
    if median <= 0:
        return None
    for divisor in range(1, MAX_DROPPED_RUN + 1):
        candidate = median / divisor
        offsets = sorted(abs(g / candidate - round(g / candidate)) for g in gaps)
        if offsets[int(len(offsets) * GRID_QUORUM)] < GRID_TOLERANCE:
            return candidate
    return median


def grid_health(timestamps: Sequence[float]) -> GridHealth:
    """Assess how completely `timestamps` samples the grid they were drawn from."""
    n = len(timestamps)
    interval = frame_interval(timestamps) if n > 1 else None
    if not interval:
        return GridHealth(captured=n, implied=n, interval=0.0, irregularity=0.0)
    implied = round((timestamps[-1] - timestamps[0]) / interval) + 1
    gaps = [b - a for a, b in zip(timestamps, timestamps[1:]) if b > a]
    median = sorted(gaps)[len(gaps) // 2]
    irregularity = sum(1 for g in gaps if g > 1.5 * median) / len(gaps) if gaps else 0.0
    return GridHealth(captured=n, implied=max(implied, n), interval=interval,
                      irregularity=irregularity)
