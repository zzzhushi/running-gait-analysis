// In-browser BlazePose extraction mapped to the canonical PoseSequence schema.
// Keep BLAZEPOSE and toCanonical() aligned with extractor/blazepose.py.

import { TASKS_VISION_URL, POSE_MODEL_URL, MP4BOX_URL } from "./config.js";

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

// ISO/IEC 14496-12's tkhd matrix carries a phone's display rotation separately from the
// coded pixels. A <video> element applies it for free during playback; VideoDecoder does
// not apply it at all, so a decoder-based path must read and apply it explicitly or hand
// back sideways-oriented frames.
//
// Values are 16.16 fixed-point (row a,b,c,d at indices 0,1,3,4; ISO 14496-12 §8.4.2.2),
// the same convention CanvasRenderingContext2D.setTransform uses, so the matrix maps
// directly onto a canvas transform once translated into the positive quadrant. Only the
// four axis-aligned rotations phones actually emit are handled; an unrecognised
// transform (shear, perspective, a flip) returns null rather than a guess.
export function rotationFromMatrix(matrix) {
  const FIXED = 65536; // 16.16 fixed-point unit
  const round = (v) => Math.round(v / FIXED);
  const a = round(matrix[0]);
  const b = round(matrix[1]);
  const c = round(matrix[3]);
  const d = round(matrix[4]);
  const CASES = {
    "1,0,0,1": { angle: 0, swapped: false },
    "0,1,-1,0": { angle: 90, swapped: true },
    "-1,0,0,-1": { angle: 180, swapped: false },
    "0,-1,1,0": { angle: 270, swapped: true },
  };
  return CASES[`${a},${b},${c},${d}`] || null;
}

// A canvas transform equivalent to `rot`, for a coded frame of `codedW` x `codedH`,
// translated so the rotated content lands in the canvas's positive quadrant. Matches
// CanvasRenderingContext2D.setTransform(a, b, c, d, e, f)'s own argument order.
export function canvasTransformFor(rot, codedW, codedH) {
  switch (rot.angle) {
    case 90: return [0, 1, -1, 0, codedH, 0];
    case 180: return [-1, 0, 0, -1, codedW, codedH];
    case 270: return [0, -1, 1, 0, 0, codedW];
    default: return [1, 0, 0, 1, 0, 0];
  }
}

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
//
// `signal` lets a caller cancel collection (see withTimeout below): aborting stops the
// rVFC re-registration loop and pauses the video, so a timed-out collector cannot keep
// driving playback out from under the extraction loop that takes over the same element.
export function collectFrameTimes(video, { signal } = {}) {
  if (typeof video.requestVideoFrameCallback !== "function") return Promise.resolve(null);
  return new Promise((resolve) => {
    const times = [];
    let done = false;
    // Return a copy so later extraction seeks cannot mutate the collected grid.
    const finish = () => {
      if (done) return;
      done = true;
      video.removeEventListener("ended", finish);
      if (signal) signal.removeEventListener("abort", finish);
      video.pause();
      resolve(times.length ? times.slice() : null);
    };
    if (signal) {
      if (signal.aborted) { finish(); return; }
      signal.addEventListener("abort", finish, { once: true });
    }
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

// Race a cancellable collection against a timeout so a stalled extraction (e.g. a tab
// that never comes back to the foreground) falls back instead of hanging indefinitely.
// `collect` receives an AbortSignal and must stop driving the video once it fires --
// otherwise the losing side keeps playing the same <video> element the fallback path
// is about to take over for inference.
function withTimeout(collect, ms) {
  const controller = new AbortController();
  return new Promise((resolve) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      controller.abort();
      resolve(null);
    }, ms);
    collect(controller.signal).then((v) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(v);
    });
  });
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

// Extract a pose dict via requestVideoFrameCallback-driven playback. First collect the
// presentation-time grid, then seek and run inference without real-time pressure.
// Preserve that grid as the pose timestamps; browsers without rVFC use a fixed 30 fps
// grid. This is the fallback used where WebCodecs is unavailable; see extractViaWebCodecs
// for the primary path and why this one is not used when a demuxer is available.
async function extractViaPlayback(videoUrl, view, onProgress) {
  onProgress(0, "Loading pose model…");
  const [landmarker, video] = await Promise.all([getLandmarker(), loadVideo(videoUrl)]);
  const width = video.videoWidth;
  const height = video.videoHeight;
  const duration = video.duration || 0;

  onProgress(0, "Scanning frames…");
  // At EXTRACTION_PLAYBACK_RATE, collection itself takes ~1/rate real time; add slack
  // on top for the tab to regain focus once if it gets backgrounded mid-collection.
  const collectTimeoutMs = Math.max(15000, (duration * 1000) / EXTRACTION_PLAYBACK_RATE + 20000);
  let frameTimes = await withTimeout(
    (signal) => collectFrameTimes(video, { signal }), collectTimeoutMs
  );
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

// Demux the video's track with mp4box.js: raw samples plus the codec's avcC/hvcC
// description, which VideoDecoder.configure() requires and a <video> element does not
// expose. Resolves once every sample the container promised has been delivered, since
// this build's onFlush callback is not reliably invoked after flush().
async function demuxVideoTrack(videoUrl) {
  const mod = await import(MP4BOX_URL);
  const MP4Box = mod.default || mod;
  const buf = await (await fetch(videoUrl)).arrayBuffer();
  buf.fileStart = 0;

  return new Promise((resolve, reject) => {
    const file = MP4Box.createFile();
    const collected = [];
    let track = null;
    let description = null;
    file.onError = (e) => reject(new Error(`mp4 demux failed: ${e}`));
    file.onReady = (info) => {
      track = info.videoTracks[0];
      if (!track) { reject(new Error("No video track in file")); return; }
      const trak = file.getTrackById(track.id);
      for (const entry of trak.mdia.minf.stbl.stsd.entries) {
        const box = entry.avcC || entry.hvcC;
        if (box) {
          const stream = new MP4Box.DataStream(undefined, 0, MP4Box.DataStream.BIG_ENDIAN);
          box.write(stream);
          description = new Uint8Array(stream.buffer, 8); // skip the box header
        }
      }
      if (!description) { reject(new Error("No avcC/hvcC description in track")); return; }
      file.setExtractionOptions(track.id, null, { nbSamples: track.nb_samples });
      file.start();
    };
    file.onSamples = (id, user, arr) => {
      for (const s of arr) collected.push(s);
      if (collected.length >= track.nb_samples) {
        // codedWidth/Height is the elementary stream's own size, which is what
        // VideoDecoder needs configured and what a decoded VideoFrame is shaped as.
        // It is the coded (pre-rotation) size, not necessarily the display size --
        // rotation is handled separately by the caller via `rotation`.
        const rotation = rotationFromMatrix(track.matrix);
        if (!rotation) {
          // A transform this codebase does not recognise (shear, perspective, a flip)
          // must not be coerced to identity: that would silently score pixels in the
          // wrong orientation, which is the exact failure this whole path exists to
          // prevent. No frame has been decoded yet, so this is safe to reject outright.
          reject(new Error("Unsupported video orientation (non-axis-aligned display transform)"));
          return;
        }
        resolve({
          codec: track.codec,
          codedWidth: track.video.width,
          codedHeight: track.video.height,
          rotation,
          timescale: track.timescale,
          samples: collected,
          description,
        });
      }
    };
    file.appendBuffer(buf);
    file.flush();
  });
}

// Thrown by extractViaWebCodecs. Never caught to retry via the playback path (see
// extract()) -- `partial` is diagnostic, not a branch point: false means nothing was
// fed to the landmarker yet (unsupported container/codec, no track, an unrecognised
// display transform); true means some frames were already decoded and scored before
// the failure, so the landmarker's cached VIDEO-mode state and _mpEpoch reflect a run
// that never finished. Either way the caller sees a clear failure rather than a result
// stitched from two different extraction mechanisms with no signal that happened.
class ExtractionError extends Error {
  constructor(message, { partial }) {
    super(message);
    this.partial = partial;
  }
}

// Extract a pose dict via WebCodecs: demux the container's samples directly and decode
// them with VideoDecoder, bypassing <video> element playback and
// requestVideoFrameCallback entirely. On WebKit that presentation pipeline can silently
// drop a large fraction of a high-frame-rate clip's frames regardless of playback rate,
// while seeking within the same video remains frame-accurate; decoding demuxed samples
// sidesteps presentation altogether, so every sample the container declares is decoded.
async function extractViaWebCodecs(videoUrl, view, onProgress) {
  onProgress(0, "Loading pose model…");
  const [landmarker, track] = await Promise.all([getLandmarker(), demuxVideoTrack(videoUrl)]);
  const { codedWidth, codedHeight, rotation, timescale, samples, description } = track;
  // The canonical pose is always in display orientation -- toCanonical()'s (w, h) scale
  // and the mapping every downstream metric assumes must match what a person watching
  // the clip actually sees, the same contract the <video>-based path gets for free.
  const width = rotation.swapped ? codedHeight : codedWidth;
  const height = rotation.swapped ? codedWidth : codedHeight;

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(...canvasTransformFor(rotation, codedWidth, codedHeight));

  const frames = [];
  const timestamps = [];
  const epoch = _mpEpoch;
  let lastMs = -1;
  let lastTs = -Infinity;
  const total = samples.length;
  let processed = 0;
  let failure = null;

  onProgress(0, "Decoding frames…");
  try {
    await new Promise((resolve, reject) => {
      const settle = (err) => {
        if (failure) return; // first failure wins; later callbacks are no-ops
        failure = err;
        try { decoder.close(); } catch { /* already closing */ }
        reject(err);
      };
      const decoder = new VideoDecoder({
        output: (frame) => {
          if (failure) { frame.close(); return; }
          const tSec = frame.timestamp / 1e6;
          // The spec does not guarantee decode order matches presentation order for
          // every codec. Continuing past a reordered frame would corrupt event timing
          // silently -- exactly the failure mode this path exists to remove -- so it is
          // treated as a hard failure rather than a count and a warning.
          if (tSec < lastTs) {
            frame.close();
            settle(new ExtractionError(
              "decoded frame arrived out of presentation order", { partial: processed > 0 }
            ));
            return;
          }
          lastTs = tSec;

          ctx.drawImage(frame, 0, 0, codedWidth, codedHeight);
          frame.close();

          let ms = epoch + Math.round(tSec * 1000);
          if (ms <= lastMs) ms = lastMs + 1;
          lastMs = ms;
          const res = landmarker.detectForVideo(canvas, ms);
          const lm = res.landmarks && res.landmarks[0];
          frames.push(lm ? toCanonical(lm, width, height).map(round3) : ZERO_FRAME());
          timestamps.push(Math.round(tSec * 10000) / 10000);
          processed++;
          onProgress(processed / total, `Extracting pose… ${frames.length} frames`);
        },
        error: (e) => settle(new ExtractionError(
          e && e.message || String(e), { partial: processed > 0 }
        )),
      });
      try {
        decoder.configure({ codec: track.codec, codedWidth, codedHeight, description });
      } catch (e) {
        settle(new ExtractionError(`unsupported codec: ${e.message || e}`, { partial: false }));
        return;
      }
      for (const s of samples) {
        decoder.decode(new EncodedVideoChunk({
          type: s.is_sync ? "key" : "delta",
          timestamp: Math.round((s.cts * 1e6) / timescale),
          duration: Math.round((s.duration * 1e6) / timescale),
          data: s.data,
        }));
      }
      decoder.flush().then(() => { decoder.close(); resolve(); }, settle);
    });
  } finally {
    // Advance the shared landmarker clock past whatever this run fed it, success or
    // not, so a retry (via either path) never reuses timestamps this run already used.
    if (lastMs >= 0) _mpEpoch = Math.max(_mpEpoch, lastMs + 1000);
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
    timestamp_source: "decoded",
    // The container's own declared sample count is the completeness ground truth here,
    // independent of what decoding actually produced -- unlike the playback path, where
    // nothing independent of the collected grid itself was available.
    dropped_frame_ratio: total ? 1 - processed / total : null,
    source_interval: samples.length > 1
      ? (samples[samples.length - 1].cts - samples[0].cts) / timescale / (samples.length - 1)
      : null,
  };
}

function webCodecsAvailable() {
  return typeof VideoDecoder !== "undefined" && typeof EncodedVideoChunk !== "undefined";
}

// Extract a pose dict from a video object URL. Prefers WebCodecs, which decodes every
// frame the container declares regardless of engine. The playback path is used only
// when WebCodecs itself is unsupported by the browser, never as a recovery from a
// WebCodecs failure on a browser that does support it: a file the primary path cannot
// handle is not evidence the unreliable fallback would have handled it correctly, so
// such a file surfaces as a clear extraction failure instead of a silent retry.
export async function extract(videoUrl, view, onProgress = () => {}) {
  if (!webCodecsAvailable()) return extractViaPlayback(videoUrl, view, onProgress);
  return extractViaWebCodecs(videoUrl, view, onProgress);
}
