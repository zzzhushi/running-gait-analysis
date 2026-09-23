"""The viewer must pair saved pose points with the correct source frame or refuse."""

import copy
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from gaitlab.core.schema import PoseSequence
from gaitlab.debug.landmark_references import RULE, SCHEMA, validate
from scripts import review_pose_landmarks as review
from scripts.overstride_render import SourceFrames

DATA = Path(__file__).resolve().parent / "data"
VIDEO = DATA / "female_high_cadence.mp4"
RTMPOSE = DATA / "female_high_cadence.pose.rtmpose.json"
BLAZEPOSE = DATA / "female_high_cadence.pose.blazepose.json"
ASSETS = DATA.parent.parent / "docs" / "validation" / "assets"
EXAMPLE_FRAMES = [1401, 1408, 1415]


@pytest.mark.skipif(not shutil.which("ffprobe") or not shutil.which("ffmpeg"),
                    reason="ffmpeg and ffprobe are required for exact-frame review")
def test_committed_review_images_are_current(tmp_path):
    generated = review.build_review(
        VIDEO, {"RTMPose": RTMPOSE, "Python BlazePose": BLAZEPOSE},
        EXAMPLE_FRAMES, tmp_path,
    )
    for fresh in generated:
        with Image.open(fresh) as actual, Image.open(ASSETS / fresh.name) as expected:
            assert actual.size == expected.size
            assert actual.mode == expected.mode
            assert actual.info == expected.info
            # Fonts and video decoders may differ slightly across CI hosts.
            diff = ImageChops.difference(expected, actual)
            assert max(ImageStat.Stat(diff).mean) <= 1.0
            assert sum(diff.convert("L").histogram()[21:]) <= expected.width * expected.height * 0.005


@pytest.mark.skipif(not shutil.which("ffprobe") or not shutil.which("ffmpeg"),
                    reason="ffmpeg and ffprobe are required for exact-frame review")
def test_source_only_export_contains_exact_decoded_pixels_and_no_pose(tmp_path):
    sources = review.build_source_only(VIDEO, EXAMPLE_FRAMES, tmp_path)
    assert len(sources) == 3
    for index, path in zip(EXAMPLE_FRAMES, sources):
        with Image.open(path) as actual:
            assert actual.size == (720, 1280)
            assert actual.info["gaitlab.frame_index"] == str(index)
            assert actual.info["gaitlab.video_sha256"] == review.sha256(VIDEO)
            assert actual.info["gaitlab.model_layers_visible"] == "false"
            assert not any("pose" in key for key in actual.info)
            expected = SourceFrames(VIDEO, actual.size)(index)
            assert ImageChops.difference(expected, actual).getbbox() is None
            with Image.open(ASSETS / path.name) as committed:
                assert committed.size == actual.size
                assert committed.info == actual.info
                diff = ImageChops.difference(committed, actual)
                assert max(ImageStat.Stat(diff).mean) <= 1.0
                assert sum(diff.convert("L").histogram()[21:]) <= actual.width * actual.height * 0.005


@pytest.mark.skipif(not shutil.which("ffprobe") or not shutil.which("ffmpeg"),
                    reason="ffmpeg and ffprobe are required for exact-frame review")
def test_review_image_uses_the_same_frame_for_both_extractors(tmp_path):
    images = review.build_review(
        VIDEO, {"RTMPose": RTMPOSE, "Python BlazePose": BLAZEPOSE}, [1408], tmp_path,
    )
    assert len(images) == 1
    with Image.open(images[0]) as image:
        assert image.width == 3 * review.PANEL_WIDTH  # raw, RTMPose, BlazePose
        assert image.info["gaitlab.frame_index"] == "1408"
        assert image.info["gaitlab.video_pts_s"] == "11.741667"
        assert image.info["gaitlab.video_sha256"] == review.sha256(VIDEO)
        assert json.loads(image.info["gaitlab.pose_sha256"]) == {
            "RTMPose": review.sha256(RTMPOSE),
            "Python BlazePose": review.sha256(BLAZEPOSE),
        }
        width = review.PANEL_WIDTH
        raw = image.crop((0, 0, width, image.height))
        rtmpose = image.crop((width, 0, 2 * width, image.height))
        blazepose = image.crop((2 * width, 0, 3 * width, image.height))
        # The panels have identical source pixels, then separate model layers.
        raw = raw.crop((0, review.HEADER_HEIGHT, width, image.height))
        rtmpose = rtmpose.crop((0, review.HEADER_HEIGHT, width, image.height))
        blazepose = blazepose.crop((0, review.HEADER_HEIGHT, width, image.height))
        decoded = SourceFrames(VIDEO, (720, 1280))(1408)
        expected = decoded.crop((0, round(decoded.height * 0.43), 720, 1280))
        expected = expected.resize(raw.size, Image.Resampling.LANCZOS)
        assert ImageChops.difference(raw, expected).getbbox() is None
        assert ImageChops.difference(raw, rtmpose).getbbox() is not None
        assert ImageChops.difference(raw, blazepose).getbbox() is not None


def test_dropped_or_shifted_frames_are_refused():
    seq = PoseSequence.from_pose_dict(json.loads(RTMPOSE.read_text())).validate()
    pts = list(seq.timestamps)
    review.check_alignment(seq, pts, (seq.width, seq.height), name="RTMPose")
    with pytest.raises(ValueError, match="one timestamped frame"):
        review.check_alignment(seq, pts[:-1], (seq.width, seq.height), name="browser")
    shifted = copy.deepcopy(seq)
    shifted.timestamps = [t + 2 / 120 for t in pts]
    with pytest.raises(ValueError, match="frame 0"):
        review.check_alignment(shifted, pts, (seq.width, seq.height), name="browser")


def test_rear_view_is_not_presented_as_overstride_validation():
    seq = PoseSequence.from_pose_dict(json.loads(RTMPOSE.read_text())).validate()
    seq.view = "rear"
    with pytest.raises(ValueError, match="side-only"):
        review.check_alignment(seq, list(seq.timestamps), (seq.width, seq.height), name="rear")


def _reference_record():
    return {
        "schema": SCHEMA, "rule": RULE, "view": "side-right",
        "clip": "female_high_cadence", "video_sha256": "a" * 64,
        "frame_count": 3, "image_size": [720, 1280],
        "annotator": "reviewer-1", "model_layers_visible": False,
        "prior_pose_exposure": False,
        "observations": [{
            "frame_index": 1, "video_pts_s": 0.008333,
            "track": "near_leg", "side": None, "landmark": "heel",
            "basis": "visible_shoe", "xy": [320.0, 1120.0],
            "uncertainty_radius_px": 4.0,
        }, {
            "frame_index": 1, "video_pts_s": 0.008333,
            "track": "far_leg", "side": None, "landmark": "hip",
            "basis": "unlabelable", "xy": None,
            "uncertainty_radius_px": None, "reason": "hidden by the near leg",
        }],
    }


def _validate(record):
    return validate(record, video_sha256="a" * 64,
                    pts=[0.0, 0.008333, 0.016667], image_size=(720, 1280))


def test_reference_record_is_video_only_and_carries_uncertainty():
    record = _reference_record()
    assert "pose_sha256" not in record
    assert _validate(record) is record


@pytest.mark.parametrize("change,match", [
    (lambda r: r.update(video_sha256="b" * 64), "different video"),
    (lambda r: r.update(view="rear"), "side view"),
    (lambda r: r.update(clip=""), "clip is required"),
    (lambda r: r.update(model_layers_visible=True), "without model layers"),
    (lambda r: r.pop("prior_pose_exposure"), "prior_pose_exposure"),
    (lambda r: r["observations"][0].update(video_pts_s=0.05), "decoded frame"),
    (lambda r: r["observations"][0].update(basis="visible_body"), "hidden by shoes"),
    (lambda r: r["observations"][0].update(uncertainty_radius_px=0), "uncertainty radius"),
    (lambda r: r["observations"][1].update(xy=[10, 10]), "must not carry a point"),
    (lambda r: r["observations"][0].pop("side"), "anatomical side"),
])
def test_reference_record_refuses_false_precision(change, match):
    record = copy.deepcopy(_reference_record())
    change(record)
    with pytest.raises(ValueError, match=match):
        _validate(record)
