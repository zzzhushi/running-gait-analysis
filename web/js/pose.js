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
      // BlazePose has no crown-of-head point; the ear midpoint is a stable head-region
      // proxy for lateral head sway / head drop (RTMPose-Halpe supplies one directly).
      // Fall back to the nose when neither ear is visible (e.g. sharp profile).
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
// PoseLandmarker requires strictly increasing timestamps for the LIFETIME of the
// instance, not just within one video. Since the landmarker is a cached singleton (to
// avoid re-loading the model per analysis), a second extract() call restarting at
// mediaTime=0 would be LESS than the first video's last timestamp and MediaPipe throws
// ("Packet timestamp mismatch"). A free-running counter, independent of any video's own
// clock, sidesteps this — the real per-frame time is tracked separately in `timestamps`.
let _mpClock = 0;
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

function seekTo(video, t) {
  return new Promise((resolve) => {
    video.addEventListener("seeked", resolve, { once: true });
    video.currentTime = t;
  });
}

// Record every native frame's true presentation time via a lightweight real-time
// playthrough: the rVFC callback only pushes a timestamp, so it never falls behind and
// never coalesces frames the way running inference in the callback would. This is how we
// learn the real frame grid (count + VFR-correct timing) without dropping anything;
// extraction then seeks to each of these times and runs the model with no time pressure.
// Returns ascending mediaTimes, or null when rVFC is unavailable (Firefox).
function collectFrameTimes(video) {
  if (typeof video.requestVideoFrameCallback !== "function") return Promise.resolve(null);
  return new Promise((resolve) => {
    const times = [];
    let done = false;
    // Once finished, stop the rVFC self-loop and hand back a COPY. Otherwise the final
    // callback re-arms itself, and when extraction later seeks the video (no longer
    // "ended") it keeps firing and appending to the array we're iterating over.
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
    video.play().catch(finish); // autoplay blocked -> fall back below
  });
}

// fps as the median inter-frame interval of the frames we actually decoded. The engine
// reconstructs real time as frame_index / fps (events.py cadence, duration = n/fps), so
// the returned fps MUST match the true spacing of the emitted frames — otherwise cadence
// scales by whatever the sampling error was. Deriving it from real mediaTimes (not the
// probe) keeps cadence correct and identical run-to-run.
function fpsFromTimestamps(ts) {
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

// Extract a pose dict from a video object-URL. onProgress(fraction 0..1, note).
//
// Extraction is deliberately NOT bound to real-time playback: we pause, seek to each
// target time, wait for it to decode, then run inference (however long that takes). This
// mirrors how the Python extractors read every frame from the file via cap.read()
// (extract_pose.py / extract_pose_mediapipe.py), decoupled from wall-clock speed. An
// earlier version drove extraction off requestVideoFrameCallback during real-time
// playback, which silently dropped frames whenever inference (the "heavy" model) took
// longer than one frame interval — the browser delivers only the *latest* rendered frame
// to a busy callback, coalescing away everything in between.
//
// We first learn the true frame grid (collectFrameTimes), then seek to each frame time
// and run the model. Because video.currentTime after a seek reports the *requested* time
// (not the decoded frame's PTS) and rVFC doesn't fire on a paused seek, the frame times
// from the playthrough are the only reliable source of true per-frame timing — so we
// record those as the timestamps and derive fps from them. That keeps the frame count
// deterministic (≈ the file's real frame count, like RTMPose) and the engine's cadence
// (frame_index / fps) correct. Firefox lacks rVFC → fall back to a fixed 30fps seek grid.
export async function extract(videoUrl, view, onProgress = () => {}) {
  onProgress(0, "Loading pose model…");
  const [landmarker, video] = await Promise.all([getLandmarker(), loadVideo(videoUrl)]);
  const width = video.videoWidth;
  const height = video.videoHeight;
  const duration = video.duration || 0;

  onProgress(0, "Scanning frames…");
  let frameTimes = await collectFrameTimes(video);
  if (!frameTimes || frameTimes.length < 4) {
    frameTimes = [];
    for (let t = 0; t < duration; t += 1 / 30) frameTimes.push(t);
  }
  await seekTo(video, 0);

  const frames = [];
  const timestamps = [];

  for (let i = 0; i < frameTimes.length; i++) {
    const t = Math.min(frameTimes[i], duration);
    await seekTo(video, t);
    const res = landmarker.detectForVideo(video, ++_mpClock);
    const lm = res.landmarks && res.landmarks[0];
    frames.push(lm ? toCanonical(lm, width, height).map(round3) : ZERO_FRAME());
    timestamps.push(Math.round(t * 10000) / 10000);
    onProgress((i + 1) / frameTimes.length, `Extracting pose… ${frames.length} frames`);
  }

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
  };
}
