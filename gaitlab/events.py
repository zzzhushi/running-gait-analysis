"""Gait-event detection from normalized landmarks.

A foot is on the ground roughly when its ankle is at its lowest point in the image
(largest y). We therefore take per-foot contacts as local maxima of the (smoothed)
ankle-y signal, and toe-off as the moment the foot has lifted a set fraction of its
vertical range afterwards. Everything downstream (cadence, contact time, per-stride
metrics) is segmented from these events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Dict, List, Tuple

from . import geometry as geo
from .schema import PoseSequence


@dataclass
class GaitEvents:
    strikes: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    toeoffs: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    stance: Dict[str, List[Tuple[int, int]]] = field(default_factory=lambda: {"l": [], "r": []})
    cadence_spm: float = float("nan")
    stride_time: Dict[str, float] = field(default_factory=dict)   # seconds, median
    contact_time: Dict[str, float] = field(default_factory=dict)  # seconds, median

    def midstance(self, side: str) -> List[int]:
        return [int((s + e) / 2) for (s, e) in self.stance[side]]


def detect_events(seq: PoseSequence) -> GaitEvents:
    ev = GaitEvents()
    fps = seq.fps or 30.0
    n = seq.n
    if n < 4:
        return ev

    min_dist = max(3, int(fps * 0.22))  # two contacts of one foot can't be closer than this

    for side in ("l", "r"):
        ankle_y = geo.moving_average(seq.series_y(f"{side}_ankle"), 3)
        amp = geo.peak_to_peak(ankle_y)
        if amp != amp or amp <= 0:
            continue
        strikes = geo.find_peaks(ankle_y, min_distance=min_dist, min_prominence=amp * 0.12)
        ev.strikes[side] = strikes

        # toe-off: first frame after a strike where the foot has lifted >25% of its range.
        lift_thresh = amp * 0.25
        toeoffs: List[int] = []
        stance: List[Tuple[int, int]] = []
        for k, s in enumerate(strikes):
            top = ankle_y[s]
            next_s = strikes[k + 1] if k + 1 < len(strikes) else n
            to = None
            for i in range(s + 1, next_s):
                if top - ankle_y[i] >= lift_thresh:
                    to = i
                    break
            if to is None:
                to = min(next_s - 1, s + int(fps * 0.20))
            toeoffs.append(to)
            stance.append((s, to))
        ev.toeoffs[side] = toeoffs
        ev.stance[side] = stance

        same_foot = [strikes[i + 1] - strikes[i] for i in range(len(strikes) - 1)]
        if same_foot:
            ev.stride_time[side] = median(same_foot) / fps
        contacts = [(to - s) / fps for (s, to) in stance]
        if contacts:
            ev.contact_time[side] = median(contacts)

    # cadence from the merged (either-foot) step interval — robust to edge effects
    all_strikes = sorted(ev.strikes["l"] + ev.strikes["r"])
    steps = [all_strikes[i + 1] - all_strikes[i] for i in range(len(all_strikes) - 1)]
    if steps:
        step_s = median(steps) / fps
        if step_s > 0:
            ev.cadence_spm = 60.0 / step_s
    return ev
