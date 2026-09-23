"""Schema and coverage rules for reference contact annotations."""

from __future__ import annotations

import copy

import pytest
from PIL import Image

from gaitlab.debug.contacts import (
    SCHEMA,
    ContactReferenceError,
    as_debug_references,
    labelled_events,
    uncertainty_frames,
    validate,
)
from scripts.overstride_render import sweep_centers


def _record():
    return {
        "schema": SCHEMA,
        "clip": "female_overstride",
        "video_sha256": "0" * 64,
        "annotation_rule": "initial-contact-v1",
        "coverage": "full-sweep",
        "passes": [{
            "pass_id": "a1",
            "annotator": "annotator-a",
            "blinded": True,
            "detector_hidden": True,
            "events": [
                {
                    "event": "initial_contact",
                    "track": "near_foot",
                    "contact_interval_frames": [581, 587],
                    "central_frame": 584,
                    "visibility": "clear",
                    "unlabelable": False,
                },
                {
                    "event": "initial_contact",
                    "track": "far_foot",
                    "visibility": "occluded",
                    "unlabelable": True,
                    "unlabelable_reason": "far limb behind the near limb",
                },
            ],
        }],
    }


def test_a_well_formed_record_validates():
    validate(_record())


@pytest.mark.parametrize("mutate,match", [
    (lambda r: r.update(schema="gaitlab.contact-references/v0"), "schema"),
    (lambda r: r.update(clip=""), "clip is required"),
    (lambda r: r.update(video_sha256=""), "video_sha256 is required"),
    (lambda r: r.update(annotation_rule=""), "annotation_rule is required"),
    (lambda r: r.update(coverage="detector-seeded"), "coverage"),
    (lambda r: r.update(passes=[]), "non-empty"),
    (lambda r: r["passes"][0].update(annotator=""), "annotator is required"),
    (lambda r: r["passes"][0].update(blinded="yes"), "blinded"),
    (lambda r: r["passes"][0]["events"][0].update(track="l"), "track"),
    (lambda r: r["passes"][0]["events"][0].update(visibility="maybe"), "visibility"),
    (lambda r: r["passes"][0]["events"][0].update(event="heel_strike"), "event"),
])
def test_malformed_records_are_rejected(mutate, match):
    record = _record()
    mutate(record)
    with pytest.raises(ContactReferenceError, match=match):
        validate(record)


def test_a_nominated_frame_outside_its_own_interval_is_a_contradiction():
    record = _record()
    record["passes"][0]["events"][0]["central_frame"] = 590

    with pytest.raises(ContactReferenceError, match="outside interval"):
        validate(record)


def test_an_unlabelable_event_may_not_also_carry_frames():
    """Recording frames on a declined judgement makes it read as a made one."""
    record = _record()
    record["passes"][0]["events"][1]["contact_interval_frames"] = [100, 106]

    with pytest.raises(ContactReferenceError, match="must not carry frames"):
        validate(record)


def test_an_unlabelable_event_needs_a_reason():
    record = _record()
    del record["passes"][0]["events"][1]["unlabelable_reason"]

    with pytest.raises(ContactReferenceError, match="unlabelable_reason"):
        validate(record)


def test_repeated_pass_ids_are_rejected():
    record = _record()
    record["passes"].append(copy.deepcopy(record["passes"][0]))

    with pytest.raises(ContactReferenceError, match="duplicate pass_id"):
        validate(record)


def test_uncertainty_comes_from_the_interval():
    record = validate(_record())
    events = labelled_events(record, "a1")

    assert uncertainty_frames(events[0]) == 6
    assert uncertainty_frames(record["passes"][0]["events"][1]) is None


def test_labelled_events_exclude_the_ones_the_annotator_declined():
    record = validate(_record())
    events = labelled_events(record, "a1")

    assert [event["track"] for event in events] == ["near_foot"]


def test_debug_references_carry_the_interval_with_the_frame():
    """A consumer must not be able to take the nominated frame as a point estimate."""
    record = validate(_record())

    references = as_debug_references(record, "a1")

    assert references == [{
        "track": "near_foot",
        "frame_index": 584,
        "contact_interval_frames": [581, 587],
        "visibility": "clear",
        "provenance": "initial-contact-v1/a1",
    }]


@pytest.mark.parametrize("frame_count,radius", [(1, 3), (7, 3), (8, 3), (100, 3), (1160, 3),
                                                (360, 5), (9, 0)])
def test_sweep_windows_tile_every_frame_without_a_gap(frame_count, radius):
    """A frame no window covers is a contact an annotator is never shown."""
    covered = set()
    for center in sweep_centers(frame_count, radius):
        covered.update(range(max(center - radius, 0), min(center + radius, frame_count - 1) + 1))

    assert covered == set(range(frame_count))


def test_an_empty_clip_sweeps_to_nothing():
    assert sweep_centers(0, 3) == []


def test_sweep_export_hides_the_detector_and_records_how_coverage_was_reached(tmp_path):
    """A sweep that still showed detector markers would reintroduce the anchoring it removes,
    and a manifest that did not say so would leave a reader unable to tell the passes apart.
    """
    import json

    from scripts import export_overstride_debug
    from tests.reach_fixture import load_authored_reach_fixture

    case = load_authored_reach_fixture()
    pose = tmp_path / "pose.json"
    pose.write_text(json.dumps(case.sequence.to_pose_dict()))

    clip = tmp_path / "clip.gif"
    # Distinct per frame, or the encoder collapses identical frames and the indices shift.
    frames = [Image.new("RGB", (case.sequence.width, case.sequence.height),
                        (30 + index * 40, 40, 50))
              for index in range(case.sequence.n)]
    frames[0].save(clip, save_all=True, append_images=frames[1:], duration=17, loop=0,
                   optimize=False)

    out = tmp_path / "swept"
    assert export_overstride_debug.main([
        "--pose", str(pose), "--video", str(clip), "--output", str(out),
        "--sweep", "--strip-radius", "1",
    ]) == 0

    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["detector_markers_visible"] is False
    assert manifest["coverage"] == "full-sweep"
