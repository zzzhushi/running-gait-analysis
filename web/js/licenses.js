// Attribution shown for browser-delivered dependencies. Versions come from config.js;
// license and source links are declared with each component below.

import { PYODIDE_VERSION, TASKS_VISION_VERSION, MP4BOX_VERSION } from "./config.js";
import { el } from "./format.js";

export const THIRD_PARTY = [
  {
    name: "Pyodide",
    version: PYODIDE_VERSION,
    license: "MPL-2.0",
    role: "Runs the Python analysis engine in your browser (WebAssembly).",
    url: "https://github.com/pyodide/pyodide",
    licenseUrl: "https://github.com/pyodide/pyodide/blob/main/LICENSE",
  },
  {
    name: "MediaPipe Tasks Vision",
    version: TASKS_VISION_VERSION,
    license: "Apache-2.0",
    role: "Detects body landmarks in each video frame.",
    url: "https://github.com/google-ai-edge/mediapipe",
    licenseUrl: "https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE",
  },
  {
    name: "BlazePose GHUM pose landmarker (heavy)",
    version: "float16/1",
    license: "Apache-2.0",
    role: "The pose model itself — © Google. Downloaded once, then runs locally.",
    url: "https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker",
    licenseUrl: "https://storage.googleapis.com/mediapipe-assets/Model%20Card%20BlazePose%20GHUM%203D.pdf",
  },
  {
    name: "MP4Box.js",
    version: MP4BOX_VERSION,
    license: "BSD-3-Clause",
    role: "Reads your video's frame data before pose detection runs on it.",
    url: "https://github.com/gpac/mp4box.js",
    licenseUrl: "https://github.com/gpac/mp4box.js/blob/master/LICENSE",
  },
];

let _dlg = null;

function build() {
  const rows = THIRD_PARTY.map((d) =>
    el("div", { class: "lic-row" }, [
      el("div", { class: "lic-head" }, [
        el("a", { href: d.url, target: "_blank", rel: "noopener noreferrer" }, d.name),
        el("span", { class: "lic-ver" }, " " + d.version),
        el("a", {
          class: "lic-tag", href: d.licenseUrl, target: "_blank", rel: "noopener noreferrer",
        }, d.license),
      ]),
      el("div", { class: "lic-role" }, d.role),
    ]));

  const dlg = el("dialog", { class: "lic-dlg" }, [
    el("h2", {}, "About & licenses"),
    el("p", { class: "lic-own" }, [
      "GaitLab is free and open source under the ",
      el("a", {
        href: "https://github.com/zzzhushi/running-gait-analysis/blob/main/LICENSE",
        target: "_blank", rel: "noopener noreferrer",
      }, "MIT License"),
      " — © 2026 zzzhushi.",
    ]),
    el("p", { class: "lic-priv" },
      "Your video is never uploaded. Everything below runs on your own device; the only " +
      "network requests are the one-time downloads of these components."),
    el("h3", {}, "Third-party components"),
    ...rows,
    el("form", { method: "dialog" }, [el("button", { class: "btn" }, "Close")]),
  ]);

  document.body.append(dlg);
  return dlg;
}

export function openLicenses() {
  if (!_dlg) _dlg = build();
  _dlg.showModal();
}
