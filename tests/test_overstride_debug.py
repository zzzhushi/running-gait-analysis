"""Record-to-artifact alignment for the overstride diagnostic slice.

These tests intentionally force contact. They validate provenance, selection, and rendering;
they do not claim that the detector would choose the right frame on real footage.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from gaitlab.core.events import GaitEvents
from gaitlab.core.schema import PoseSequence
from gaitlab.debug.overstride import build_overstride_debug_record, record_by_id
from scripts import export_overstride_debug
from scripts.overstride_render import (
    SourceFrames,
    find_row,
    render_annotated_frame,
    render_plan,
    save_annotated_frame,
    save_grid,
    trace_rows,
    write_strike_table,
)
from tests.reach_fixture import load_authored_reach_fixture


@pytest.fixture(scope="module")
def debug_bundle():
    case = load_authored_reach_fixture()
    annotations = {
        "references": [{
            "side": "l",
            "frame_index": 1,
            "contact_interval_frames": [1, 2],
            "landmarks": {"ankle": [321.0, 601.0]},
            "provenance": "hand/reference-a",
        }],
        "adjustments": [{
            "side": "l",
            "original_frame_index": 1,
            "adjusted_frame_index": 2,
            "adjusted_timestamp_s": case.sequence.time_at(2),
            "provenance": "user/session-a",
        }],
    }
    return build_overstride_debug_record(
        case.sequence,
        GaitEvents(strikes=case.forced_strikes),
        source_id=case.name,
        annotations=annotations,
        denominator=case.denominator,
        facing=case.facing,
    )


def test_record_captures_the_complete_canonical_path(debug_bundle):
    bundle = debug_bundle
    row = find_row(bundle, "l", 1)

    assert bundle["schema"] == "gaitlab.overstride-debug/v1"
    assert len(bundle["frames"]) == bundle["source"]["frame_count"] * 2
    assert row["source_frame"] == {
        "identifier": "overstride_stage3#decoded-frame=1",
        "decoded_index": 1,
        "timestamp_s": pytest.approx(0.016667),
        "effective_fps": pytest.approx(60.000600006),
    }
    assert row["measurement_landmarks"]["hip"] == {
        "x": 300.0, "y": 500.0, "confidence": 0.99, "provenance": "pose"
    }
    assert row["measurement_landmarks"]["ankle"]["x"] == 320.0
    assert row["measurement_landmarks"]["foot_midpoint_proxy"] == {
        "x": 320.0,
        "y": 605.0,
        "confidence": 0.95,
        "provenance": "arithmetic mean of pose heel and big-toe coordinates",
    }
    assert row["reach"]["ankle"] == {
        "px": 20.0, "pct_leg": 20.0,
        "px_unavailable": None, "pct_unavailable": None,
    }
    assert row["inclination"]["degrees_from_vertical"] == pytest.approx(11.309932)
    assert row["contact"]["detected"] is True
    assert row["contact"]["original_frame_index"] == 1
    assert row["contact"]["adjusted_frame_index"] == 2
    assert row["references"][0]["provenance"] == "hand/reference-a"
    assert row["validity"] == {"usable": True, "reasons": []}

    report = bundle["measurement"]["production_report"]
    assert report["value"] == pytest.approx(20.0)
    assert report["per_side"] == {"l": pytest.approx(20.0), "r": None}
    assert report["contact_record_ids"] == [row["record_id"]]
    assert bundle["does_not_validate"]
    json.dumps(bundle, allow_nan=False)  # machine-readable JSON, not JavaScript NaN tokens


def test_natural_denominator_keeps_every_contributing_point():
    case = load_authored_reach_fixture()
    bundle = build_overstride_debug_record(
        case.sequence,
        GaitEvents(strikes=case.forced_strikes),
        source_id=case.name,
    )
    denominator = bundle["measurement"]["denominator"]
    assert denominator["samples"]
    sample = denominator["samples"][0]
    assert set(sample["points"]) == {"hip", "knee", "ankle"}
    assert sample["segments_px"]["total"] == pytest.approx(
        sample["segments_px"]["thigh"] + sample["segments_px"]["shank"]
    )


def test_table_plan_png_and_report_share_one_record_and_value(debug_bundle, tmp_path):
    row = find_row(debug_bundle, "l", 1)
    table = tmp_path / "strikes.csv"
    write_strike_table(debug_bundle, table)
    with table.open(newline="") as handle:
        csv_row = next(csv.DictReader(handle))

    background = Image.new("RGB", (640, 720), (19, 43, 67))
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    plan = save_annotated_frame(debug_bundle, row, background, first)
    save_annotated_frame(debug_bundle, row, background, second)
    with Image.open(first) as image:
        metadata = dict(image.info)

    report = debug_bundle["measurement"]["production_report"]
    assert csv_row["record_id"] == plan["record_id"] == metadata["gaitlab.record_id"]
    assert float(csv_row["reach_pct_leg"]) == plan["reach_pct_leg"] == report["value"]
    assert json.loads(metadata["gaitlab.reach_pct_leg"]) == report["value"]
    assert metadata["gaitlab.source_frame"] == row["source_frame"]["identifier"]
    assert first.read_bytes() == second.read_bytes(), "same record must regenerate identically"


def test_pose_reference_original_and_adjusted_contacts_remain_distinct(debug_bundle):
    original = find_row(debug_bundle, "l", 1)
    adjusted = find_row(debug_bundle, "l", 2)
    original_plan = render_plan(debug_bundle, original)
    adjusted_plan = render_plan(debug_bundle, adjusted)

    assert original_plan["detected_contact"] is True
    assert original_plan["references"][0]["landmarks"]["ankle"] == [321.0, 601.0]
    assert original_plan["measurement_landmarks"]["ankle"]["provenance"] == "pose"
    assert adjusted_plan["detected_contact"] is False
    assert adjusted_plan["adjusted_contact"] is True


def test_detector_marker_can_be_hidden_without_hiding_the_measurement(debug_bundle):
    row = find_row(debug_bundle, "l", 1)
    background = Image.new("RGB", (640, 720), (19, 43, 67))
    visible, visible_plan = render_annotated_frame(debug_bundle, row, background)
    hidden, hidden_plan = render_annotated_frame(
        debug_bundle, row, background, show_detector=False
    )

    assert visible_plan["detected_contact"] is True
    assert hidden_plan["detected_contact"] is False
    assert hidden_plan["reach_pct_leg"] == visible_plan["reach_pct_leg"] == 20.0
    assert visible.getpixel((10, 10)) != background.getpixel((10, 10))
    assert hidden.getpixel((10, 10)) == background.getpixel((10, 10))


def test_strip_center_can_be_any_frame_not_only_a_detector_neighborhood(debug_bundle):
    center = find_row(debug_bundle, "l", 2)  # not the forced contact at frame 1
    rows = trace_rows(debug_bundle, center, radius=1)
    assert [row["source_frame"]["decoded_index"] for row in rows] == [1, 2]
    assert center["contact"]["detected"] is False


def test_indexed_source_decode_and_overlay_use_the_same_frame(debug_bundle, tmp_path):
    clip = tmp_path / "diagnostic.gif"
    colors = [(220, 20, 60), (20, 180, 90), (40, 80, 220)]
    frames = [Image.new("RGB", (640, 720), color) for color in colors]
    frames[0].save(clip, save_all=True, append_images=frames[1:], duration=17, loop=0,
                   optimize=False)
    source = SourceFrames(clip, (640, 720))
    row = find_row(debug_bundle, "l", 1)
    image, plan = render_annotated_frame(debug_bundle, row, source(1))

    assert plan["decoded_index"] == 1
    # An untouched corner carries frame 1's unique green background, proving the requested
    # record did not receive frame 0 or 2. The detector triangle occupies the opposite corner.
    assert image.getpixel((639, 719)) == colors[1]


def test_dimension_mismatch_is_refused_instead_of_scaled_into_alignment(debug_bundle):
    row = find_row(debug_bundle, "l", 1)
    with pytest.raises(ValueError, match="silently misaligned"):
        render_annotated_frame(debug_bundle, row, Image.new("RGB", (320, 360)))


def test_contact_sheet_metadata_names_every_rendered_record(debug_bundle, tmp_path):
    ids = debug_bundle["measurement"]["production_report"]["contact_record_ids"]
    rows = record_by_id(debug_bundle)
    rendered = []
    for record_id in ids:
        image, plan = render_annotated_frame(
            debug_bundle, rows[record_id], Image.new("RGB", (640, 720), "#123456")
        )
        rendered.append((image, plan))
    path = tmp_path / "contact-sheet.png"
    save_grid(rendered, path, columns=4, artifact="contact-sheet")

    with Image.open(path) as image:
        assert image.info["gaitlab.artifact"] == "contact-sheet"
        assert json.loads(image.info["gaitlab.record_ids"]) == ids


def test_committed_nine_frame_sequence_uses_neutral_names_and_canonical_endpoints():
    assets = Path(__file__).resolve().parents[1] / "docs" / "validation" / "assets"
    bundle = json.loads((assets / "overstride-debug-sequence.record.json").read_text())
    sequence = bundle["diagnostic_sequence"]
    rows = record_by_id(bundle)

    assert len(sequence["frame_record_ids"]) == 9
    assert all("good" not in name and "bad" not in name for name in sequence["names"])
    reaches = [rows[record_id]["reach"]["ankle"]["pct_leg"]
               for record_id in sequence["frame_record_ids"]]
    assert reaches[0] == pytest.approx(0.0)
    assert reaches[-1] == pytest.approx(20.0)
    assert reaches == sorted(reaches)
    assert (assets / "overstride-debug-sequence.source.gif").is_file()
    assert (assets / "overstride-debug-sequence.gif").is_file()
    assert (assets / "overstride-debug-sequence.png").is_file()


def test_committed_sequence_is_reproducible_from_the_current_code():
    """Checking a few of the record's fields cannot notice a changed record shape.

    Without this, adding a field to the builder leaves the committed artifacts describing a
    format the code no longer produces, and every other test here still passes. PNG pixels,
    dimensions and metadata are exact; its host-dependent compression bytes are not evidence.
    """
    from scripts.gen_overstride_debug_sequence import stale_artifacts

    assert not stale_artifacts()


def test_png_staleness_compares_visual_evidence_not_host_compression(tmp_path, monkeypatch):
    """A zlib byte difference is harmless; a pixel or traceability change is stale."""
    from scripts import gen_overstride_debug_sequence as generator

    assets = tmp_path / "assets"
    assets.mkdir()
    generator.write_artifacts(assets)
    monkeypatch.setattr(generator, "ASSETS", assets)
    path = assets / "overstride-debug-sequence.png"
    original_bytes = path.read_bytes()

    with Image.open(path) as source:
        image = source.copy()
        metadata = dict(source.info)
    pnginfo = PngImagePlugin.PngInfo()
    for key, value in metadata.items():
        pnginfo.add_text(key, value)
    image.save(path, format="PNG", pnginfo=pnginfo, compress_level=0)
    assert path.read_bytes() != original_bytes
    assert generator.stale_artifacts() == []

    image.putpixel((0, 0), (0, 0, 0))
    image.save(path, format="PNG", pnginfo=pnginfo, compress_level=0)
    assert generator.stale_artifacts() == ["overstride-debug-sequence.png"]


def test_committed_sequence_locks_decode_index_and_orientation():
    assets = Path(__file__).resolve().parents[1] / "docs" / "validation" / "assets"
    bundle = json.loads((assets / "overstride-debug-sequence.record.json").read_text())
    source = SourceFrames(assets / "overstride-debug-sequence.source.gif", (640, 720))
    source.preload([6, 2])
    decoded = source(6)

    # _background() gives each source frame a distinct base color away from its grid and text.
    # This is the actual frame-index assertion; the four corner markers below are identical in
    # every frame and specifically establish orientation.
    assert decoded.getpixel((100, 100)) == (49, 50, 60)
    assert decoded.getpixel((5, 5)) == (220, 38, 38)       # top-left red
    assert decoded.getpixel((635, 5)) == (34, 197, 94)     # top-right green
    assert decoded.getpixel((5, 715)) == (234, 179, 8)     # bottom-left yellow
    assert decoded.getpixel((635, 715)) == (37, 99, 235)   # bottom-right blue

    row = find_row(bundle, "l", 6)
    rendered, plan = render_annotated_frame(bundle, row, decoded, show_detector=False)
    assert plan["decoded_index"] == 6
    assert rendered.getpixel((5, 5)) == (220, 38, 38)
    assert rendered.getpixel((635, 5)) == (34, 197, 94)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="renderer video decoding requires ffmpeg")
def test_rotation_tagged_video_aligns_ffmpeg_pixels_and_display_space_pose():
    """The renderer must use the same display rotation as the pose extractor.

    The browser fixture is a lossless 90-degree display-matrix remux of male_side.mp4. The
    source pose belongs to its unrotated 720x1280 pixels, so the expected display transform is
    x'=y, y'=719-x. This tests the renderer's ffmpeg path, not WebCodecs or Pillow GIF decode.
    """
    root = Path(__file__).resolve().parents[1]
    original = json.loads((root / "tests" / "data" / "male_side.pose.blazepose.json").read_text())
    coded_width, coded_height = original["width"], original["height"]
    display = dict(original)
    display["width"], display["height"] = coded_height, coded_width
    display["source"] = "display-rotated browser fixture"
    display["frames"] = [
        [
            [point[1], coded_width - 1 - point[0], point[2]] if point[2] > 0 else list(point)
            for point in frame
        ]
        for frame in original["frames"]
    ]
    sequence = PoseSequence.from_pose_dict(display).validate()
    frame_index = 10
    bundle = build_overstride_debug_record(
        sequence, GaitEvents(), source_id="rotated_male_side.mp4"
    )

    rotated = SourceFrames(root / "tests" / "browser" / "rotated_male_side.mp4", (1280, 720))
    unrotated = SourceFrames(root / "tests" / "data" / "male_side.mp4", (720, 1280))
    rotated.preload([frame_index])
    decoded = rotated(frame_index)

    # An ordinary, non-overlay pixel establishes the actual ffmpeg display transform.
    assert decoded.getpixel((200, 619)) == unrotated(frame_index).getpixel((100, 200))
    row = find_row(bundle, "l", frame_index)
    rendered, plan = render_annotated_frame(bundle, row, decoded, show_detector=False)
    nose = row["pose_landmarks"]["nose"]
    assert plan["decoded_index"] == frame_index
    assert rendered.getpixel((round(nose["x"]), round(nose["y"]))) == (220, 229, 239)


def test_saved_record_refuses_a_same_sized_different_source_video(tmp_path):
    """A filename or dimensions cannot establish that render pixels match the saved record."""
    case = load_authored_reach_fixture()
    pose = tmp_path / "pose.json"
    pose.write_text(json.dumps({
        "fps": case.sequence.fps,
        "width": case.sequence.width,
        "height": case.sequence.height,
        "view": case.sequence.view,
        "frames": case.sequence.frames,
        "keypoint_names": case.sequence.keypoint_names,
        "timestamps": case.sequence.timestamps,
        "source": "authored provenance test",
    }))
    source_a = tmp_path / "source-a.gif"
    source_b = tmp_path / "source-b.gif"
    a_frames = [Image.new("RGB", (640, 720), "#123456") for _ in range(case.sequence.n)]
    b_frames = [Image.new("RGB", (640, 720), "#654321") for _ in range(case.sequence.n)]
    a_frames[0].save(source_a, save_all=True, append_images=a_frames[1:], duration=17, loop=0)
    b_frames[0].save(source_b, save_all=True, append_images=b_frames[1:], duration=17, loop=0)

    initial = tmp_path / "initial"
    assert export_overstride_debug.main([
        "--pose", str(pose), "--video", str(source_a), "--output", str(initial), "--record-only",
    ]) == 0
    record = initial / "debug-record.json"
    saved = json.loads(record.read_text())
    assert saved["source"]["video"]["sha256"]
    assert saved["source"]["pose_input"]["sha256"]

    replay = tmp_path / "replay"
    assert export_overstride_debug.main([
        "--record", str(record), "--video", str(source_a), "--output", str(replay),
    ]) == 0
    assert (replay / "manifest.json").is_file()

    with pytest.raises(SystemExit, match="video bytes do not match"):
        export_overstride_debug.main([
            "--record", str(record), "--video", str(source_b), "--output", str(tmp_path / "wrong"),
        ])
