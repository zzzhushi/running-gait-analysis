// Timeline dropout hatching (web/js/overlay.js): the pure pixel-mapping piece,
// testable without a real <canvas>. drawTimeline() itself needs a 2D rendering
// context this suite has no jsdom/canvas polyfill for, so it isn't exercised here.
import { describe, it, expect } from "vitest";
import { dropoutPixelSpans } from "../js/overlay.js";

describe("dropoutPixelSpans", () => {
  it("maps a quality check's frame span to pixel x/width", () => {
    const quality = [{ level: "warn", message: "...", frames: [30, 60] }];
    expect(dropoutPixelSpans(quality, 300, 900)).toEqual([[90, 90]]);
  });

  it("ignores checks with no frame span", () => {
    const quality = [
      { level: "ok", message: "Capture looks good." },
      { level: "info", message: "..." },
    ];
    expect(dropoutPixelSpans(quality, 300, 900)).toEqual([]);
  });

  it("handles several dropout spans", () => {
    const quality = [
      { level: "warn", message: "a", frames: [0, 30] },
      { level: "warn", message: "b", frames: [270, 299] },
    ];
    expect(dropoutPixelSpans(quality, 300, 900)).toEqual([[0, 90], [810, 87]]);
  });

  it("never returns a zero-width span, so a one-frame gap still draws", () => {
    const quality = [{ level: "warn", message: "a", frames: [10, 10] }];
    const [[, w]] = dropoutPixelSpans(quality, 300, 900);
    expect(w).toBeGreaterThanOrEqual(1);
  });

  it("returns nothing for an empty or missing quality list", () => {
    expect(dropoutPixelSpans([], 300, 900)).toEqual([]);
    expect(dropoutPixelSpans(undefined, 300, 900)).toEqual([]);
  });
});
