// Thin wrappers over the local JSON API (same-origin, no CORS needed).

async function j(res) {
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
}

export const listRuns = () => fetch("/api/runs").then(j);
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
