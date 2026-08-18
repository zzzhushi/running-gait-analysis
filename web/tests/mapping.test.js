// Layer 3 — the one risky pure-JS port. Feed fake BlazePose landmarks to toCanonical()
// and assert the canonical 22-keypoint frame: pixel scaling, derived neck/mid_hip/head,
// and zeroed small toes. No browser, no video, no model.
import { describe, it, expect } from "vitest";
import { toCanonical, KEYPOINTS, BLAZEPOSE, fpsFromTimestamps } from "../js/pose.js";

const W = 1000;
const H = 2000;

// 33 landmarks with distinct, easy-to-check normalized coords.
function fakeLandmarks() {
  return Array.from({ length: 33 }, (_, i) => ({
    x: (i + 1) / 50,
    y: (i + 1) / 40,
    visibility: 0.9,
  }));
}
const idx = (name) => KEYPOINTS.indexOf(name);
const P = (i) => [((i + 1) / 50) * W, ((i + 1) / 40) * H, 0.9];

describe("toCanonical", () => {
  const frame = toCanonical(fakeLandmarks(), W, H);

  it("emits exactly the 22 canonical keypoints", () => {
    expect(KEYPOINTS.length).toBe(22);
    expect(frame.length).toBe(22);
  });

  it("scales mapped keypoints to pixels using their BlazePose index", () => {
    expect(frame[idx("nose")]).toEqual(P(BLAZEPOSE.nose));
    expect(frame[idx("l_hip")]).toEqual(P(BLAZEPOSE.l_hip));
    expect(frame[idx("l_big_toe")]).toEqual(P(BLAZEPOSE.l_big_toe));
  });

  it("derives neck as the shoulder midpoint (min confidence)", () => {
    const a = P(11), b = P(12);
    expect(frame[idx("neck")]).toEqual([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.min(a[2], b[2])]);
  });

  it("derives mid_hip as the hip midpoint", () => {
    const a = P(23), b = P(24);
    expect(frame[idx("mid_hip")]).toEqual([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.min(a[2], b[2])]);
  });

  it("derives head as the ear midpoint (BlazePose has no crown point)", () => {
    const a = P(7), b = P(8); // left/right ear
    expect(frame[idx("head")]).toEqual([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.min(a[2], b[2])]);
  });

  it("falls back to nose for head when both ears are invisible", () => {
    const lm = fakeLandmarks();
    lm[7].visibility = 0;
    lm[8].visibility = 0;
    const f = toCanonical(lm, W, H);
    expect(f[idx("head")]).toEqual([lm[0].x * W, lm[0].y * H, 0.9]); // nose keeps its own visibility
  });

  it("leaves small toes absent (zeroed) — BlazePose has none", () => {
    expect(frame[idx("l_small_toe")]).toEqual([0, 0, 0]);
    expect(frame[idx("r_small_toe")]).toEqual([0, 0, 0]);
  });

  it("defaults missing visibility to 1.0", () => {
    const lm = fakeLandmarks();
    delete lm[BLAZEPOSE.nose].visibility;
    const f = toCanonical(lm, W, H);
    expect(f[idx("nose")][2]).toBe(1.0);
  });
});

// The fps we hand the engine is a time base, not a frame-spacing statistic: the engine
// maps frame INDEX back to wall-clock as index/fps, so this must be the average rate over
// the clip. Reporting 1/median(gap) instead silently inflates cadence in proportion to
// however many frames the real-time playthrough dropped — a real 165 spm came back as 200.
describe("fpsFromTimestamps", () => {
  const grid = (n, step, from = 0) => Array.from({ length: n }, (_, i) => from + i * step);

  it("returns the nominal rate for an evenly spaced grid", () => {
    expect(fpsFromTimestamps(grid(301, 1 / 30))).toBeCloseTo(30, 6);
  });

  // Drop every 6th frame while KEEPING the first and last, so the surviving span is a
  // clean 10 s and the expected rate is exactly 250/10 = 25 with no edge effects to
  // reason about. (Dropping index 0 and the last index instead shortens the span and
  // makes the true answer 25.067 — a fine result, but a needlessly fiddly assertion.)
  const droppedGrid = () => grid(301, 1 / 30).filter((_, i) => i % 6 !== 5);

  it("reports the AVERAGE rate when frames are missing, not the surviving gap", () => {
    // Survivors are still mostly 1/30 apart, so a median-gap reading would say ~30 and
    // overstate the rate by 20% — which is exactly how cadence got inflated.
    const ts = droppedGrid();
    expect(fpsFromTimestamps(ts)).toBeCloseTo(25, 6);   // 5 of every 6 frames kept
    expect(fpsFromTimestamps(ts)).toBeLessThan(29);     // must NOT come back as ~30
  });

  it("keeps index/fps reconstructing the true clip duration", () => {
    const ts = droppedGrid();
    const span = ts[ts.length - 1] - ts[0];
    expect((ts.length - 1) / fpsFromTimestamps(ts)).toBeCloseTo(span, 6);
  });

  it("falls back to 30 rather than dividing by zero on degenerate input", () => {
    expect(fpsFromTimestamps([])).toBe(30);
    expect(fpsFromTimestamps([1.5])).toBe(30);
    expect(fpsFromTimestamps([2, 2, 2])).toBe(30);     // zero span
  });
});
