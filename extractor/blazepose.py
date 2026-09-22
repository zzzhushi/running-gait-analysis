"""MediaPipe BlazePose extraction — a lighter, install-once alternative to RTMPose.

    pip install mediapipe opencv-python

The filename avoids shadowing the `mediapipe` package. Output uses the same canonical
`PoseSequence` as every other extractor.
"""

from __future__ import annotations

import sys

from gaitlab.core.schema import KEYPOINTS, PoseSequence

from .base import PoseExtractor
from .timestamps import check_frame_count, choose_timestamps, probe_timestamps

# MediaPipe BlazePose 33-landmark indices -> canonical names. BlazePose has no neck /
# pelvis / small-toe, so neck & mid_hip are derived and small toes are left absent.
BLAZEPOSE = {
    "nose": 0,
    "l_shoulder": 11, "r_shoulder": 12, "l_elbow": 13, "r_elbow": 14, "l_wrist": 15, "r_wrist": 16,
    "l_hip": 23, "r_hip": 24, "l_knee": 25, "r_knee": 26, "l_ankle": 27, "r_ankle": 28,
    "l_heel": 29, "r_heel": 30, "l_big_toe": 31, "r_big_toe": 32,
}


def to_canonical(lm, w: int, h: int):
    def P(i):
        return [lm[i].x * w, lm[i].y * h, float(getattr(lm[i], "visibility", 1.0))]

    def mid(a, b):
        return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, min(a[2], b[2])]

    frame = []
    for name in KEYPOINTS:
        if name in BLAZEPOSE:
            frame.append(P(BLAZEPOSE[name]))
        elif name == "neck":
            frame.append(mid(P(11), P(12)))
        elif name == "mid_hip":
            frame.append(mid(P(23), P(24)))
        elif name == "head":
            # BlazePose lacks a crown-of-head point; the ear midpoint is a stable
            # head-region proxy for lateral head sway (RTMPose-Halpe has one directly).
            # Fall back to the nose when neither ear is visible.
            l, r = P(7), P(8)
            frame.append(mid(l, r) if (l[2] > 0.1 or r[2] > 0.1) else P(0))
        else:
            frame.append([0.0, 0.0, 0.0])
    return frame


class MediaPipeExtractor(PoseExtractor):
    def __init__(self, model_complexity: int = 2, min_detection_confidence: float = 0.5):
        self.model_complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence

    def extract(self, video_path: str, view: str, *, every: int = 1,
                max_seconds: float = None, no_ffprobe: bool = False) -> PoseSequence:
        try:
            import cv2
            import mediapipe as mp
        except ImportError:
            raise RuntimeError("Needs MediaPipe. Run:\n  pip install mediapipe opencv-python") from None

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError("could not open video: " + video_path)
        # A phone clip's rotation is container metadata (a display matrix), not pixel
        # data; without this, a portrait recording decodes in its coded landscape
        # orientation and every image-vertical/horizontal metric is measured sideways.
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        pose = mp.solutions.pose.Pose(model_complexity=self.model_complexity,
                                       min_detection_confidence=self.min_detection_confidence)
        print(f"Running MediaPipe BlazePose on {video_path} ({width}x{height} @ {fps:.0f}fps)…",
              file=sys.stderr)

        probe_ts = None if no_ffprobe else probe_timestamps(video_path)

        frames = []
        pos_msec = []
        kept_idx = []
        read_i = 0
        max_frames = int(max_seconds * fps) if max_seconds else None
        stopped_by_request = False
        while True:
            t_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            ok, img = cap.read()
            if not ok:
                break
            if read_i % every == 0:
                res = pose.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                if res.pose_landmarks:
                    frames.append(to_canonical(res.pose_landmarks.landmark, width, height))
                else:
                    frames.append([[0.0, 0.0, 0.0] for _ in KEYPOINTS])
                pos_msec.append(t_msec / 1000.0)
                kept_idx.append(read_i)
                if len(frames) % 15 == 0:
                    print(f"\r  {len(frames)} frames analyzed…", end="", file=sys.stderr)
            read_i += 1
            if max_frames and read_i >= max_frames:
                stopped_by_request = True
                break
        cap.release()

        timestamps, ts_src = choose_timestamps(probe_ts, pos_msec, kept_idx, read_i)
        print(f"\n  timestamp source: {ts_src}", file=sys.stderr)

        # A max_seconds request stopping the loop early is not the container losing
        # frames, so only compare against the full container count when we attempted
        # to decode all of it.
        expected_frames = len(probe_ts) if probe_ts is not None and not stopped_by_request else None
        frame_count_note, frame_count_severe = check_frame_count(expected_frames, read_i)
        if frame_count_note:
            print(f"\n  {frame_count_note}", file=sys.stderr)
        if frame_count_severe:
            raise RuntimeError(f"{frame_count_note}; refusing a silently truncated pose sequence")

        return PoseSequence(
            fps=fps / every, width=width, height=height, view=view, frames=frames,
            source="mediapipe-blazepose", keypoint_names=list(KEYPOINTS), timestamps=timestamps,
            timestamp_source=ts_src if timestamps is not None else None,
            frame_count_note=frame_count_note,
        )
