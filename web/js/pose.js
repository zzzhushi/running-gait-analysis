// In-browser BlazePose extraction mapped to the canonical PoseSequence schema.
// Keep BLAZEPOSE and toCanonical() aligned with extractor/blazepose.py.

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

// BlazePose face landmarks used to derive the canonical `head` point (ears/nose).
const EAR_L = 7, EAR_R = 8, NOSE = 0;

// Pure function: one frame of BlazePose landmarks -> one canonical frame (22 points).
// `lm` is an array of { x, y, visibility } in normalized [0,1] coords. Mirrors the
// Python to_canonical(): pixel-scale by (w,h), derive neck/mid_hip/head, zero small toes.
export function toCanonical(lm, w, h) {
  const P = (i) => [lm[i].x * w, lm[i].y * h, Number(lm[i].visibility ?? 1.0)];
  const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.min(a[2], b[2])];
  const frame = [];
  for (const name of KEYPOINTS) {
    if (name in BLAZEPOSE) {
      frame.push(P(BLAZEPOSE[name]));
    } else if (name === "neck") {
      frame.push(mid(P(11), P(12)));
    } else if (name === "mid_hip") {
      frame.push(mid(P(23), P(24)));
    } else if (name === "head") {
      // BlazePose lacks a crown point; use the ears when visible, otherwise the nose.
      const l = P(EAR_L), r = P(EAR_R);
      frame.push(l[2] > 0.1 || r[2] > 0.1 ? mid(l, r) : P(NOSE));
    } else {
      frame.push([0.0, 0.0, 0.0]);
    }
  }
  return frame;
}

const ZERO_FRAME = () => KEYPOINTS.map(() => [0.0, 0.0, 0.0]);
const round3 = (p) => p.map((v) => Math.round(v * 1000) / 1000);

let _landmarkerPromise = null;
// MediaPipe uses timestamp deltas for smoothing and requires them to increase across the
// cached landmarker's lifetime. Offset real media time for each extraction run.
let _mpEpoch = 0;
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

// Real-time playback lets the compositor skip presenting a frame it can't keep up
// with, so requestVideoFrameCallback silently sees fewer frames than the video has.
// Slowing playback during collection is what makes every frame actually get presented.
export const EXTRACTION_PLAYBACK_RATE = 0.25;

export function seekTo(video, t) {
  return new Promise((resolve) => {
    // currentTime already equal to t (e.g. the first requested frame, at 0) would
    // never fire its own "seeked" event, hanging extraction on frame one.
    if (Math.abs(video.currentTime - t) < 1e-3) { resolve(); return; }
    video.addEventListener("seeked", resolve, { once: true });
    video.currentTime = t;
  });
}

// Collect presentation times without running inference in the callback, then process those
// frames without real-time pressure. Returns null when rVFC is unavailable.
export function collectFrameTimes(video) {
  if (typeof video.requestVideoFrameCallback !== "function") return Promise.resolve(null);
  return new Promise((resolve) => {
    const times = [];
    let done = false;
    // Return a copy so later extraction seeks cannot mutate the collected grid.
    const finish = () => {
      if (done) return;
      done = true;
      video.pause();
      resolve(times.length ? times.slice() : null);
    };
    const onFrame = (_now, meta) => {
      if (done) return;
      times.push(meta.mediaTime);
      if (video.ended) finish();
      else video.requestVideoFrameCallback(onFrame);
    };
    video.addEventListener("ended", finish, { once: true });
    video.requestVideoFrameCallback(onFrame);
    video.playbackRate = EXTRACTION_PLAYBACK_RATE;
    const tryPlay = () => {
      video.play().catch((e) => {
        // A backgrounded tab aborts video-only playback; retry once the tab is
        // visible again rather than silently falling back to an assumed grid.
        const backgrounded = e && e.name === "AbortError" &&
          typeof document !== "undefined" && document.hidden;
        if (!backgrounded) { finish(); return; }
        const onVisible = () => {
          if (document.hidden) return;
          document.removeEventListener("visibilitychange", onVisible);
          tryPlay();
        };
        document.addEventListener("visibilitychange", onVisible);
      });
    };
    tryPlay();
  });
}

// Race a promise against a timeout so a stalled extraction (e.g. a tab that never
// comes back to the foreground) falls back instead of hanging indefinitely.
function withTimeout(promise, ms) {
  return Promise.race([promise, new Promise((resolve) => setTimeout(() => resolve(null), ms))]);
}

// Fraction of frames the browser itself reports dropping during collection, when it
// exposes that count. A debug/diagnostic signal only — no browser guarantees this API.
function droppedFrameRatio(video) {
  if (typeof video.getVideoPlaybackQuality !== "function") return null;
  const q = video.getVideoPlaybackQuality();
  const total = q.totalVideoFrames || 0;
  return total ? (q.droppedVideoFrames || 0) / total : null;
}

// Discard display-refresh callbacks that occur too close to represent distinct video
// frames; keeping them would distort the frame-index-to-time mapping.
function dedupeFrameTimes(times) {
  if (times.length < 4) return times;
  const gaps = [];
  for (let i = 1; i < times.length; i++) gaps.push(times[i] - times[i - 1]);
  gaps.sort((a, b) => a - b);
  const medGap = gaps[gaps.length >> 1];
  if (!(medGap > 0)) return times;
  const minGap = medGap * 0.6;
  const kept = [times[0]];
  for (let i = 1; i < times.length; i++) {
    if (times[i] - kept[kept.length - 1] >= minGap) kept.push(times[i]);
  }
  return kept;
}

// Use the average observed rate so frame index / fps spans the same elapsed time even when
// frames are missing. Median frame gaps do not preserve total duration.
export function fpsFromTimestamps(ts) {
  if (ts.length >= 2) {
    const span = ts[ts.length - 1] - ts[0];
    if (span > 0) return (ts.length - 1) / span;
  }
  const diffs = [];
  for (let i = 1; i < ts.length; i++) {
    const d = ts[i] - ts[i - 1];
    if (d > 0) diffs.push(d);
  }
  if (!diffs.length) return 30;
  diffs.sort((a, b) => a - b);
  const med = diffs[diffs.length >> 1];
  return med > 0 ? 1 / med : 30;
}

// Extract a pose dict from a video object URL. First collect the presentation-time grid,
// then seek and run inference without real-time pressure. Preserve that grid as the pose
// timestamps; browsers without rVFC use a fixed 30 fps grid.
export async function extract(videoUrl, view, onProgress = () => {}) {
  onProgress(0, "Loading pose model…");
  const [landmarker, video] = await Promise.all([getLandmarker(), loadVideo(videoUrl)]);
  const width = video.videoWidth;
  const height = video.videoHeight;
  const duration = video.duration || 0;

  onProgress(0, "Scanning frames…");
  // At EXTRACTION_PLAYBACK_RATE, collection itself takes ~1/rate real time; add slack
  // on top for the tab to regain focus once if it gets backgrounded mid-collection.
  const collectTimeoutMs = Math.max(15000, (duration * 1000) / EXTRACTION_PLAYBACK_RATE + 20000);
  let frameTimes = await withTimeout(collectFrameTimes(video), collectTimeoutMs);
  const droppedRatio = droppedFrameRatio(video);
  let timestampSource = "measured";
  if (!frameTimes || frameTimes.length < 4) {
    frameTimes = [];
    for (let t = 0; t < duration; t += 1 / 30) frameTimes.push(t);
    timestampSource = "assumed";
  }
  frameTimes = dedupeFrameTimes(frameTimes);
  await seekTo(video, 0);

  const frames = [];
  const timestamps = [];
  // Preserve real frame deltas while keeping MediaPipe timestamps monotonic across runs.
  const epoch = _mpEpoch;
  let lastMs = -1;

  for (let i = 0; i < frameTimes.length; i++) {
    const t = Math.min(frameTimes[i], duration);
    await seekTo(video, t);
    let ms = epoch + Math.round(t * 1000);
    if (ms <= lastMs) ms = lastMs + 1; // guard vs rounding collisions
    lastMs = ms;
    const res = landmarker.detectForVideo(video, ms);
    const lm = res.landmarks && res.landmarks[0];
    frames.push(lm ? toCanonical(lm, width, height).map(round3) : ZERO_FRAME());
    timestamps.push(Math.round(t * 10000) / 10000);
    onProgress((i + 1) / frameTimes.length, `Extracting pose… ${frames.length} frames`);
  }
  _mpEpoch = Math.max(_mpEpoch, lastMs + 1000); // next run starts past this one (monotonic)

  onProgress(1, `Extracted ${frames.length} frames`);
  return {
    schema: "gaitlab.pose/v1",
    source: "mediapipe-blazepose",
    view,
    fps: fpsFromTimestamps(timestamps),
    width,
    height,
    keypoint_names: KEYPOINTS.slice(),
    frames,
    timestamps,
    // Client-side capture diagnostics. The Python engine's from_pose_dict() reads a
    // fixed set of keys and round-trips only those, so these never reach the analysis
    // result — upload.js reads them straight off this return value instead.
    timestamp_source: timestampSource,
    dropped_frame_ratio: droppedRatio,
  };
}
