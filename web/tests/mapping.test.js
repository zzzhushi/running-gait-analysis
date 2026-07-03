// Layer 3 — the one risky pure-JS port. Feed fake BlazePose landmarks to toCanonical()
// and assert the canonical 22-keypoint frame: pixel scaling, derived neck/mid_hip, and
// zeroed small toes. No browser, no video, no model.
import { describe, it, expect } from "vitest";
import { toCanonical, KEYPOINTS, BLAZEPOSE } from "../js/pose.js";

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
