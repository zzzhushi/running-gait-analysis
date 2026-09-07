"""Confidence-aware gait-event estimates from a single 2-D pose sequence.

These are kinematic estimates, not force-platform contact events. Initial contact
is anchored to a local maximum of the tracked foot/ankle vertical signal. Toe-off
requires an observed, sustained lift after contact; it is never fabricated when
the signal does not contain one. Candidate contacts are checked for physiological
spacing and left/right alternation before downstream metrics use them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median
from typing import Dict, List, Optional, Tuple

from . import geometry as geo
from .schema import PoseSequence


@dataclass
class GaitEvents:
    strikes: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    toeoffs: Dict[str, List[int]] = field(default_factory=lambda: {"l": [], "r": []})
    stance: Dict[str, List[Tuple[int, int]]] = field(default_factory=lambda: {"l": [], "r": []})
    cadence_spm: float = float("nan")
    stride_time: Dict[str, float] = field(default_factory=dict)
    step_time: Dict[str, float] = field(default_factory=dict)
    contact_time: Dict[str, float] = field(default_factory=dict)
    flight_time: Dict[str, float] = field(default_factory=dict)
    duty_factor: Dict[str, float] = field(default_factory=dict)
    stride_times: Dict[str, List[float]] = field(default_factory=lambda: {"l": [], "r": []})
    step_times: Dict[str, List[float]] = field(default_factory=lambda: {"l": [], "r": []})
    contact_times: Dict[str, List[float]] = field(default_factory=lambda: {"l": [], "r": []})
    flight_times: Dict[str, List[float]] = field(default_factory=lambda: {"l": [], "r": []})
    sample_count: Dict[str, int] = field(default_factory=dict)
    alternation_ratio: float = 0.0
    confidence: str = "low"
    warnings: List[str] = field(default_factory=list)

    def midstance(self, side: str) -> List[int]:
        return [int((s + e) / 2) for (s, e) in self.stance[side]]

    def event_frames(self) -> List[int]:
        return sorted({f for side in ("l", "r") for f in self.strikes[side] + self.toeoffs[side]})


def _foot_y(seq: PoseSequence, side: str) -> List[float]:
    """Robust vertical foot signal; median of available ankle/heel/toe points."""
    names = [f"{side}_ankle", f"{side}_heel", f"{side}_big_toe"]
    out: List[float] = []
    for f in range(seq.n):
        vals = [seq.xy(f, name)[1] for name in names if seq.has(name)]
        vals = [v for v in vals if math.isfinite(v)]
        out.append(median(vals) if vals else float("nan"))
    return geo.moving_average(out, 3)


def _candidate_strikes(seq: PoseSequence, signal: List[float]) -> List[int]:
    vals = [v for v in signal if math.isfinite(v)]
    if len(vals) < 4:
        return []
    amp = max(vals) - min(vals)
    if amp <= 0:
        return []
    candidates = geo.find_peaks(signal, min_distance=1, min_prominence=amp * 0.12)
    # Apply spacing in elapsed time rather than frame count so variable-frame-
    # rate recordings do not silently fall back to the nominal fps metadata.
    spaced: List[int] = []
    for frame in candidates:
        if not spaced or seq.elapsed(spaced[-1], frame) >= 0.22:
            spaced.append(frame)
        elif signal[frame] > signal[spaced[-1]]:
            spaced[-1] = frame
    return spaced


def _enforce_alternation(
    candidates: Dict[str, List[int]], signals: Dict[str, List[float]], seq: PoseSequence
) -> Tuple[Dict[str, List[int]], float]:
    merged = sorted((f, side) for side in ("l", "r") for f in candidates[side])
    if not merged:
        return {"l": [], "r": []}, 0.0

    accepted: List[Tuple[int, str]] = []
    min_step_s = 0.12
    for frame, side in merged:
        if not accepted:
            accepted.append((frame, side))
            continue
        prev_frame, prev_side = accepted[-1]
        too_close = seq.elapsed(prev_frame, frame) < min_step_s
        if side == prev_side or too_close:
            if signals[side][frame] > signals[prev_side][prev_frame]:
                accepted[-1] = (frame, side)
            continue
        accepted.append((frame, side))

    raw_transitions = max(0, len(merged) - 1)
    alternating = sum(1 for a, b in zip(merged, merged[1:]) if a[1] != b[1])
    ratio = alternating / raw_transitions if raw_transitions else 0.0
    out = {"l": [], "r": []}
    for frame, side in accepted:
        out[side].append(frame)
    return out, ratio


def _toeoff_after(
    seq: PoseSequence, signal: List[float], strike: int, stop: int, amplitude: float
) -> Optional[int]:
    """First sustained observed lift after strike, or None when not observed."""
    min_lift = max(amplitude * 0.18, 1.0)
    baseline = signal[strike]
    for f in range(strike + 1, max(strike + 1, stop - 1)):
        if seq.elapsed(strike, f) < 0.04:
            continue
        if seq.elapsed(strike, f) > 0.65:
            break
        if not all(math.isfinite(signal[j]) for j in (f - 1, f, f + 1)):
            continue
        lifted = baseline - signal[f] >= min_lift
        rising = signal[f + 1] < signal[f - 1]
        if lifted and rising:
            return f
    return None


def _median_elapsed(seq: PoseSequence, pairs: List[Tuple[int, int]]) -> Optional[float]:
    vals = [seq.elapsed(a, b) for a, b in pairs if b > a]
    return median(vals) if vals else None


def _preceding_opposite(strikes: Dict[str, List[int]], side: str, frame: int) -> Optional[int]:
    other = "r" if side == "l" else "l"
    prior = [f for f in strikes[other] if f < frame]
    return prior[-1] if prior else None


def detect_events(seq: PoseSequence) -> GaitEvents:
    ev = GaitEvents()
    if seq.n < 4:
        ev.warnings.append("clip_too_short")
        return ev

    signals = {side: _foot_y(seq, side) for side in ("l", "r")}
    candidates = {side: _candidate_strikes(seq, signals[side]) for side in ("l", "r")}
    ev.strikes, ev.alternation_ratio = _enforce_alternation(candidates, signals, seq)

    for side in ("l", "r"):
        signal = signals[side]
        finite = [v for v in signal if math.isfinite(v)]
        amplitude = (max(finite) - min(finite)) if finite else 0.0
        strikes = ev.strikes[side]

        stride_pairs = list(zip(strikes, strikes[1:]))
        ev.stride_times[side] = [seq.elapsed(a, b) for a, b in stride_pairs]
        stride = median(ev.stride_times[side]) if ev.stride_times[side] else None
        if stride is not None:
            ev.stride_time[side] = stride

        step_pairs = []
        for strike in strikes:
            previous = _preceding_opposite(ev.strikes, side, strike)
            if previous is not None:
                step_pairs.append((previous, strike))
        ev.step_times[side] = [seq.elapsed(a, b) for a, b in step_pairs]
        step = median(ev.step_times[side]) if ev.step_times[side] else None
        if step is not None:
            ev.step_time[side] = step

        for i, strike in enumerate(strikes):
            stop = strikes[i + 1] if i + 1 < len(strikes) else seq.n
            toeoff = _toeoff_after(seq, signal, strike, stop, amplitude)
            if toeoff is None:
                continue
            contact = seq.elapsed(strike, toeoff)
            local_stride = seq.elapsed(strike, stop) if stop < seq.n else stride
            if local_stride and contact >= local_stride * 0.75:
                continue
            ev.toeoffs[side].append(toeoff)
            ev.stance[side].append((strike, toeoff))

        contacts = [seq.elapsed(s, to) for s, to in ev.stance[side]]
        ev.contact_times[side] = contacts
        if contacts:
            ev.contact_time[side] = median(contacts)
        if stride and contacts:
            ev.duty_factor[side] = median(contacts) / stride * 100.0

        flights = []
        for toeoff in ev.toeoffs[side]:
            other = "r" if side == "l" else "l"
            later = [s for s in ev.strikes[other] if s > toeoff]
            if later:
                flights.append(seq.elapsed(toeoff, later[0]))
        if flights:
            ev.flight_times[side] = flights
            ev.flight_time[side] = median(flights)

    merged = sorted(ev.strikes["l"] + ev.strikes["r"])
    step_s = _median_elapsed(seq, list(zip(merged, merged[1:])))
    if step_s and step_s > 0:
        ev.cadence_spm = 60.0 / step_s

    ev.sample_count = {
        "strikes": len(merged),
        "strides_l": max(0, len(ev.strikes["l"]) - 1),
        "strides_r": max(0, len(ev.strikes["r"]) - 1),
        "complete_stances_l": len(ev.stance["l"]),
        "complete_stances_r": len(ev.stance["r"]),
    }

    complete_stances = len(ev.stance["l"]) + len(ev.stance["r"])
    if ev.alternation_ratio < 0.8:
        ev.warnings.append("inconsistent_left_right_alternation")
    if complete_stances < 4:
        ev.warnings.append("too_few_complete_stances")
    if not math.isfinite(ev.cadence_spm) or not (100 <= ev.cadence_spm <= 260):
        ev.warnings.append("implausible_or_missing_cadence")

    if not ev.warnings and complete_stances >= 8 and ev.alternation_ratio >= 0.9:
        ev.confidence = "high"
    elif complete_stances >= 4 and ev.alternation_ratio >= 0.75 and math.isfinite(ev.cadence_spm):
        ev.confidence = "moderate"
    else:
        ev.confidence = "low"
    return ev
