"""Video-only landmark reference records for issue #82.

These labels are independent of a particular pose model. They describe visible image
proxies or explicitly uncertain inferences, not anatomical ground truth.
"""

from __future__ import annotations

import math
import re

SCHEMA = "gaitlab.landmark-references/v1"
RULE = "side-landmark-review-v1"
LANDMARKS = {"hip", "ankle", "heel", "big_toe"}
BASIS = {"visible_body", "visible_shoe", "inferred", "unlabelable"}
TRACKS = {"near_leg", "far_leg"}
SIDES = ("l", "r", None)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def validate(record: dict, *, video_sha256: str, pts: list[float],
             image_size: tuple[int, int]) -> dict:
    """Reject contradictory or falsely paired labels; do not judge point correctness."""
    if record.get("schema") != SCHEMA or record.get("rule") != RULE:
        raise ValueError("unknown landmark reference schema or rule")
    if record.get("view") not in ("side-left", "side-right"):
        raise ValueError("landmark references for overstride require a side view")
    if not isinstance(record.get("clip"), str) or not record["clip"].strip():
        raise ValueError("clip is required")
    if not isinstance(record.get("video_sha256"), str) or not SHA256.fullmatch(record["video_sha256"]):
        raise ValueError("video_sha256 must be a SHA-256 hex digest")
    if record["video_sha256"] != video_sha256:
        raise ValueError("reference labels belong to different video bytes")
    if record.get("image_size") != list(image_size):
        raise ValueError("reference image size does not match the decoded video")
    if record.get("frame_count") != len(pts):
        raise ValueError("reference frame count does not match the decoded video")
    if record.get("model_layers_visible") is not False:
        raise ValueError("reference annotations must be made without model layers")
    if type(record.get("prior_pose_exposure")) is not bool:
        raise ValueError("prior_pose_exposure must be recorded as true or false")
    if not isinstance(record.get("annotator"), str) or not record["annotator"].strip():
        raise ValueError("annotator is required")
    observations = record.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("observations must be non-empty")
    seen = set()
    for observation in observations:
        if not isinstance(observation, dict):
            raise ValueError("observation must be an object")
        index = observation.get("frame_index")
        if type(index) is not int or not 0 <= index < len(pts):
            raise ValueError("observation frame_index is out of range")
        timestamp = observation.get("video_pts_s")
        if (type(timestamp) not in (int, float) or not math.isfinite(timestamp)
                or abs(timestamp - pts[index]) > 0.000001):
            raise ValueError("observation video_pts_s does not match its decoded frame")
        track = observation.get("track")
        if (not isinstance(track, str) or track not in TRACKS
                or "side" not in observation or observation["side"] not in SIDES):
            raise ValueError("track or anatomical side is invalid")
        landmark, basis = observation.get("landmark"), observation.get("basis")
        if (not isinstance(landmark, str) or landmark not in LANDMARKS
                or not isinstance(basis, str) or basis not in BASIS):
            raise ValueError("landmark or observation basis is invalid")
        key = (index, track, landmark)
        if key in seen:
            raise ValueError("duplicate observation for frame, track and landmark")
        seen.add(key)
        if basis == "unlabelable":
            if observation.get("xy") is not None or observation.get("uncertainty_radius_px") is not None:
                raise ValueError("unlabelable observation must not carry a point")
            if not observation.get("reason"):
                raise ValueError("unlabelable observation needs a reason")
            continue
        xy = observation.get("xy")
        radius = observation.get("uncertainty_radius_px")
        if (not isinstance(xy, list) or len(xy) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in xy)
                or not 0 <= xy[0] < image_size[0] or not 0 <= xy[1] < image_size[1]):
            raise ValueError("labelled observation needs an in-bounds finite xy point")
        if type(radius) not in (int, float) or not math.isfinite(radius) or radius <= 0:
            raise ValueError("labelled observation needs a positive uncertainty radius")
        if landmark == "hip" and basis != "inferred":
            raise ValueError("hip joint centre is hidden in this video; label it as inferred")
        if landmark in {"heel", "big_toe"} and basis == "visible_body":
            raise ValueError("heel and toe anatomy are hidden by shoes; use visible_shoe or inferred")
    return record
