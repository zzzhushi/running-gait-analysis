// Frame-grid extraction (web/js/pose.js): the pieces testable without a real
// <video> element or a browser. No jsdom needed — seekTo/collectFrameTimes only
// touch the video-like object passed to them, never `document`.
import { describe, it, expect, vi } from "vitest";
import { seekTo, collectFrameTimes, EXTRACTION_PLAYBACK_RATE } from "../js/pose.js";

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
