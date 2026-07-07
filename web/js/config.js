// Runtime selector + pinned CDN/asset versions — one source of truth for both the
// static (GitHub Pages) build and the local server.py build. The *same* SPA runs
// either way; only api.js's internals and the asset base paths differ.

const _search = (typeof location !== "undefined" && location.search) || "";
const _params = new URLSearchParams(_search);
const _override = _params.get("runtime") || (typeof window !== "undefined" && window.GAITLAB_RUNTIME);

// Default to the static, client-side runtime (the shipped product). Local dev
// against server.py opts in with ?runtime=server.
export const RUNTIME = _override === "server" ? "server" : "static";
export const IS_STATIC = RUNTIME === "static";

// Build stamp — replaced with the short commit sha at deploy time by scripts/build_web.py
// (stays "dev" locally). Shown in the footer and logged on boot so you can confirm which
// code a browser is actually running after a deploy.
export const BUILD_VERSION = "dev";

// Pinned CDN versions — bump deliberately, keep in sync with .github/workflows/pages.yml.
export const PYODIDE_VERSION = "0.26.4";
export const PYODIDE_INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

export const TASKS_VISION_VERSION = "0.10.14";
export const TASKS_VISION_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${TASKS_VISION_VERSION}`;

// Heavy pose model — sharpest foot/pronation landmarks. Google's pinned storage URL
// by default; vendoring the .task under web/models/ is a drop-in swap.
export const POSE_MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task";

// The engine package, zipped into web/py/ at build time (make web-static / pages.yml).
export const GAITLAB_ZIP_URL = "./py/gaitlab.zip";
