"""RTMPose extraction via rtmlib, the default source for detailed foot keypoints.

    pip install rtmlib onnxruntime opencv-python
"""

from __future__ import annotations

import sys

from gaitlab.core.schema import KEYPOINTS, PoseSequence

from .base import PoseExtractor
from .timestamps import check_frame_count, choose_timestamps, probe_timestamps

# RTMPose body+feet (Halpe26). Has the 6 foot keypoints we care about.
HALPE26 = {
    "nose": 0, "head": 17, "neck": 18, "mid_hip": 19,
    "l_shoulder": 5, "r_shoulder": 6, "l_elbow": 7, "r_elbow": 8, "l_wrist": 9, "r_wrist": 10,
    "l_hip": 11, "r_hip": 12, "l_knee": 13, "r_knee": 14, "l_ankle": 15, "r_ankle": 16,
    "l_heel": 24, "r_heel": 25, "l_big_toe": 20, "r_big_toe": 21, "l_small_toe": 22, "r_small_toe": 23,
}
# RTMPose whole-body (COCO-WholeBody 133). neck / mid_hip are derived from shoulders / hips.
WHOLEBODY = {
    "nose": 0,
    "l_shoulder": 5, "r_shoulder": 6, "l_elbow": 7, "r_elbow": 8, "l_wrist": 9, "r_wrist": 10,
    "l_hip": 11, "r_hip": 12, "l_knee": 13, "r_knee": 14, "l_ankle": 15, "r_ankle": 16,
    "l_big_toe": 17, "l_small_toe": 18, "l_heel": 19, "r_big_toe": 20, "r_small_toe": 21, "r_heel": 22,
}


def build_model(kind: str, mode: str = "balanced"):
    try:
        from rtmlib import BodyWithFeet, Wholebody
    except ImportError:
        raise RuntimeError(
            "rtmlib is not installed. Run:\n  pip install rtmlib onnxruntime opencv-python"
        ) from None
    if kind == "wholebody":
        return Wholebody(mode=mode, backend="onnxruntime", device="cpu"), WHOLEBODY, "rtmpose-wholebody"
    return BodyWithFeet(mode=mode, backend="onnxruntime", device="cpu"), HALPE26, "rtmpose-halpe26"


def pick_person(keypoints, scores):
    """Choose the most confident detected person (assume one runner)."""
    if keypoints is None or len(keypoints) == 0:
        return None, None
    best = max(range(len(scores)), key=lambda i: float(scores[i].mean()))
    return keypoints[best], scores[best]


def to_canonical(kp, sc, idxmap):
    frame = []
    for name in KEYPOINTS:
        if name in idxmap:
            i = idxmap[name]
            frame.append([float(kp[i][0]), float(kp[i][1]), float(sc[i])])
        elif name == "neck" and "l_shoulder" in idxmap:
            a, b = idxmap["l_shoulder"], idxmap["r_shoulder"]
            frame.append([float((kp[a][0] + kp[b][0]) / 2), float((kp[a][1] + kp[b][1]) / 2), float(min(sc[a], sc[b]))])
        elif name == "mid_hip" and "l_hip" in idxmap:
            a, b = idxmap["l_hip"], idxmap["r_hip"]
            frame.append([float((kp[a][0] + kp[b][0]) / 2), float((kp[a][1] + kp[b][1]) / 2), float(min(sc[a], sc[b]))])
        else:
            frame.append([0.0, 0.0, 0.0])
    return frame


class RTMPoseExtractor(PoseExtractor):
    """Reusable extractor configured by model and speed/accuracy mode."""

    def __init__(self, model: str = "body26", mode: str = "balanced"):
        self.model = model
        self.mode = mode

    def extract(self, video_path: str, view: str, *, every: int = 1,
                max_seconds: float = None, no_ffprobe: bool = False) -> PoseSequence:
        try:
            import cv2
        except ImportError:
            raise RuntimeError(
                "opencv is not installed. Run:\n  pip install rtmlib onnxruntime opencv-python"
            ) from None

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

        model, idxmap, source = build_model(self.model, self.mode)
        print(f"Running {source} ({self.mode}) on {video_path} ({width}x{height} @ {fps:.0f}fps)…",
              file=sys.stderr)

        # Authoritative per-frame presentation timestamps from the container (robust to VFR).
        probe_ts = None if no_ffprobe else probe_timestamps(video_path)

        frames = []
        pos_msec = []   # OpenCV's per-frame timestamp (s) — fallback if ffprobe unavailable
        kept_idx = []   # decode index of each kept frame (to align with probe_ts)
        read_i = 0
        max_frames = int(max_seconds * fps) if max_seconds else None
        stopped_by_request = False
        while True:
            # POS_MSEC, read before grabbing, is the timestamp of the frame about to be read.
            t_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            ok, img = cap.read()
            if not ok:
                break
            if read_i % every == 0:
                kps, scs = model(img)
                kp, sc = pick_person(kps, scs)
                frames.append(to_canonical(kp, sc, idxmap) if kp is not None
                              else [[0.0, 0.0, 0.0] for _ in KEYPOINTS])
                pos_msec.append(t_msec / 1000.0)
                kept_idx.append(read_i)
                if len(frames) % 15 == 0:
                    print(f"\r  {len(frames)} frames analyzed…", end="", file=sys.stderr)
            read_i += 1
            if max_frames and read_i >= max_frames:
                stopped_by_request = True
                break
        cap.release()

        eff_fps = fps / every
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
            fps=eff_fps, width=width, height=height, view=view, frames=frames,
            source=source, keypoint_names=list(KEYPOINTS), timestamps=timestamps,
            timestamp_source=ts_src if timestamps is not None else None,
            frame_count_note=frame_count_note,
        )
