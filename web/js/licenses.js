// Third-party attribution panel (issue #21).
//
// The app ships third-party code and a third-party ML model to every visitor, so it has
// to say so in the UI. Versions are NOT repeated here — they are imported from config.js,
// which is already the single source of truth for the pinned CDN/asset versions. Bumping
// a version there updates this panel automatically.
//
// Verified obligations (do not downgrade these to guesses):
//   Pyodide            MPL-2.0     Loaded from jsDelivr, never vendored or modified. CDN
//                                  delivery is "Executable Form" (MPL §3.2), so the duty is
//                                  to keep notices intact and point at the source — not to
//                                  relicense anything. MPL is file-level copyleft and does
//                                  not affect GaitLab's own MIT code.
//   tasks-vision       Apache-2.0  Retain the notice; we make no modifications to state.
//   pose_landmarker    Apache-2.0  Per Google's BlazePose GHUM model card, which is linked
//                                  below as the authority (the solution docs page itself
//                                  does not state the bundle's license).
//   rtmlib / RTMPose   Apache-2.0  Local extractor only — never shipped to the browser, so
//                                  it is credited in the README rather than here.

import { PYODIDE_VERSION, TASKS_VISION_VERSION } from "./config.js";
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
