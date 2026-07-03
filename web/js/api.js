// The one server seam. In "server" mode these are thin wrappers over the local JSON
// API (same-origin). In "static" mode (GitHub Pages) analysis runs fully client-side:
// pose -> Pyodide engine -> in-memory store. Selected at runtime via config.js.

import { IS_STATIC } from "./config.js";
import * as engine from "./engine.js";

async function j(res) {
  if (!res.ok) {
    const text = await res.text();
    const err = new Error("HTTP " + res.status);
    err.body = text;
    throw err;
  }
  return res.json();
}

// --- static in-memory run store (no server, no persistence) -------------------
// Results live only for this session, keyed by a generated id; mirrors the videoUrls
// pattern below. report.js / analyze.js read them back through getRun() unchanged.
const runs = new Map();
let _seq = 0;
const genId = () => "r" + Date.now().toString(36) + (_seq++).toString(36);

// --- runs ---------------------------------------------------------------------
export const listRuns = IS_STATIC
  ? async () => []
  : (userId) => fetch("/api/runs" + (userId ? "?user_id=" + userId : "")).then(j);

export const getRun = IS_STATIC
  ? async (id) => runs.get(id) || null
  : (id) => fetch("/api/runs/" + id).then((r) => (r.ok ? r.json() : null));

// pose -> result. In static mode returns { id, ...result }; onProgress(fraction, note).
export const analyzePose = IS_STATIC
  ? async (pose, label, profile, onProgress) => {
      const result = await engine.runAnalysis(pose, label, profile, onProgress);
      const id = genId();
      runs.set(id, result);
      return { id, ...result };
    }
  : (pose, label, profile) =>
      fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pose, label, profile }),
      }).then(j);

export const deleteRun = (id) => fetch("/api/runs/" + id, { method: "DELETE" }).then(j);
export const reseed = () => fetch("/api/seed", { method: "POST" }).then(j);
export const narrative = (id) => fetch("/api/narrative/" + id, { method: "POST" }).then(j);

// --- users (server only; static returns none so the picker stays hidden) ------
export const listUsers = IS_STATIC ? async () => [] : () => fetch("/api/users").then(j);
export const createUser = (data) =>
  fetch("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then(j);
export const updateUser = (id, data) =>
  fetch("/api/users/" + id, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then(j);
export const deleteUser = (id) =>
  fetch("/api/users/" + id, { method: "DELETE" }).then(j);

const ACTIVE_USER_KEY = "gaitlab_active_user";
export const getActiveUser = () => {
  try { return JSON.parse(localStorage.getItem(ACTIVE_USER_KEY)); } catch { return null; }
};
export const setActiveUser = (user) =>
  localStorage.setItem(ACTIVE_USER_KEY, user ? JSON.stringify(user) : "null");

// --- videos (server only; static picks a local file in upload.js) -------------
export const listVideos = () => fetch("/api/videos").then(j);
export const ingest = (video, view, opts = {}) =>
  fetch("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video, view, ...opts }),
  }).then(j);

// Video blobs are not persisted server-side; keep them in-memory per run id so the
// player can overlay on the real footage during this session.
const videoUrls = new Map();
export const setVideoUrl = (id, url) => videoUrls.set(id, url);
export const getVideoUrl = (id) => videoUrls.get(id);
