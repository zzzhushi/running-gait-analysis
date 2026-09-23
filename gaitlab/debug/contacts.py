"""Reference contact annotations: human-marked initial-contact intervals for a clip.

These record agreement with a written annotation rule, not physical contact. Accuracy in a
criterion sense needs force plates, pressure insoles or marker-based capture; nothing here
claims it. A label is an interval because visual identification of the initial-contact frame
carries rater disagreement of the same order as the quantity being measured, so a single
frame would assert precision the method does not have.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import math
import re
from typing import Any, Dict, List, Mapping, Optional

SCHEMA = "gaitlab.contact-references/v1"

# Labels carry the pose file's hash and the instants it assigns to each frame, which makes a
# stale or re-extracted timeline detectable by comparison but not wrong by construction:
# nothing here checks those instants against the video's own frames. That correspondence is
# owned by frame/time validation, so every record states it rather than implying it.
TIMEBASE_NOT_VALIDATED = (
    "that the pose input's timestamps were extracted from the source video's actual frames"
)

# Side identity is not always visible from one camera, so a label names the track it can
# actually see. Mapping a track to a body side is a separate claim, made elsewhere.
TRACKS = ("near_foot", "far_foot")

VISIBILITY = ("clear", "uncertain", "occluded")

# How the annotator reached the frames they looked at. Detector-seeded windows cannot
# reveal a contact the detector never found, so coverage that depends on them is not
# evidence about how many contacts exist.
COVERAGE = ("full-sweep", "tiled-windows")

EVENTS = ("initial_contact", "toe_off")

# The order events were presented in. A repeat pass shown the same sequence carries
# information from the first pass in the sequence itself.
PRESENTATION_ORDERS = ("sequential", "randomized")

# A single pass measures nothing about agreement. `complete` is the state a repeat-pass
# check may consume; `draft` exists so a first pass can be stored without being mistaken
# for evidence.
STATUSES = ("draft", "complete")
REQUIRED_BLINDED_PASSES = 2
# What makes a repeat independent of the pass it is compared against: a different person, or
# enough elapsed time that the same person re-reads the footage rather than recalling a
# specific clip. Heuristic separation; the published reliability work this protocol imitates
# does not state the interval it used between passes.
INDEPENDENCE_BASES = ("different-annotator", "time-separated")
MIN_SAME_ANNOTATOR_SEPARATION = timedelta(hours=24)

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def _is_sha256_digest(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_HEX.fullmatch(value) is not None


class ContactReferenceError(ValueError):
    """Raised when a reference-annotation record is structurally invalid."""


def _check_event(event: Mapping[str, Any], where: str, errs: List[str]) -> None:
    kind = event.get("event")
    if kind not in EVENTS:
        errs.append(f"{where}: event must be one of {EVENTS} (got {kind!r})")
    if event.get("track") not in TRACKS:
        errs.append(f"{where}: track must be one of {TRACKS} (got {event.get('track')!r})")
    if event.get("visibility") not in VISIBILITY:
        errs.append(
            f"{where}: visibility must be one of {VISIBILITY} (got {event.get('visibility')!r})"
        )

    unlabelable = event.get("unlabelable", False)
    if not isinstance(unlabelable, bool):
        errs.append(f"{where}: unlabelable must be true or false")
        return

    interval = event.get("contact_interval_frames")
    central = event.get("central_frame")

    if unlabelable:
        # An ambiguous event is recorded as ambiguous. Carrying frames as well would let a
        # reader treat a declined judgement as a made one.
        if not event.get("unlabelable_reason"):
            errs.append(f"{where}: unlabelable event needs unlabelable_reason")
        if interval is not None or central is not None:
            errs.append(f"{where}: unlabelable event must not carry frames")
        return

    if not (isinstance(interval, (list, tuple)) and len(interval) == 2
            and all(isinstance(f, int) for f in interval)):
        errs.append(f"{where}: contact_interval_frames must be two integer frames")
        return
    lo, hi = interval
    if lo < 0 or hi < lo:
        errs.append(f"{where}: contact_interval_frames must be non-negative and ordered")
        return
    if not isinstance(central, int):
        errs.append(f"{where}: central_frame must be an integer")
    elif not lo <= central <= hi:
        # The interval is the uncertainty; a central frame outside it contradicts the label.
        errs.append(f"{where}: central_frame {central} outside interval [{lo}, {hi}]")
    _check_times(event, where, errs)


def _check_times(event: Mapping[str, Any], where: str, errs: List[str]) -> None:
    """Frame indices alone cannot be audited against a variable-rate clock.

    A label carries the instants its frames resolved to, so a nominated instant outside its
    own interval is caught here. Whether those instants are the video's real ones is not:
    see `TIMEBASE_NOT_VALIDATED`.
    """
    times = event.get("contact_interval_timestamps_s")
    central_t = event.get("central_timestamp_s")
    values = list(times or []) + [central_t]
    if not (isinstance(times, (list, tuple)) and len(times) == 2):
        errs.append(f"{where}: contact_interval_timestamps_s must be two seconds values")
        return
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
           for v in values):
        errs.append(f"{where}: timestamps must be finite numbers")
        return
    if times[1] < times[0]:
        errs.append(f"{where}: contact_interval_timestamps_s must be ordered")
    elif not times[0] <= central_t <= times[1]:
        errs.append(f"{where}: central_timestamp_s outside its interval")


def _check_pass(entry: Mapping[str, Any], index: int, errs: List[str]) -> None:
    where = f"pass {entry.get('pass_id', index)}"
    if not entry.get("pass_id"):
        errs.append(f"{where}: pass_id is required")
    if not entry.get("annotator"):
        errs.append(f"{where}: annotator is required")
    if _parse_session_time(entry.get("completed_at")) is None:
        errs.append(f"{where}: completed_at must be a timezone-aware ISO-8601 timestamp")
    for flag in ("blinded", "detector_hidden"):
        if not isinstance(entry.get(flag), bool):
            errs.append(f"{where}: {flag} must be true or false")
    if entry.get("blinded") is True and entry.get("detector_hidden") is False:
        # The rule defines a pass shown detector output as not blinded, so this pair
        # describes no procedure that can be run.
        errs.append(f"{where}: a pass shown the detector is not blinded")
    if entry.get("presentation_order") not in PRESENTATION_ORDERS:
        errs.append(
            f"{where}: presentation_order must be one of {PRESENTATION_ORDERS} "
            f"(got {entry.get('presentation_order')!r})"
        )
    events = entry.get("events")
    if not isinstance(events, list):
        errs.append(f"{where}: events must be a list")
        return
    for position, event in enumerate(events):
        _check_event(event, f"{where} event {position}", errs)


def _parse_session_time(value: Any) -> Optional[datetime]:
    """Return an aware annotation-session timestamp, or None when it is not usable."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _qualifies(entry: Mapping[str, Any]) -> bool:
    """Whether a pass may count toward agreement evidence.

    Both conditions, because they are asserted separately and a pass that saw the detector
    is anchored by it whatever else was withheld.
    """
    return entry.get("blinded") is True and entry.get("detector_hidden") is True


def _completion_gaps(record: Mapping[str, Any], passes: List[Mapping[str, Any]]) -> List[str]:
    """Why a record cannot yet be treated as agreement evidence, if anything."""
    errs: List[str] = []
    qualifying = [entry for entry in passes if _qualifies(entry)]
    if len(qualifying) < REQUIRED_BLINDED_PASSES:
        errs.append(
            f"status 'complete' needs {REQUIRED_BLINDED_PASSES} blinded passes with the "
            f"detector hidden (got {len(qualifying)})"
        )
        return errs

    pair = record.get("agreement_pair")
    if not isinstance(pair, Mapping):
        return ["status 'complete' needs agreement_pair naming the first and repeat passes"]
    first_id, repeat_id = pair.get("first_pass_id"), pair.get("repeat_pass_id")
    if not isinstance(first_id, str) or not isinstance(repeat_id, str) or first_id == repeat_id:
        return ["agreement_pair needs two distinct pass ids"]
    by_id = {entry.get("pass_id"): entry for entry in passes}
    first, repeat = by_id.get(first_id), by_id.get(repeat_id)
    if first is None or repeat is None:
        return ["agreement_pair names a pass that does not exist"]
    if not _qualifies(first) or not _qualifies(repeat):
        return ["agreement_pair passes must both be blinded with the detector hidden"]
    # The pair now resolves to two usable passes, so the remaining conditions are
    # independent of each other and are all reported together.
    if repeat.get("presentation_order") != "randomized":
        errs.append("agreement_pair repeat pass must be presented in randomized order")

    basis = pair.get("independence_basis")
    if basis not in INDEPENDENCE_BASES:
        errs.append(f"agreement_pair independence_basis must be one of {INDEPENDENCE_BASES}")
    elif basis == "different-annotator":
        if first.get("annotator") == repeat.get("annotator"):
            errs.append("different-annotator agreement_pair needs distinct annotators")
    else:
        errs.extend(_separation_gaps(first, repeat))
    return errs


def _separation_gaps(first: Mapping[str, Any], repeat: Mapping[str, Any]) -> List[str]:
    """Whether one annotator's two sessions are far enough apart, and in the right order."""
    first_at = _parse_session_time(first.get("completed_at"))
    repeat_at = _parse_session_time(repeat.get("completed_at"))
    if first_at is None or repeat_at is None:
        return ["time-separated agreement_pair needs usable session timestamps"]
    if repeat_at < first_at:
        # Elapsed time is not the problem here: whichever pass came first is the one the
        # repeat should be compared against, so the pair names them the wrong way round.
        return ["agreement_pair repeat pass predates the first pass"]
    if repeat_at - first_at < MIN_SAME_ANNOTATOR_SEPARATION:
        return [
            "time-separated agreement_pair needs at least "
            f"{int(MIN_SAME_ANNOTATOR_SEPARATION.total_seconds() // 3600)} hours"
        ]
    return []


def validate(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """Check a reference-annotation record; raise ContactReferenceError listing every problem.

    Returns the record so it can be chained.
    """
    errs: List[str] = []
    if record.get("schema") != SCHEMA:
        errs.append(f"schema must be {SCHEMA!r} (got {record.get('schema')!r})")
    for field in ("clip", "annotation_rule"):
        if not record.get(field):
            errs.append(f"{field} is required")
    for field in ("video_sha256", "pose_sha256"):
        value = record.get(field)
        if not value:
            errs.append(f"{field} is required")
        elif not _is_sha256_digest(value):
            errs.append(f"{field} must be a 64-character hexadecimal SHA-256 digest")
    limits = record.get("does_not_validate")
    if not isinstance(limits, list) or TIMEBASE_NOT_VALIDATED not in limits:
        errs.append(
            "does_not_validate must state that pose timestamps are not checked against the "
            "source video's frames; without it a record reads as timebase-validated evidence"
        )
    if record.get("coverage") not in COVERAGE:
        errs.append(f"coverage must be one of {COVERAGE} (got {record.get('coverage')!r})")
    status = record.get("status")
    if status not in STATUSES:
        errs.append(f"status must be one of {STATUSES} (got {status!r})")

    passes = record.get("passes")
    if not isinstance(passes, list) or not passes:
        errs.append("passes must be a non-empty list")
    else:
        seen = set()
        for index, entry in enumerate(passes):
            _check_pass(entry, index, errs)
            pass_id = entry.get("pass_id")
            if pass_id in seen:
                errs.append(f"duplicate pass_id {pass_id!r}")
            seen.add(pass_id)
        if status == "complete":
            errs.extend(_completion_gaps(record, passes))

    if errs:
        raise ContactReferenceError("; ".join(errs))
    return record


def uncertainty_frames(event: Mapping[str, Any]) -> Optional[int]:
    """Width of a label's interval, or None when the event is unlabelable.

    Derived from the interval rather than stored, so the two cannot disagree.
    """
    interval = event.get("contact_interval_frames")
    if not interval:
        return None
    return interval[1] - interval[0]


def labelled_events(record: Mapping[str, Any], pass_id: str,
                    event: str = "initial_contact") -> List[Dict[str, Any]]:
    """Events of one kind from one pass, excluding those the annotator declined to label."""
    for entry in record["passes"]:
        if entry["pass_id"] == pass_id:
            return [dict(item) for item in entry["events"]
                    if item["event"] == event and not item.get("unlabelable", False)]
    raise KeyError(f"no pass {pass_id!r} in this record")


def as_debug_references(record: Mapping[str, Any], pass_id: str,
                        track_to_side: Mapping[str, str]) -> List[Dict[str, Any]]:
    """Reference layer for the debug record, from one annotation pass.

    `track_to_side` maps each labelled track to `l` or `r`. That mapping is a claim the
    annotation does not make — one camera cannot always tell which leg is which — so it is
    required rather than assumed, and an unmapped track raises instead of producing a
    reference the renderer would silently discard.

    Frames come from the interval's central frame; the interval and its instants travel
    with them so a consumer cannot quietly turn a range into a point estimate.
    """
    unknown = {side for side in track_to_side.values() if side not in ("l", "r")}
    if unknown:
        raise KeyError(f"track_to_side must map to 'l' or 'r' (got {sorted(unknown)})")
    out = []
    for event in labelled_events(record, pass_id):
        track = event["track"]
        if track not in track_to_side:
            raise KeyError(
                f"track {track!r} has no side in track_to_side; the debug record selects "
                f"references by side, so an unmapped track would render nothing"
            )
        out.append({
            "side": track_to_side[track],
            "track": track,
            "frame_index": event["central_frame"],
            "contact_interval_frames": list(event["contact_interval_frames"]),
            "contact_interval_timestamps_s": list(event["contact_interval_timestamps_s"]),
            "visibility": event["visibility"],
            "provenance": f"{record['annotation_rule']}/{pass_id}",
        })
    return out
