"""Issue #81: checked-in evidence must reproduce from the committed inputs."""

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from scripts import gen_overstride_timebase_evidence as evidence

ASSETS = Path(__file__).resolve().parents[1] / "docs/validation/assets"


@pytest.mark.skipif(not shutil.which("ffprobe") or not shutil.which("ffmpeg"),
                    reason="local ffprobe/ffmpeg unavailable; required in CI")
def test_committed_timebase_evidence_is_current():
    assert evidence.stale_artifacts(portable_images=True) == []
    report = json.loads((ASSETS / evidence.REPORT).read_text())
    manifest = json.loads(evidence.MANIFEST.read_text())
    assert [clip["id"] for clip in report["clips"]] == [case["id"] for case in manifest["clips"]]
    expected_contexts = {
        "female_high_cadence": list(range(1401, 1416)),
        "male_side": list(range(116, 131)),
    }
    for clip in report["clips"]:
        assert all(clip["checks"].values())
        assert clip["max_pose_pts_delta_s"] <= report["timestamp_tolerance_s"]
        assert clip["stored_timestamp_source"] == "unrecorded (legacy fixture)"
        if clip["anchor_frame"] is not None:
            case = next(item for item in manifest["clips"] if item["id"] == clip["id"])
            seq = evidence.PoseSequence.from_pose_dict(json.loads(
                (evidence.ROOT / clip["pose_input"]["path"]).read_text())).validate()
            footer = evidence.footer_lines(case, seq, clip)
            assert f"decoded frame {clip['anchor_frame']}" in footer[0]
            assert f"video PTS={clip['anchor_container_pts_s']:.6f}s" in footer[1]
            assert "contact/landmarks NOT validated" in footer[2]
            name = f"overstride-timebase-{clip['id']}-frame-{clip['anchor_frame']}.png"
            with Image.open(ASSETS / name) as image:
                assert image.size == (clip["pose_display_width"], clip["pose_display_height"])
                assert image.info["gaitlab.decoded_frame"] == str(clip["anchor_frame"])
                assert image.info["gaitlab.video_sha256"] == clip["video"]["sha256"]
                assert image.info["gaitlab.pose_sha256"] == clip["pose_input"]["sha256"]
        if clip["context_frame_indices"]:
            assert clip["context_frame_indices"] == expected_contexts[clip["id"]]
            with Image.open(ASSETS / f"overstride-timebase-{clip['id']}-context.png") as image:
                assert json.loads(image.info["gaitlab.frame_indices"]) == clip["context_frame_indices"]
                assert image.info["gaitlab.selected_frame"] == str(clip["anchor_frame"])
                assert image.info["gaitlab.video_sha256"] == clip["video"]["sha256"]
                assert image.info["gaitlab.pose_sha256"] == clip["pose_input"]["sha256"]
    assert {clip["id"] for clip in report["clips"] if clip["context_frame_indices"]} == set(expected_contexts)


def test_manifest_anchors_are_fixed_not_detector_selected():
    manifest = json.loads(evidence.MANIFEST.read_text())
    assert {case["id"]: case["anchor_frame"] for case in manifest["clips"]
            if case["anchor_frame"] is not None} == {
                "female_high_cadence": 1408, "female_overstride": 262,
                "male_side": 120}
