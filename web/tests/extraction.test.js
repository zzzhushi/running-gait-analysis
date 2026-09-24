// Frame-grid extraction (web/js/pose.js): the pieces testable without a real
// <video> element or a browser. No jsdom needed — seekTo/collectFrameTimes only
// touch the video-like object passed to them, never `document`.
import { describe, it, expect, vi } from "vitest";
import {
  seekTo, collectFrameTimes, EXTRACTION_PLAYBACK_RATE,
  rotationFromMatrix, canvasTransformFor,
  mp4PresentationTimeline,
} from "../js/pose.js";

describe("mp4PresentationTimeline (issue #99)", () => {
  const sample = (cts) => ({ cts });
  const edit = (mediaTime, duration = 1000) => ({
    media_time: mediaTime, segment_duration: duration,
    media_rate_integer: 1, media_rate_fraction: 0,
  });

  it("keeps composition PTS unchanged when there is no edit list", () => {
    const clock = mp4PresentationTimeline([sample(256)], 15360, 1000, null);
    expect(clock.timestampUs(sample(256))).toBe(16667);
    expect(clock.timestampSource).toContain("no edit list");
  });

  it("uses the file's media_time and both timebases, not a fixed frame offset", () => {
    const clock = mp4PresentationTimeline(
      [sample(256), sample(384), sample(512)], 15360, 1000, [edit(256)]
    );
    expect([256, 384, 512].map(cts => clock.timestampUs(sample(cts))))
      .toEqual([0, 8333, 16667]);
    expect(clock.timestampSource).toContain("edit list applied");
  });

  it("accounts for a leading empty edit in movie, not media, time units", () => {
    const clock = mp4PresentationTimeline(
      [sample(300), sample(450)], 30000, 1000,
      [{ media_time: -1, segment_duration: 250 }, edit(300)]
    );
    expect(clock.timestampUs(sample(300))).toBe(250000);
    expect(clock.timestampUs(sample(450))).toBe(255000);
  });

  it("rejects trims and non-unit or repeated edits rather than mislabeling frames", () => {
    expect(() => mp4PresentationTimeline([sample(100), sample(200)], 1000, 1000,
      [edit(200)])).toThrow(/outside the presentation edit/);
    expect(() => mp4PresentationTimeline([sample(1000)], 1000, 1000,
      [edit(0, 1000)])).toThrow(/outside the presentation edit/);
    expect(() => mp4PresentationTimeline([sample(0)], 1000, 1000,
      [{ ...edit(0), media_rate_integer: 2 }])).toThrow(/Unsupported MP4 edit list/);
    expect(() => mp4PresentationTimeline([sample(0)], 1000, 1000,
      [edit(0), edit(0)])).toThrow(/Unsupported MP4 edit list/);
  });
});

function fakeVideo(overrides = {}) {
  const listeners = {};
  return {
    currentTime: 0,
    playbackRate: 1,
    ended: false,
    addEventListener: (name, cb) => { listeners[name] = cb; },
    removeEventListener: (name) => { delete listeners[name]; },
    _listeners: listeners,
    play: () => Promise.resolve(),
    pause: vi.fn(),
    requestVideoFrameCallback: () => {},
    ...overrides,
  };
}

describe("seekTo", () => {
  it("resolves without waiting when already at the target time", async () => {
    const video = fakeVideo({ currentTime: 1.234 });
    let waited = false;
    video.addEventListener = () => { waited = true; };
    await seekTo(video, 1.234);
    expect(waited).toBe(false);
  });

  it("otherwise sets currentTime and waits for the seeked event", async () => {
    const video = fakeVideo();
    const done = vi.fn();
    seekTo(video, 2.5).then(done);
    expect(video.currentTime).toBe(2.5);
    expect(done).not.toHaveBeenCalled();
    video._listeners.seeked();
    await Promise.resolve();
    expect(done).toHaveBeenCalled();
  });
});

describe("collectFrameTimes", () => {
  it("plays back at the slowed extraction rate, not real time", () => {
    const video = fakeVideo({ play: () => new Promise(() => {}) });
    collectFrameTimes(video);
    expect(video.playbackRate).toBe(EXTRACTION_PLAYBACK_RATE);
    expect(EXTRACTION_PLAYBACK_RATE).toBeLessThan(1);
  });

  it("resolves null when the browser has no requestVideoFrameCallback", async () => {
    const video = fakeVideo({ requestVideoFrameCallback: undefined });
    await expect(collectFrameTimes(video)).resolves.toBeNull();
  });

  it("stops driving the video once its signal is aborted", async () => {
    let onFrame;
    const rvfc = vi.fn((cb) => { onFrame = cb; });
    const video = fakeVideo({ requestVideoFrameCallback: rvfc });
    const controller = new AbortController();

    const result = collectFrameTimes(video, { signal: controller.signal });
    onFrame(0, { mediaTime: 0 }); // one real frame arrives, re-registers itself
    const registeredBeforeAbort = rvfc.mock.calls.length;

    controller.abort();
    await result;

    // The extraction loop is about to seek this same element; it must be paused, not
    // still mid-playback from an abandoned collection.
    expect(video.pause).toHaveBeenCalled();
    // A stray in-flight callback firing after abort must not restart the loop.
    onFrame(1, { mediaTime: 1 / 30 });
    expect(rvfc.mock.calls.length).toBe(registeredBeforeAbort);
  });
});

// ISO/IEC 14496-12 tkhd matrices in 16.16 fixed point (a,b,u,c,d,v,x,y,w): the four
// values a phone encoder actually emits for axis-aligned display rotation. A <video>
// element applies this automatically; WebCodecs decode does not.
const FP = 65536;
const W = 0x40000000;
const IDENTITY = [FP, 0, 0, 0, FP, 0, 0, 0, W];
const ROT_90 = [0, FP, 0, -FP, 0, 0, 0, 0, W];
const ROT_180 = [-FP, 0, 0, 0, -FP, 0, 0, 0, W];
const ROT_270 = [0, -FP, 0, FP, 0, 0, 0, 0, W];

describe("rotationFromMatrix", () => {
  it("reads identity as no rotation", () => {
    expect(rotationFromMatrix(IDENTITY)).toEqual({ angle: 0, swapped: false });
  });

  it("reads the 90-degree matrix and flags a width/height swap", () => {
    expect(rotationFromMatrix(ROT_90)).toEqual({ angle: 90, swapped: true });
  });

  it("reads 180 degrees without a swap", () => {
    expect(rotationFromMatrix(ROT_180)).toEqual({ angle: 180, swapped: false });
  });

  it("reads 270 degrees with a swap", () => {
    expect(rotationFromMatrix(ROT_270)).toEqual({ angle: 270, swapped: true });
  });

  it("returns null for a matrix that is not one of the four axis-aligned rotations", () => {
    // A flip (mirrored) matrix: same family as a front-camera selfie clip, which this
    // codebase does not claim to handle -- reporting unsupported beats guessing wrong.
    expect(rotationFromMatrix([-FP, 0, 0, 0, FP, 0, 0, 0, W])).toBeNull();
  });
});

describe("canvasTransformFor", () => {
  it("is the identity transform at 0 degrees", () => {
    expect(canvasTransformFor({ angle: 0 }, 720, 1280)).toEqual([1, 0, 0, 1, 0, 0]);
  });

  it("maps a coded corner into the positive quadrant at 90 degrees", () => {
    const [a, b, c, d, e, f] = canvasTransformFor({ angle: 90 }, 720, 1280);
    // The coded frame's four corners, after this transform, must land inside a
    // 1280x720 canvas (the swapped, display-oriented size) with no negative coordinate.
    const corners = [[0, 0], [720, 0], [0, 1280], [720, 1280]];
    for (const [x, y] of corners) {
      const px = a * x + c * y + e;
      const py = b * x + d * y + f;
      expect(px).toBeGreaterThanOrEqual(0);
      expect(px).toBeLessThanOrEqual(1280);
      expect(py).toBeGreaterThanOrEqual(0);
      expect(py).toBeLessThanOrEqual(720);
    }
  });

  it("maps a coded corner into the positive quadrant at 270 degrees", () => {
    const [a, b, c, d, e, f] = canvasTransformFor({ angle: 270 }, 720, 1280);
    const corners = [[0, 0], [720, 0], [0, 1280], [720, 1280]];
    for (const [x, y] of corners) {
      const px = a * x + c * y + e;
      const py = b * x + d * y + f;
      expect(px).toBeGreaterThanOrEqual(0);
      expect(px).toBeLessThanOrEqual(1280);
      expect(py).toBeGreaterThanOrEqual(0);
      expect(py).toBeLessThanOrEqual(720);
    }
  });
});
