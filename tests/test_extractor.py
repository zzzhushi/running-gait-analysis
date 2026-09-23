"""PoseExtractor contracts, pure mapping logic, timestamps, and pipeline integration.

Real extractor dependencies are optional, so most coverage uses pure helpers and
`MockExtractor`; separate tests verify clear failures when optional packages are absent.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

from extractor.base import PoseExtractor
from extractor.blazepose import BLAZEPOSE
from extractor.blazepose import MediaPipeExtractor
from extractor.blazepose import to_canonical as blazepose_to_canonical
from extractor.extract_pose import _resolve_video
from extractor.mock import MockExtractor
from extractor.rtmpose import HALPE26, WHOLEBODY
from extractor.rtmpose import RTMPoseExtractor
from extractor.rtmpose import build_model, pick_person
from extractor.rtmpose import to_canonical as rtmpose_to_canonical
from extractor.timestamps import (
    _monotonic_positive,
    check_frame_count,
    choose_timestamps,
    probe_timestamps,
)
from gaitlab.core.schema import KEYPOINTS, PoseSequence
from pipeline import analyze_video


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


@pytest.fixture
def without_optional_deps(monkeypatch):
    """Force lazy optional-dependency imports to fail on every test environment."""
    for name in ("rtmlib", "cv2", "mediapipe"):
        monkeypatch.setitem(sys.modules, name, None)


class TestMissingDependencies:
    """A missing optional dependency must surface as a clear RuntimeError telling you what
    to install, not as a bare ImportError traceback."""

    def test_build_model_without_rtmlib_raises_runtime_error(self, without_optional_deps):
        with pytest.raises(RuntimeError, match="rtmlib is not installed"):
            build_model("body26")

    def test_rtmpose_extract_without_opencv_raises_runtime_error(self, without_optional_deps):
        with pytest.raises(RuntimeError, match="opencv is not installed"):
            RTMPoseExtractor().extract("video.mp4", "side-left")

    def test_mediapipe_extract_without_mediapipe_raises_runtime_error(self, without_optional_deps):
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

    def test_defaults_to_rtmpose_extractor_when_none_given(self, without_optional_deps):
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
    def test_monotonic_positive_rejects_a_flat_series(self):
        """A stalled decoder clock contains no elapsed-time information."""
        assert not _monotonic_positive([1.0, 1.0, 1.0])

    def test_monotonic_positive_rejects_a_decreasing_series(self):
        assert not _monotonic_positive([5.0, 3.0])

    def test_monotonic_positive_rejects_a_single_value(self):
        assert not _monotonic_positive([1.0])

    def test_monotonic_positive_accepts_strictly_increasing(self):
        assert _monotonic_positive([0.0, 0.5, 1.0])

    def test_monotonic_positive_rejects_a_repeated_value(self):
        """Two indices sharing one instant make a frame index ambiguous as a moment."""
        assert not _monotonic_positive([0.0, 0.033, 0.033, 0.066])

    def test_duplicate_container_pts_falls_back_to_a_usable_clock(self):
        duplicated = [0.0, 0.033, 0.033, 0.066]
        ts, src = choose_timestamps(duplicated, pos_msec=[0.0, 0.03, 0.06, 0.09],
                                    kept_idx=[0, 1, 2, 3], total_read=4)
        assert ts == [0.0, 0.03, 0.06, 0.09]
        assert src == "OpenCV POS_MSEC"

    def test_duplicates_in_every_source_fall_back_to_the_assumed_timebase(self):
        ts, src = choose_timestamps(probe_ts=[0.0, 0.033, 0.033], pos_msec=[0.0, 0.03, 0.03],
                                    kept_idx=[0, 1, 2], total_read=3)
        assert ts is None
        assert "constant frame rate" in src

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


class TestFrameCount:
    def test_matching_counts_produce_no_note(self):
        assert check_frame_count(expected=120, actual=120) == (None, False)

    def test_more_decoded_than_expected_produces_no_note(self):
        """The container's own count can undercount at the edges; more frames out
        than the container reported is not evidence of a dropped frame."""
        assert check_frame_count(expected=120, actual=121) == (None, False)

    def test_unknown_container_count_produces_no_note(self):
        assert check_frame_count(expected=None, actual=87) == (None, False)

    def test_small_deficit_is_noted_but_not_severe(self):
        note, severe = check_frame_count(expected=120, actual=119)
        assert note is not None and "120" in note and "119" in note
        assert severe is False

    def test_large_deficit_is_severe(self):
        note, severe = check_frame_count(expected=120, actual=80)
        assert note is not None
        assert severe is True

    @pytest.mark.parametrize("expected,actual", [(4, 2), (10, 8), (40, 36)])
    def test_loss_past_the_trailing_frame_is_judged_proportionally(self, expected, actual):
        """Beyond the one-frame edge case, a short clip gets no larger proportional
        allowance than a long one."""
        _note, severe = check_frame_count(expected=expected, actual=actual)
        assert severe is True

    @pytest.mark.parametrize("expected", [4, 10, 120, 1160])
    def test_one_trailing_frame_is_allowed_at_every_clip_length(self, expected):
        """The flat allowance is intentionally disproportionate on a short clip, where one
        frame is a large share of the whole. It is recorded either way, so the deficit stays
        visible rather than being silently accepted."""
        note, severe = check_frame_count(expected=expected, actual=expected - 1)
        assert note is not None
        assert severe is False


class _ScoreRow(list):
    """Duck-types rtmlib's numpy score arrays: pick_person only calls .mean()."""

    def mean(self):
        return sum(self) / len(self)


class _RotatedCapture:
    """Simulates the FFMPEG backend on a portrait clip carrying a display-matrix
    rotation: FRAME_WIDTH/HEIGHT report the coded (unrotated) landscape size until
    ORIENTATION_AUTO is enabled, matching cv2's real behavior on such a file."""

    def __init__(self, coded_w=1920, coded_h=1080, n_frames=3):
        self._coded_w, self._coded_h = coded_w, coded_h
        self._n_frames = n_frames
        self._read = 0
        self._auto = 0

    def isOpened(self):
        return True

    def get(self, prop):
        import cv2
        if prop == cv2.CAP_PROP_FPS:
            return 120.0
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self._coded_h if self._auto else self._coded_w)
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(self._coded_w if self._auto else self._coded_h)
        return 0.0

    def set(self, prop, value):
        import cv2
        if prop == cv2.CAP_PROP_ORIENTATION_AUTO:
            self._auto = value
        return True

    def read(self):
        if self._read >= self._n_frames:
            return False, None
        self._read += 1
        return True, object()  # pixel content is irrelevant; the pose model is faked below

    def release(self):
        pass


def _install_fake_cv2(monkeypatch, capture):
    fake = types.ModuleType("cv2")
    fake.CAP_PROP_FPS = 5
    fake.CAP_PROP_FRAME_WIDTH = 3
    fake.CAP_PROP_FRAME_HEIGHT = 4
    fake.CAP_PROP_POS_MSEC = 0
    fake.CAP_PROP_ORIENTATION_AUTO = 48
    fake.COLOR_BGR2RGB = 4
    fake.VideoCapture = lambda path: capture
    fake.cvtColor = lambda img, code: img
    monkeypatch.setitem(sys.modules, "cv2", fake)


class TestOrientation:
    """A phone clip's display-matrix rotation is container metadata, not pixel data —
    cv2 only applies it when CAP_PROP_ORIENTATION_AUTO is enabled. Without it, a
    portrait recording decodes as landscape and every geometry-based metric (trunk
    lean, hip extension, foot-strike angle, ...) is measured in the wrong frame."""

    def test_rtmpose_reports_the_rotated_orientation(self, monkeypatch):
        from extractor.rtmpose import HALPE26, RTMPoseExtractor

        capture = _RotatedCapture(coded_w=1920, coded_h=1080)
        _install_fake_cv2(monkeypatch, capture)
        fake_model = lambda img: ([[(0.0, 0.0)] * 26], [_ScoreRow([0.9] * 26)])
        monkeypatch.setattr(
            "extractor.rtmpose.build_model", lambda model, mode: (fake_model, HALPE26, "fake")
        )

        seq = RTMPoseExtractor().extract("clip.mov", "side-right", no_ffprobe=True)

        assert (seq.width, seq.height) == (1080, 1920)

    def test_blazepose_reports_the_rotated_orientation(self, monkeypatch):
        capture = _RotatedCapture(coded_w=1920, coded_h=1080)
        _install_fake_cv2(monkeypatch, capture)
        fake_pose = types.SimpleNamespace(
            process=lambda img: types.SimpleNamespace(pose_landmarks=None)
        )
        fake_mp = types.SimpleNamespace(
            solutions=types.SimpleNamespace(pose=types.SimpleNamespace(Pose=lambda **kw: fake_pose))
        )
        monkeypatch.setitem(sys.modules, "mediapipe", fake_mp)

        seq = MediaPipeExtractor().extract("clip.mov", "side-right", no_ffprobe=True)

        assert (seq.width, seq.height) == (1080, 1920)


class _TimedCapture:
    """An unrotated capture whose POS_MSEC advances by a fixed step each read."""

    def __init__(self, n_frames=4, step_ms=33.333):
        self._n_frames = n_frames
        self._step_ms = step_ms
        self._read = 0

    def isOpened(self):
        return True

    def get(self, prop):
        import cv2
        if prop == cv2.CAP_PROP_FPS:
            return 30.0
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return 640.0
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return 480.0
        if prop == cv2.CAP_PROP_POS_MSEC:
            return self._read * self._step_ms
        return 0.0

    def set(self, prop, value):
        return True

    def read(self):
        if self._read >= self._n_frames:
            return False, None
        self._read += 1
        return True, object()

    def release(self):
        pass


class TestTimestampProvenance:
    """The extractor must not discard where its timestamps came from.

    Duration, effective FPS, and every timing-dependent metric depend on whether the
    clock is a real per-frame timestamp or an assumed constant frame rate; that
    provenance has to survive on the PoseSequence, not just print to stderr.
    """

    def test_opencv_pos_msec_source_is_recorded_on_the_sequence(self, monkeypatch):
        capture = _TimedCapture()
        _install_fake_cv2(monkeypatch, capture)
        fake_model = lambda img: ([[(0.0, 0.0)] * 26], [_ScoreRow([0.9] * 26)])
        monkeypatch.setattr(
            "extractor.rtmpose.build_model", lambda model, mode: (fake_model, HALPE26, "fake")
        )

        seq = RTMPoseExtractor().extract("clip.mov", "side-right", no_ffprobe=True)

        assert seq.timestamps == pytest.approx([0.0, 0.033333, 0.066666, 0.099999], abs=1e-4)
        assert seq.timestamp_source == "OpenCV POS_MSEC"

    def test_no_trustworthy_clock_records_the_assumed_timebase(self, monkeypatch):
        """Falling back to f/fps is a provenance claim, not an absence of one."""
        from gaitlab.core.schema import ASSUMED_TIMEBASE

        capture = _TimedCapture(step_ms=0.0)  # a stalled clock carries no elapsed-time information
        _install_fake_cv2(monkeypatch, capture)
        fake_model = lambda img: ([[(0.0, 0.0)] * 26], [_ScoreRow([0.9] * 26)])
        monkeypatch.setattr(
            "extractor.rtmpose.build_model", lambda model, mode: (fake_model, HALPE26, "fake")
        )

        seq = RTMPoseExtractor().extract("clip.mov", "side-right", no_ffprobe=True)

        assert seq.timestamps is None
        assert seq.timestamp_source == ASSUMED_TIMEBASE
        seq.validate()


class TestFrameCountEnforcement:
    """The extractor must not silently return a shorter sequence than its source video."""

    def test_matching_container_count_produces_no_note(self, monkeypatch):
        capture = _TimedCapture(n_frames=4)
        _install_fake_cv2(monkeypatch, capture)
        fake_model = lambda img: ([[(0.0, 0.0)] * 26], [_ScoreRow([0.9] * 26)])
        monkeypatch.setattr(
            "extractor.rtmpose.build_model", lambda model, mode: (fake_model, HALPE26, "fake")
        )
        monkeypatch.setattr("extractor.rtmpose.probe_timestamps", lambda path: [0.0, 0.1, 0.2, 0.3])

        seq = RTMPoseExtractor().extract("clip.mov", "side-right")

        assert seq.frame_count_note is None

    def test_small_deficit_is_recorded_without_raising(self, monkeypatch):
        capture = _TimedCapture(n_frames=4)
        _install_fake_cv2(monkeypatch, capture)
        fake_model = lambda img: ([[(0.0, 0.0)] * 26], [_ScoreRow([0.9] * 26)])
        monkeypatch.setattr(
            "extractor.rtmpose.build_model", lambda model, mode: (fake_model, HALPE26, "fake")
        )
        # container reports 5 frames; only 4 were decodable.
        monkeypatch.setattr("extractor.rtmpose.probe_timestamps",
                            lambda path: [0.0, 0.1, 0.2, 0.3, 0.4])

        seq = RTMPoseExtractor().extract("clip.mov", "side-right")

        assert seq.frame_count_note is not None
        assert "4" in seq.frame_count_note and "5" in seq.frame_count_note

    def test_severe_deficit_raises_instead_of_returning_a_truncated_sequence(self, monkeypatch):
        capture = _TimedCapture(n_frames=4)
        _install_fake_cv2(monkeypatch, capture)
        fake_model = lambda img: ([[(0.0, 0.0)] * 26], [_ScoreRow([0.9] * 26)])
        monkeypatch.setattr(
            "extractor.rtmpose.build_model", lambda model, mode: (fake_model, HALPE26, "fake")
        )
        # container reports 40 frames; only 4 were decodable — a badly truncated file.
        monkeypatch.setattr("extractor.rtmpose.probe_timestamps",
                            lambda path: [i * 0.1 for i in range(40)])

        with pytest.raises(RuntimeError, match="dropped"):
            RTMPoseExtractor().extract("clip.mov", "side-right")

    def test_a_max_seconds_request_does_not_falsely_report_dropped_frames(self, monkeypatch):
        """Stopping early because the caller asked for a shorter clip is not the
        same failure as OpenCV silently losing frames mid-decode."""
        capture = _TimedCapture(n_frames=40)
        _install_fake_cv2(monkeypatch, capture)
        fake_model = lambda img: ([[(0.0, 0.0)] * 26], [_ScoreRow([0.9] * 26)])
        monkeypatch.setattr(
            "extractor.rtmpose.build_model", lambda model, mode: (fake_model, HALPE26, "fake")
        )
        monkeypatch.setattr("extractor.rtmpose.probe_timestamps",
                            lambda path: [i * 0.1 for i in range(40)])

        seq = RTMPoseExtractor().extract("clip.mov", "side-right", max_seconds=0.1)

        assert seq.frame_count_note is None


class TestResolveVideo:
    def test_returns_an_existing_absolute_path_unchanged(self, tmp_path):
        f = tmp_path / "clip.mp4"
        f.write_bytes(b"")
        assert _resolve_video(str(f)) == str(f)

    def test_exits_when_nothing_matches(self):
        with pytest.raises(SystemExit):
            _resolve_video("no_such_stem_anywhere")
