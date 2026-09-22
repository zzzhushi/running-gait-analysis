"""Build the machine-readable source of truth for overstride debug artifacts.

This module does not render and does not implement a second overstride formula. It records
the existing reach curve, detected events, denominator provenance, and production metric
result. Tables and images in ``scripts/overstride_render.py`` consume this record.

The record establishes traceability, not correctness of pose localization or contact time.
Those require independent reference annotations and are deliberately represented as optional
layers rather than silently substituted for detector output.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, Iterable, Mapping, Optional

from ..core.events import GaitEvents, detect_events
from ..core.reach import Denominator, ReachSample
from ..core.schema import PoseSequence
from ..metrics.compute import aggregate
from ..metrics.ctx import Ctx
from ..metrics.defs import METRIC_DEFS
from ..metrics.keys import MetricKey

SCHEMA = "gaitlab.overstride-debug/v1"
DOES_NOT_VALIDATE = [
    "correct pose-landmark localization",
    "correct initial-contact timing",
    "that a manually supplied pose file was extracted from the supplied video",
    "anatomical or clinical meaning of the overstride value",
]


# Distinguishes a sequence whose per-frame clock predates provenance recording from one
# whose clock is deliberately assumed, so neither reads as the other.
UNRECORDED_TIMESTAMP_SOURCE = "per-frame (provider unrecorded)"
ASSUMED_TIMESTAMP_SOURCE = "nominal-fps (assumed constant frame rate)"


def _timestamp_source(seq: PoseSequence) -> str:
    """Name the clock behind `seq`'s frame times, never collapsing two providers into one."""
    if seq.timestamps is None:
        return ASSUMED_TIMESTAMP_SOURCE
    return seq.timestamp_source or UNRECORDED_TIMESTAMP_SOURCE


def _finite(value: float) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def _point(point, provenance: str = "pose") -> Dict[str, Any]:
    return {
        "x": _finite(point[0]),
        "y": _finite(point[1]),
        "confidence": _finite(point[2]) if len(point) > 2 else None,
        "provenance": provenance,
    }


def _xy(point, provenance: str) -> Dict[str, Any]:
    return {
        "x": _finite(point[0]),
        "y": _finite(point[1]),
        "provenance": provenance,
    }


def _reading(reading) -> Dict[str, Any]:
    return {
        "px": _finite(reading.px),
        "pct_leg": _finite(reading.pct),
        "px_unavailable": reading.px_unavailable,
        "pct_unavailable": reading.pct_unavailable,
    }


def _denominator_record(denominator: Denominator) -> Dict[str, Any]:
    samples = []
    for sample in denominator.samples:
        samples.append({
            "frame_index": sample.frame,
            "timestamp_s": sample.t,
            "side": sample.side,
            "points": {
                "hip": _point(sample.hip),
                "knee": _point(sample.knee),
                "ankle": _point(sample.ankle),
            },
            "segments_px": {
                "thigh": sample.thigh_px,
                "shank": sample.shank_px,
                "total": sample.total_px,
            },
            "minimum_confidence": sample.min_confidence,
        })
    return {
        "id": "projected-leg-length",
        "value_px": _finite(denominator.px),
        "method": denominator.method,
        "unavailable": denominator.unavailable,
        "samples": samples,
    }


def _annotation_index(annotations: Optional[Mapping[str, Any]], key: str) -> Dict[tuple, dict]:
    indexed: Dict[tuple, dict] = {}
    for item in (annotations or {}).get(key, []):
        side = item.get("side")
        frame = item.get("frame_index", item.get("original_frame_index"))
        if side in ("l", "r") and isinstance(frame, int):
            indexed[(side, frame)] = dict(item)
    return indexed


def _references_for_frame(annotations: Optional[Mapping[str, Any]], side: str,
                          frame: int) -> list[dict]:
    matches = []
    for item in (annotations or {}).get("references", []):
        if item.get("side") != side:
            continue
        interval = item.get("contact_interval_frames")
        exact = item.get("frame_index")
        if exact == frame or (
            isinstance(interval, list) and len(interval) == 2
            and interval[0] <= frame <= interval[1]
        ):
            matches.append(dict(item))
    return matches


def _record_id(source_id: str, sample: ReachSample) -> str:
    # Content-address the measurement inputs as well as its source location. Two pose
    # extractors applied to the same video frame must not receive an indistinguishable ID.
    identity = [
        source_id, sample.frame, round(sample.t, 9), sample.side, sample.facing,
        sample.hip, sample.ankle, sample.heel, sample.toe,
        sample.denominator.px, sample.denominator.method,
    ]
    raw = json.dumps(identity, separators=(",", ":")).encode()
    return "os-" + hashlib.sha256(raw).hexdigest()[:16]


def _validity(sample: ReachSample) -> Dict[str, Any]:
    reasons = []
    if sample.ankle_reach.px_unavailable:
        reasons.append(sample.ankle_reach.px_unavailable)
    if sample.ankle_reach.pct_unavailable:
        reasons.append(sample.ankle_reach.pct_unavailable)
    if sample.inclination_unavailable:
        reasons.append(sample.inclination_unavailable)
    return {"usable": not reasons, "reasons": list(dict.fromkeys(reasons))}


def _frame_record(seq: PoseSequence, sample: ReachSample, source_id: str,
                  detected_strikes: Iterable[int], adjustments: Mapping[tuple, dict],
                  annotations: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    frame = sample.frame
    side = sample.side
    timestamp = sample.t
    adjustment = adjustments.get((side, frame))
    references = _references_for_frame(annotations, side, frame)
    detected = frame in detected_strikes
    record_id = _record_id(source_id, sample)

    pose_landmarks = {
        name: _point(seq.pt(frame, name)) for name in seq.keypoint_names
    }
    heel_conf = sample.heel[2]
    toe_conf = sample.toe[2]
    midpoint = _xy(
        sample.foot_midpoint_proxy,
        "arithmetic mean of pose heel and big-toe coordinates",
    )
    midpoint["confidence"] = _finite(min(heel_conf, toe_conf)) if heel_conf > 0 and toe_conf > 0 else None

    return {
        "record_id": record_id,
        "source_frame": {
            "identifier": f"{source_id}#decoded-frame={frame}",
            "decoded_index": frame,
            "timestamp_s": timestamp,
            "effective_fps": seq.effective_fps,
        },
        "side": side,
        "view": seq.view,
        "facing_sign": sample.facing,
        "processing": sample.processing,
        "pose_landmarks": pose_landmarks,
        "measurement_landmarks": {
            "hip": _point(sample.hip),
            "ankle": _point(sample.ankle),
            "heel": _point(sample.heel),
            "big_toe": _point(sample.toe),
            "foot_midpoint_proxy": midpoint,
        },
        "denominator_id": "projected-leg-length",
        "reach": {
            "ankle": _reading(sample.ankle_reach),
            "heel": _reading(sample.heel_reach),
            "big_toe": _reading(sample.toe_reach),
            "foot_midpoint_proxy": _reading(sample.midpoint_reach),
        },
        "inclination": {
            "degrees_from_vertical": _finite(sample.inclination_deg),
            "unavailable": sample.inclination_unavailable,
        },
        "contact": {
            "detected": detected,
            "original_frame_index": frame if detected else None,
            "original_timestamp_s": timestamp if detected else None,
            "subframe_timestamp_s": None,
            "adjusted_frame_index": adjustment.get("adjusted_frame_index") if adjustment else None,
            "adjusted_timestamp_s": adjustment.get("adjusted_timestamp_s") if adjustment else None,
            "adjustment_provenance": adjustment.get("provenance") if adjustment else None,
        },
        "references": references,
        "validity": _validity(sample),
    }


def build_overstride_debug_record(
    seq: PoseSequence,
    events: Optional[GaitEvents] = None,
    *,
    source_id: Optional[str] = None,
    annotations: Optional[Mapping[str, Any]] = None,
    denominator: Optional[Denominator] = None,
    facing: Optional[int] = None,
) -> Dict[str, Any]:
    """Capture every input and intermediate behind the production overstride result.

    ``denominator`` and ``facing`` are injectable for authored fixtures. For normal clips they
    default to the same values used by :class:`~gaitlab.metrics.ctx.Ctx`.
    """
    seq.validate()
    events = events or detect_events(seq)
    source_id = source_id or seq.source or "unknown"
    ctx = Ctx(seq, events, None)
    if denominator is not None:
        ctx.denominator = denominator
        ctx.leg = denominator.px
    if facing is not None:
        ctx.facing = facing
    adjustments = _annotation_index(annotations, "adjustments")

    frames = []
    by_id = {}
    for side in ("l", "r"):
        curve = ctx.reach_curve(side)
        for sample in curve:
            record = _frame_record(
                seq, sample, source_id, events.strikes[side], adjustments, annotations
            )
            frames.append(record)
            by_id[(side, sample.frame)] = record["record_id"]

    contacts = [
        {
            "record_id": by_id[(side, frame)],
            "side": side,
            "frame_index": frame,
            "timestamp_s": seq.time_at(frame),
        }
        for side in ("l", "r")
        for frame in events.strikes[side]
        if (side, frame) in by_id
    ]
    # Invoke the registered production formula and aggregator against this exact context.
    # In normal use this is the report path. Dependency injection exists only so the authored
    # formula fixture can keep its known denominator/facing while exercising the same hook.
    definition = METRIC_DEFS[MetricKey.OVERSTRIDE]
    raw_per_side = {side: definition.compute(ctx, side) for side in ("l", "r")}
    metric_value = aggregate(
        definition.aggregate, raw_per_side["l"], raw_per_side["r"]
    )
    per_side = {side: _finite(value) for side, value in raw_per_side.items()}

    return {
        "schema": SCHEMA,
        "source": {
            "id": source_id,
            "pose_source": seq.source,
            "width": seq.width,
            "height": seq.height,
            "view": seq.view,
            "nominal_fps": seq.fps,
            "effective_fps": seq.effective_fps,
            "frame_count": seq.n,
            "timestamp_source": _timestamp_source(seq),
            "frame_count_note": seq.frame_count_note,
        },
        "measurement": {
            "name": "overstride",
            "unit": "%leg",
            "definition": "facing-adjusted horizontal ankle-to-hip reach at detected contact",
            "denominator": _denominator_record(ctx.denominator),
            "production_report": {
                "value": _finite(metric_value),
                "per_side": per_side,
                "contact_record_ids": [contact["record_id"] for contact in contacts],
            },
            "debug_dependency_overrides": {
                "denominator": denominator is not None,
                "facing": facing is not None,
            },
        },
        "events": {
            "detected_contacts": contacts,
            "reference_contacts": list((annotations or {}).get("references", [])),
            "adjustments": list((annotations or {}).get("adjustments", [])),
        },
        "frames": frames,
        "does_not_validate": list(DOES_NOT_VALIDATE),
    }


def frame_records(record: Mapping[str, Any], *, side: Optional[str] = None) -> list[dict]:
    """Return frame records in deterministic frame/side order."""
    rows = [dict(row) for row in record["frames"] if side is None or row["side"] == side]
    return sorted(rows, key=lambda row: (row["source_frame"]["decoded_index"], row["side"]))


def record_by_id(record: Mapping[str, Any]) -> Dict[str, dict]:
    return {row["record_id"]: row for row in record["frames"]}
