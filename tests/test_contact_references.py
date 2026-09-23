"""Schema and coverage rules for reference contact annotations."""

from __future__ import annotations

import copy

import pytest
from PIL import Image

from gaitlab.debug.contacts import (
    SCHEMA,
    TIMEBASE_NOT_VALIDATED,
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
        "pose_sha256": "1" * 64,
        "does_not_validate": [TIMEBASE_NOT_VALIDATED],
        "annotation_rule": "initial-contact-v1",
        "coverage": "full-sweep",
        "status": "draft",
        "passes": [{
            "pass_id": "a1",
            "annotator": "annotator-a",
            "completed_at": "2026-09-20T10:00:00Z",
            "blinded": True,
            "detector_hidden": True,
            "presentation_order": "sequential",
            "events": [
                {
                    "event": "initial_contact",
                    "track": "near_foot",
                    "contact_interval_frames": [581, 587],
                    "central_frame": 584,
                    "contact_interval_timestamps_s": [4.8458, 4.8958],
                    "central_timestamp_s": 4.8708,
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
    (lambda r: r.pop("pose_sha256"), "pose_sha256 is required"),
    (lambda r: r.update(annotation_rule=""), "annotation_rule is required"),
    (lambda r: r.update(coverage="detector-seeded"), "coverage"),
    (lambda r: r.update(passes=[]), "non-empty"),
    (lambda r: r["passes"][0].update(annotator=""), "annotator is required"),
    (lambda r: r["passes"][0].update(completed_at="not-a-time"), "completed_at"),
    (lambda r: r["passes"][0].update(blinded="yes"), "blinded"),
    (lambda r: r["passes"][0]["events"][0].update(track="l"), "track"),
    (lambda r: r["passes"][0]["events"][0].update(visibility="maybe"), "visibility"),
    (lambda r: r["passes"][0]["events"][0].update(event="heel_strike"), "event"),
    (lambda r: r.update(status="final"), "status"),
    (lambda r: r["passes"][0].update(presentation_order="shuffled"), "presentation_order"),
    (lambda r: r["passes"][0]["events"][0].update(central_timestamp_s=9.0), "outside its interval"),
    (lambda r: r["passes"][0]["events"][0].update(contact_interval_timestamps_s=[5.0, 4.0]),
     "must be ordered"),
    (lambda r: r["passes"][0]["events"][0].update(contact_interval_timestamps_s=[float("nan"), 5.0]),
     "finite"),
    (lambda r: r["passes"][0]["events"][0].pop("contact_interval_timestamps_s"),
     "two seconds values"),
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

    references = as_debug_references(record, "a1", {"near_foot": "l"})

    assert references == [{
        "side": "l",
        "track": "near_foot",
        "frame_index": 584,
        "contact_interval_frames": [581, 587],
        "contact_interval_timestamps_s": [4.8458, 4.8958],
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


def _annotation_bundle(tmp_path, radius="1"):
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

    out = tmp_path / "annotate"
    assert export_overstride_debug.main([
        "--pose", str(pose), "--video", str(clip), "--output", str(out),
        "--sweep", "--strip-radius", radius,
    ]) == 0
    return case, out, pose


def test_annotation_bundle_contains_nothing_the_detector_selected(tmp_path):
    """Hiding the marker is not blinding. Filenames, a contact sheet, traces or a record
    chosen by the detector announce its predictions without drawing one.
    """
    _case, out, _pose = _annotation_bundle(tmp_path)

    produced = sorted(path.relative_to(out).as_posix()
                      for path in out.rglob("*") if path.is_file())

    assert "debug-record.json" not in produced
    assert "strikes.csv" not in produced
    assert not [name for name in produced if "contact-sheet" in name]
    assert not [name for name in produced if name.startswith("traces/")]
    # Detector-derived artifacts are named by record id; annotation frames are named by index.
    assert not [name for name in produced if "/os-" in name]
    assert all(name == "manifest.json" or name.startswith("frames/frame-")
               for name in produced), produced


def test_annotation_frames_carry_no_model_layer(tmp_path):
    """The pose overlay is the estimate the annotator exists to be independent of."""
    from PIL import Image as PILImage

    from scripts.overstride_render import render_annotated_frame

    case, out, _pose = _annotation_bundle(tmp_path)
    plain = PILImage.new("RGB", (case.sequence.width, case.sequence.height), (30, 40, 50))
    with PILImage.open(out / "frames" / "frame-000001.png") as annotation:
        annotated = annotation.convert("RGB").copy()

    # Above the footer strip, an annotation frame must be untouched source pixels, while the
    # diagnostic renderer draws plumb line, limb lines and landmark markers over the same area.
    region = (0, 0, case.sequence.width, case.sequence.height - 40)
    source = PILImage.new("RGB", (case.sequence.width, case.sequence.height), (30 + 40, 40, 50))
    assert annotated.crop(region).tobytes() == source.crop(region).tobytes()

    diagnostic, _plan = render_annotated_frame(
        _bundle_for(case), _row_for(case, 1), plain, show_detector=False
    )
    assert diagnostic.crop(region).tobytes() != plain.crop(region).tobytes()


def _bundle_for(case):
    from gaitlab.core.events import GaitEvents
    from gaitlab.debug.overstride import build_overstride_debug_record

    return build_overstride_debug_record(
        case.sequence, GaitEvents(strikes=case.forced_strikes), source_id=case.name,
        denominator=case.denominator, facing=case.facing,
    )


def _row_for(case, frame):
    from scripts.overstride_render import find_row

    return find_row(_bundle_for(case), "l", frame)


def test_annotation_manifest_states_coverage_and_that_no_model_layer_was_shown(tmp_path):
    import hashlib
    import json

    _case, out, pose = _annotation_bundle(tmp_path)
    manifest = json.loads((out / "manifest.json").read_text())

    assert manifest["coverage"] == "full-sweep"
    assert manifest["detector_markers_visible"] is False
    assert manifest["model_layers_visible"] is False
    assert manifest["annotation_rule"] == "initial-contact-v1"
    assert manifest["source_video"]["sha256"]
    # Compared against the actual input's digest, not just checked for presence: a
    # hard-coded or otherwise wrong hash would still be truthy.
    assert manifest["pose_input"]["sha256"] == hashlib.sha256(pose.read_bytes()).hexdigest()
    assert TIMEBASE_NOT_VALIDATED in manifest["does_not_validate"], (
        "a shifted or stale pose timeline can produce ordered, finite label timestamps "
        "that refer to the wrong instants; the manifest must name that limitation "
        "specifically, not just carry some does_not_validate entry"
    )


def test_annotation_frames_cover_every_frame_of_the_clip(tmp_path):
    case, out, _pose = _annotation_bundle(tmp_path)

    written = sorted(path.name for path in (out / "frames").iterdir())

    assert written == [f"frame-{index:06d}.png" for index in range(case.sequence.n)]


def test_one_pass_cannot_be_completion_evidence():
    """A single pass measures no agreement; marking it complete would let a labels PR
    present it as the repeat-pass check this issue requires."""
    record = _record()
    record["status"] = "complete"

    with pytest.raises(ContactReferenceError, match="needs 2 blinded passes"):
        validate(record)


def _complete_with_repeat(record, *, annotator="annotator-a", completed_at="2026-09-21T10:00:00Z",
                          independence_basis="time-separated"):
    record["status"] = "complete"
    repeat = copy.deepcopy(record["passes"][0])
    repeat["pass_id"] = "a2"
    repeat["annotator"] = annotator
    repeat["completed_at"] = completed_at
    repeat["presentation_order"] = "randomized"
    record["passes"].append(repeat)
    record["agreement_pair"] = {
        "first_pass_id": "a1",
        "repeat_pass_id": "a2",
        "independence_basis": independence_basis,
    }


def test_a_repeat_shown_in_the_same_order_is_not_completion_evidence():
    """An annotator can reproduce a remembered sequence rather than re-reading the footage."""
    record = _record()
    _complete_with_repeat(record)
    record["passes"][1]["presentation_order"] = "sequential"

    with pytest.raises(ContactReferenceError, match="randomized order"):
        validate(record)


def test_two_blinded_passes_with_a_randomized_repeat_complete_a_record():
    record = _record()
    _complete_with_repeat(record)

    validate(record)


def test_same_annotator_repeat_needs_the_documented_time_separation():
    record = _record()
    _complete_with_repeat(record, completed_at="2026-09-20T10:05:00Z")

    with pytest.raises(ContactReferenceError, match="at least 24 hours"):
        validate(record)


def test_different_annotator_repeat_can_complete_without_a_wait():
    record = _record()
    _complete_with_repeat(
        record, annotator="annotator-b", completed_at="2026-09-20T10:05:00Z",
        independence_basis="different-annotator",
    )

    validate(record)


def test_an_unmapped_track_cannot_be_turned_into_a_renderer_reference():
    """The debug record selects references by side, so an unmapped track would render
    nothing at all rather than failing."""
    record = validate(_record())

    with pytest.raises(KeyError, match="no side in track_to_side"):
        as_debug_references(record, "a1", {"far_foot": "r"})


def test_a_mapped_reference_is_visible_to_the_debug_record(tmp_path):
    """The end-to-end claim the intermediate dictionary cannot make."""
    from gaitlab.core.events import GaitEvents
    from gaitlab.debug.overstride import build_overstride_debug_record
    from scripts.overstride_render import find_row
    from tests.reach_fixture import load_authored_reach_fixture

    case = load_authored_reach_fixture()
    record = _record()
    event = record["passes"][0]["events"][0]
    event["contact_interval_frames"] = [1, 1]
    event["central_frame"] = 1
    event["contact_interval_timestamps_s"] = [case.sequence.time_at(1)] * 2
    event["central_timestamp_s"] = case.sequence.time_at(1)
    validate(record)

    references = as_debug_references(record, "a1", {"near_foot": "l"})
    bundle = build_overstride_debug_record(
        case.sequence, GaitEvents(strikes=case.forced_strikes), source_id=case.name,
        annotations={"references": references},
        denominator=case.denominator, facing=case.facing,
    )

    assert find_row(bundle, "l", 1)["references"], "mapped reference never reached the record"
    assert bundle["events"]["reference_contacts"][0]["side"] == "l"


def test_a_detector_exposed_pass_cannot_be_blinded():
    """The rule defines a pass shown detector output as not blinded, so the pair describes
    no procedure that can be run."""
    record = _record()
    record["passes"][0]["detector_hidden"] = False

    with pytest.raises(ContactReferenceError, match="shown the detector is not blinded"):
        validate(record)


def test_detector_exposed_passes_cannot_complete_a_record():
    """Two passes asserting `blinded` while the detector was on screen, with a randomized
    repeat, otherwise satisfy every completion condition — and would stand as agreement
    evidence about the bias that same detector is suspected of.
    """
    record = _record()
    record["status"] = "complete"
    record["passes"][0]["detector_hidden"] = False
    repeat = copy.deepcopy(record["passes"][0])
    repeat["pass_id"] = "a2"
    repeat["presentation_order"] = "randomized"
    record["passes"].append(repeat)

    with pytest.raises(ContactReferenceError):
        validate(record)


def test_agreement_pair_is_required_to_complete():
    record = _record()
    _complete_with_repeat(record)
    del record["agreement_pair"]

    with pytest.raises(ContactReferenceError, match="needs agreement_pair"):
        validate(record)


@pytest.mark.parametrize("mutate,match", [
    (lambda pair: pair.update(repeat_pass_id="a1"), "two distinct pass ids"),
    (lambda pair: pair.update(repeat_pass_id="nope"), "does not exist"),
    (lambda pair: pair.update(independence_basis="vibes"), "independence_basis"),
])
def test_malformed_agreement_pairs_are_rejected(mutate, match):
    record = _record()
    _complete_with_repeat(record)
    mutate(record["agreement_pair"])

    with pytest.raises(ContactReferenceError, match=match):
        validate(record)


def test_agreement_pair_cannot_name_a_pass_that_saw_the_detector():
    """Two other passes may qualify; the pair named is the one the claim rests on."""
    record = _record()
    _complete_with_repeat(record)
    exposed = copy.deepcopy(record["passes"][1])
    exposed.update(pass_id="a3", blinded=False, detector_hidden=False)
    record["passes"].append(exposed)
    record["agreement_pair"]["repeat_pass_id"] = "a3"

    with pytest.raises(ContactReferenceError, match="blinded with the detector hidden"):
        validate(record)


def test_different_annotator_basis_needs_distinct_annotators():
    """Without this, one annotator completes a record by declaring the basis and waiting
    for nothing: the separation requirement becomes opt-out."""
    record = _record()
    _complete_with_repeat(
        record, annotator="annotator-a", completed_at="2026-09-20T10:05:00Z",
        independence_basis="different-annotator",
    )

    with pytest.raises(ContactReferenceError, match="distinct annotators"):
        validate(record)


def test_a_repeat_recorded_before_the_first_pass_is_not_a_repeat():
    """The passes here are far enough apart; what is wrong is which one is called the repeat."""
    record = _record()
    _complete_with_repeat(record, completed_at="2026-09-18T10:00:00Z")

    with pytest.raises(ContactReferenceError, match="predates"):
        validate(record)


def test_independent_completion_problems_are_reported_together():
    """validate() documents listing every problem; an annotator fixing a record should not
    discover the next one only after fixing the last."""
    record = _record()
    _complete_with_repeat(record)
    record["passes"][1]["presentation_order"] = "sequential"
    record["agreement_pair"]["independence_basis"] = "vibes"

    with pytest.raises(ContactReferenceError) as caught:
        validate(record)

    assert "randomized order" in str(caught.value)
    assert "independence_basis" in str(caught.value)


@pytest.mark.parametrize("limits", [None, [], ["that the sweep found every contact"]])
def test_a_record_cannot_be_read_as_timebase_validated(limits):
    """Labels are the committed evidence; the annotation bundle is disposable. The limitation
    has to travel with the labels, or they read as validated against a timebase nobody
    checked."""
    record = _record()
    if limits is None:
        del record["does_not_validate"]
    else:
        record["does_not_validate"] = limits

    with pytest.raises(ContactReferenceError, match="does_not_validate"):
        validate(record)
