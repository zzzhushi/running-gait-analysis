// In-browser pose extractor. MediaPipe Tasks-Vision PoseLandmarker (BlazePose 33)
// driven frame-by-frame, mapped to the canonical 22-keypoint schema. Emits the exact
// dict shape as PoseSequence.to_pose_dict() so the engine consumes it identically.
//
// The BLAZEPOSE map + toCanonical() are a verbatim port of
// extractor/extract_pose_mediapipe.py:78-102 — keep them in lockstep.

import { TASKS_VISION_URL, POSE_MODEL_URL } from "./config.js";

// Canonical keypoint order — MUST match gaitlab/core/schema.py KEYPOINTS exactly.
export const KEYPOINTS = [
  "nose", "head", "neck", "mid_hip",
  "l_shoulder", "r_shoulder",
  "l_elbow", "r_elbow",
  "l_wrist", "r_wrist",
  "l_hip", "r_hip",
  "l_knee", "r_knee",
  "l_ankle", "r_ankle",
  "l_heel", "r_heel",
  "l_big_toe", "r_big_toe",
  "l_small_toe", "r_small_toe",
];

// BlazePose 33-landmark indices -> canonical names. BlazePose has no neck / pelvis /
// small-toe, so neck & mid_hip are derived and small toes are left absent.
export const BLAZEPOSE = {
  nose: 0,
  l_shoulder: 11, r_shoulder: 12, l_elbow: 13, r_elbow: 14, l_wrist: 15, r_wrist: 16,
  l_hip: 23, r_hip: 24, l_knee: 25, r_knee: 26, l_ankle: 27, r_ankle: 28,
  l_heel: 29, r_heel: 30, l_big_toe: 31, r_big_toe: 32,
};

// Pure function: one frame of BlazePose landmarks -> one canonical frame (22 points).
// `lm` is an array of { x, y, visibility } in normalized [0,1] coords. Mirrors the
// Python to_canonical(): pixel-scale by (w,h), derive neck/mid_hip, zero the small toes.
export function toCanonical(lm, w, h) {
  const P = (i) => [lm[i].x * w, lm[i].y * h, Number(lm[i].visibility ?? 1.0)];
  const frame = [];
  for (const name of KEYPOINTS) {
    if (name in BLAZEPOSE) {
      frame.push(P(BLAZEPOSE[name]));
    } else if (name === "neck") {
      const a = P(11), b = P(12);
      frame.push([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.min(a[2], b[2])]);
    } else if (name === "mid_hip") {
      const a = P(23), b = P(24);
      frame.push([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.min(a[2], b[2])]);
    } else {
      frame.push([0.0, 0.0, 0.0]);
    }
  }
  return frame;
}

const ZERO_FRAME = () => KEYPOINTS.map(() => [0.0, 0.0, 0.0]);
const round3 = (p) => p.map((v) => Math.round(v * 1000) / 1000);

let _landmarkerPromise = null;
async function getLandmarker() {
  if (_landmarkerPromise) return _landmarkerPromise;
  _landmarkerPromise = (async () => {
    const { FilesetResolver, PoseLandmarker } = await import(`${TASKS_VISION_URL}`);
    const fileset = await FilesetResolver.forVisionTasks(`${TASKS_VISION_URL}/wasm`);
    return PoseLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: POSE_MODEL_URL, delegate: "GPU" },
      runningMode: "VIDEO",
      numPoses: 1,
    });
  })();
  return _landmarkerPromise;
}

function loadVideo(url) {
  return new Promise((resolve, reject) => {
    const v = document.createElement("video");
    v.src = url;
    v.muted = true;
    v.playsInline = true;
    v.preload = "auto";
    v.addEventListener("loadedmetadata", () => resolve(v), { once: true });
    v.addEventListener("error", () => reject(new Error("Could not load video")), { once: true });
  });
}

// rendered fps as the median inter-frame interval — robust to variable frame rate.
function medianFps(timestamps) {
  if (timestamps.length < 2) return 30;
  const dts = [];
  for (let i = 1; i < timestamps.length; i++) {
    const dt = timestamps[i] - timestamps[i - 1];
    if (dt > 0) dts.push(dt);
  }
  if (!dts.length) return 30;
  dts.sort((a, b) => a - b);
  const med = dts[dts.length >> 1];
  return med > 0 ? 1 / med : 30;
}

// Extract a pose dict from a video object-URL. onProgress(fraction 0..1, note).
export async function extract(videoUrl, view, onProgress = () => {}) {
  onProgress(0, "Loading pose model…");
  const [landmarker, video] = await Promise.all([getLandmarker(), loadVideo(videoUrl)]);
  const width = video.videoWidth;
  const height = video.videoHeight;
  const duration = video.duration || 0;

  const frames = [];
  const timestamps = [];
  const useRVFC = typeof video.requestVideoFrameCallback === "function";

  const pushFrame = (mediaTime) => {
    const res = landmarker.detectForVideo(video, Math.max(0, mediaTime * 1000));
    const lm = res.landmarks && res.landmarks[0];
    frames.push(lm ? toCanonical(lm, width, height).map(round3) : ZERO_FRAME());
    timestamps.push(Math.round(mediaTime * 10000) / 10000);
  };
  const report = (t) => onProgress(duration ? Math.min(1, t / duration) : 0,
                                   `Extracting pose… ${frames.length} frames`);

  if (useRVFC) {
    // requestVideoFrameCallback gives the real per-frame mediaTime — the browser twin
    // of ffprobe's container PTS, correct on VFR phone video.
    await new Promise((resolve) => {
      const onFrame = (_now, meta) => {
        pushFrame(meta.mediaTime);
        report(meta.mediaTime);
        if (!video.ended) video.requestVideoFrameCallback(onFrame);
      };
      video.addEventListener("ended", () => resolve(), { once: true });
      video.requestVideoFrameCallback(onFrame);
      video.play().catch(() => resolve()); // autoplay blocked -> nothing to extract
    });
  } else {
    // Firefox: no rVFC. Step through by seeking at an assumed constant frame interval.
    const fps = 30;
    const dt = 1 / fps;
    for (let t = 0; t < duration; t += dt) {
      await new Promise((res) => {
        video.addEventListener("seeked", res, { once: true });
        video.currentTime = t;
      });
      pushFrame(video.currentTime);
      report(video.currentTime);
    }
  }

  onProgress(1, `Extracted ${frames.length} frames`);
  return {
    schema: "gaitlab.pose/v1",
    source: "mediapipe-blazepose",
    view,
    fps: medianFps(timestamps),
    width,
    height,
    keypoint_names: KEYPOINTS.slice(),
    frames,
    timestamps,
  };
}
