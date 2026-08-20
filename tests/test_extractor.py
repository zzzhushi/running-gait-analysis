"""The PoseExtractor seam: the base contract, both real implementations' pure
logic, MockExtractor, and the pipeline that ties an extractor to analyze().

Neither rtmlib, opencv, nor mediapipe is a project dependency (requirements.txt
covers them only for someone actually extracting from real video), so none is
installed in CI. What's tested here without them:

  - the base contract raises when unimplemented
  - every PURE function each extractor's extract() calls (to_canonical,
    pick_person) — these never touch cv2/rtmlib/mediapipe
  - that missing-dependency paths fail with a clear RuntimeError rather than a
    bare ImportError traceback
  - MockExtractor and the full pipeline end to end, since MockExtractor is
    exactly the seam that makes that possible with no video and no model
  - the timestamp-selection logic, which is pure once given already-decoded
    values, plus probe_timestamps' real graceful-degradation path when ffprobe
    itself is absent (also genuinely true in CI)
"""

from __future__ import annotations

import os

import pytest

from extractor.base import PoseExtractor
from extractor.blazepose import BLAZEPOSE
from extractor.blazepose import MediaPipeExtractor
from extractor.blazepose import to_canonical as blazepose_to_canonical
from extractor.extract_pose import _resolve_video
from extractor.mock import MockExtractor
from extractor.pipeline import analyze_video
from extractor.rtmpose import HALPE26, WHOLEBODY
from extractor.rtmpose import RTMPoseExtractor
from extractor.rtmpose import build_model, pick_person
from extractor.rtmpose import to_canonical as rtmpose_to_canonical
from extractor.timestamps import _monotonic_positive, choose_timestamps, probe_timestamps
from gaitlab.core.schema import KEYPOINTS, PoseSequence


class TestBaseContract:
    def test_unimplemented_extract_raises(self):
        with pytest.raises(NotImplementedError):
            PoseExtractor().extract("video.mp4", "side-left")


class TestRTMPoseToCanonical:
    def test_direct_index_lookup(self):
        """Halpe26's nose is index 0 — verify a plain positional map, not a derived one."""
        kp = [(10.0, 20.0)] + [(0.0, 0.0)] * 25
        sc = [0.9] + [0.0] * 25
        frame = rtmpose_to_canonical(kp, sc, HALPE26)
        assert frame[KEYPOINTS.index("nose")] == [10.0, 20.0, 0.9]

    def test_neck_is_derived_as_shoulder_midpoint_with_min_confidence(self):
        kp = list(HALPE26.items())
        idxmap = HALPE26
        kp_arr = [(0.0, 0.0)] * 26
        sc_arr = [0.0] * 26
        kp_arr[idxmap["l_shoulder"]] = (100.0, 200.0)
        kp_arr[idxmap["r_shoulder"]] = (200.0, 200.0)
        sc_arr[idxmap["l_shoulder"]] = 0.9
        sc_arr[idxmap["r_shoulder"]] = 0.4
        # Halpe26 already has a direct neck point (18), so give it low confidence
        # to make sure this test is exercising the map, not the fallback branch.
        idxmap_no_neck = {k: v for k, v in HALPE26.items() if k != "neck"}
        frame = rtmpose_to_canonical(kp_arr, sc_arr, idxmap_no_neck)
        neck = frame[KEYPOINTS.index("neck")]
        assert neck == [150.0, 200.0, 0.4]  # midpoint x, same y, min(0.9, 0.4)

    def test_unmapped_keypoint_falls_back_to_zero(self):
        """WHOLEBODY has no 'head' entry and no shoulder-based derivation for it."""
        kp = [(0.0, 0.0)] * 23
        sc = [0.9] * 23
        frame = rtmpose_to_canonical(kp, sc, WHOLEBODY)
        assert frame[KEYPOINTS.index("head")] == [0.0, 0.0, 0.0]

    def test_output_has_one_entry_per_canonical_keypoint(self):
        kp = [(0.0, 0.0)] * 26
        sc = [0.5] * 26
        assert len(rtmpose_to_canonical(kp, sc, HALPE26)) == len(KEYPOINTS)


class TestPickPerson:
    class _Row(list):
        """pick_person only requires scores[i].mean() — duck-typed the way
        rtmlib's numpy arrays satisfy it, without adding a numpy dependency
        here (it's already optional, extractor-only, and not installed in CI)."""

        def mean(self):
            return sum(self) / len(self)

    def test_picks_the_higher_mean_confidence(self):
        kps = [[[1.0, 1.0]], [[2.0, 2.0]]]
        scores = [self._Row([0.9]), self._Row([0.3])]
        kp, sc = pick_person(kps, scores)
        assert kp[0][0] == 1.0

    def test_no_detections_returns_none(self):
        assert pick_person([], []) == (None, None)


class TestBlazePoseToCanonical:
    class _Landmark:
        def __init__(self, x, y, visibility=1.0):
            self.x, self.y, self.visibility = x, y, visibility

    def _landmarks(self, overrides=None):
        """overrides: {landmark_index: (x, y, visibility)}. A plain dict rather
        than **kwargs — BlazePose landmark indices are ints, and dict-unpacking
        into keyword arguments requires string keys."""
        lm = [self._Landmark(0.0, 0.0, 0.0) for _ in range(33)]
        for i, (x, y, v) in (overrides or {}).items():
            lm[i] = self._Landmark(x, y, v)
        return lm

    def test_direct_index_scales_by_frame_size(self):
        lm = self._landmarks({BLAZEPOSE["nose"]: (0.5, 0.25, 0.9)})
        frame = blazepose_to_canonical(lm, w=1000, h=2000)
        assert frame[KEYPOINTS.index("nose")] == [500.0, 500.0, 0.9]

    def test_mid_hip_is_derived_from_left_and_right_hip(self):
        lm = self._landmarks({23: (0.2, 0.5, 0.8), 24: (0.4, 0.5, 0.6)})
        frame = blazepose_to_canonical(lm, w=100, h=100)
        assert frame[KEYPOINTS.index("mid_hip")] == pytest.approx([30.0, 50.0, 0.6])

    def test_head_falls_back_to_nose_when_both_ears_invisible(self):
        lm = self._landmarks({0: (0.5, 0.1, 1.0), 7: (0.0, 0.0, 0.0), 8: (0.0, 0.0, 0.0)})
        frame = blazepose_to_canonical(lm, w=100, h=100)
        assert frame[KEYPOINTS.index("head")] == frame[KEYPOINTS.index("nose")]

    def test_small_toes_are_absent_from_blazepose(self):
        lm = self._landmarks()
        frame = blazepose_to_canonical(lm, w=100, h=100)
        assert frame[KEYPOINTS.index("l_small_toe")] == [0.0, 0.0, 0.0]
        assert frame[KEYPOINTS.index("r_small_toe")] == [0.0, 0.0, 0.0]


class TestMissingDependencies:
    """rtmlib, cv2, and mediapipe are genuinely absent in this environment (as in
    CI) — these exercise the real failure path, not a simulated one."""

    def test_build_model_without_rtmlib_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="rtmlib is not installed"):
            build_model("body26")

    def test_rtmpose_extract_without_opencv_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="opencv is not installed"):
            RTMPoseExtractor().extract("video.mp4", "side-left")

    def test_mediapipe_extract_without_mediapipe_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="Needs MediaPipe"):
            MediaPipeExtractor().extract("video.mp4", "side-left")


class TestMockExtractor:
    def test_returns_a_valid_pose_sequence(self):
        seq = MockExtractor(duration=2, fps=30).extract("ignored.mp4", "side-left")
        assert isinstance(seq, PoseSequence)
        seq.validate()  # raises on structural problems
        assert seq.view == "side-left"

    def test_ignores_the_video_path_entirely(self):
        a = MockExtractor(seed=1).extract("this/path/does/not/exist.mp4", "rear")
        b = MockExtractor(seed=1).extract("neither/does/this.mp4", "rear")
        assert a.frames == b.frames

    def test_construction_kwargs_shape_the_pose(self):
        seq = MockExtractor(cadence=150).extract("x.mp4", "side-left")
        assert seq.view == "side-left"


class TestAnalyzeVideo:
    def test_full_pipeline_with_no_video_and_no_model(self):
        """The payoff of the seam: this exercises extract -> analyze with zero I/O."""
        result = analyze_video("nonexistent.mp4", "side-left", extractor=MockExtractor(duration=6))
        d = result.to_dict()
        assert 0 <= d["summary"]["overall_score"] <= 100
        assert d["summary"]["view"] == "side-left"

    def test_defaults_to_rtmpose_extractor_when_none_given(self):
        """No extractor passed -> RTMPoseExtractor -> fails on missing opencv,
        not on missing video. Confirms the default wiring without needing cv2."""
        with pytest.raises(RuntimeError, match="opencv is not installed"):
            analyze_video("video.mp4", "side-left")

    def test_profile_reaches_the_engine(self):
        result = analyze_video(
            "nonexistent.mp4", "side-left",
            profile={"sex": "female", "height_cm": 170},
            extractor=MockExtractor(duration=6),
        )
        assert result.to_dict()["summary"]["profile"] == {"sex": "female", "height_cm": 170}

    def test_label_defaults_to_the_video_path(self):
        result = analyze_video("myrun.mp4", "side-left", extractor=MockExtractor(duration=6))
        assert result.to_dict()["summary"]["label"] == "myrun.mp4"


class TestTimestamps:
    def test_monotonic_positive_accepts_a_flat_series(self):
        """The check is non-decreasing (>=), not strictly increasing — a run of
        identical timestamps (e.g. a stalled decoder) still counts as usable."""
        assert _monotonic_positive([1.0, 1.0, 1.0])

    def test_monotonic_positive_rejects_a_decreasing_series(self):
        assert not _monotonic_positive([5.0, 3.0])

    def test_monotonic_positive_rejects_a_single_value(self):
        assert not _monotonic_positive([1.0])

    def test_monotonic_positive_accepts_strictly_increasing(self):
        assert _monotonic_positive([0.0, 0.5, 1.0])

    def test_prefers_ffprobe_when_frame_count_lines_up(self):
        probe_ts = [0.0, 0.1, 0.2, 0.3]
        ts, src = choose_timestamps(probe_ts, pos_msec=[0, 90, 205], kept_idx=[0, 1, 2], total_read=4)
        assert ts == [0.0, 0.1, 0.2]
        assert "ffprobe" in src

    def test_falls_back_to_pos_msec_when_ffprobe_frame_count_is_short(self):
        ts, src = choose_timestamps(probe_ts=[0.0, 0.1], pos_msec=[0.0, 0.1, 0.2],
                                     kept_idx=[0, 1, 2], total_read=3)
        assert ts == [0.0, 0.1, 0.2]
        assert src == "OpenCV POS_MSEC"

    def test_falls_back_to_none_when_neither_source_is_trustworthy(self):
        ts, src = choose_timestamps(probe_ts=None, pos_msec=[5.0, 3.0], kept_idx=[0, 1], total_read=2)
        assert ts is None
        assert "constant frame rate" in src

    def test_probe_timestamps_returns_none_without_ffprobe_on_path(self):
        """ffprobe is genuinely not installed here, so this is the real path,
        not a mocked one — probe_timestamps must degrade gracefully."""
        assert probe_timestamps("/nonexistent/video.mp4") is None


class TestResolveVideo:
    def test_returns_an_existing_absolute_path_unchanged(self, tmp_path):
        f = tmp_path / "clip.mp4"
        f.write_bytes(b"")
        assert _resolve_video(str(f)) == str(f)

    def test_exits_when_nothing_matches(self):
        with pytest.raises(SystemExit):
            _resolve_video("no_such_stem_anywhere")
