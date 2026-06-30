// Thin wrappers over the local JSON API (same-origin, no CORS needed).

async function j(res) {
  if (!res.ok) {
    const text = await res.text();
    const err = new Error("HTTP " + res.status);
    err.body = text;
    throw err;
  }
  return res.json();
}

export const listRuns = (userId) =>
  fetch("/api/runs" + (userId ? "?user_id=" + userId : "")).then(j);
export const getRun = (id) => fetch("/api/runs/" + id).then((r) => (r.ok ? r.json() : null));
export const analyzePose = (pose, label, profile) =>
  fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pose, label, profile }),
  }).then(j);
export const deleteRun = (id) => fetch("/api/runs/" + id, { method: "DELETE" }).then(j);
export const reseed = () => fetch("/api/seed", { method: "POST" }).then(j);
export const narrative = (id) => fetch("/api/narrative/" + id, { method: "POST" }).then(j);
export const listUsers = () => fetch("/api/users").then(j);
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

export const listVideos = () => fetch("/api/videos").then(j);
export const ingest = (video, view, opts = {}) =>
  fetch("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video, view, ...opts }),
  }).then(j);

// Video blobs are not persisted server-side in v1; keep them in-memory per run id
// so the player can overlay on the real footage during this session.
const videoUrls = new Map();
export const setVideoUrl = (id, url) => videoUrls.set(id, url);
export const getVideoUrl = (id) => videoUrls.get(id);
