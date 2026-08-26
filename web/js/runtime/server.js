import { SERVER_CAPABILITIES } from "./capabilities.js";
import { normalizeAnalysisResponse } from "./contract.js";
import { readJson, requestJson } from "./http.js";

const ACTIVE_USER_KEY = "gaitlab_active_user";
const jsonHeaders = { "Content-Type": "application/json" };
const pathPart = (value) => encodeURIComponent(String(value));

function defaultStorage() {
  try { return globalThis.localStorage || null; } catch { return null; }
}

export function createServerRuntime({ fetchImpl = globalThis.fetch, storage = defaultStorage() } = {}) {
  let memoryUser = null;
  const request = (url, init) => requestJson(fetchImpl, url, init);
  const post = (url, body) => request(url, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });

  return Object.freeze({
    name: "server",
    capabilities: SERVER_CAPABILITIES,

    listRuns(userId) {
      const query = userId ? "?" + new URLSearchParams({ user_id: userId }) : "";
      return request("/api/runs" + query);
    },

    async getRun(id) {
      if (typeof fetchImpl !== "function") throw new Error("Fetch is unavailable in the server runtime");
      const response = await fetchImpl("/api/runs/" + pathPart(id));
      if (response.status === 404) return null;
      return readJson(response);
    },

    async analyzePose(pose, label, profile) {
      return normalizeAnalysisResponse(await post("/api/analyze", { pose, label, profile }));
    },

    deleteRun(id) {
      return request("/api/runs/" + pathPart(id), { method: "DELETE" });
    },

    reseed(userId = null) {
      return post("/api/seed", userId ? { user_id: userId } : {});
    },

    narrative(id) {
      return request("/api/narrative/" + pathPart(id), { method: "POST" });
    },

    listUsers() {
      return request("/api/users");
    },

    createUser(data) {
      return post("/api/users", data);
    },

    updateUser(id, data) {
      return request("/api/users/" + pathPart(id), {
        method: "PUT",
        headers: jsonHeaders,
        body: JSON.stringify(data),
      });
    },

    deleteUser(id) {
      return request("/api/users/" + pathPart(id), { method: "DELETE" });
    },

    getActiveUser() {
      try {
        const value = storage && storage.getItem(ACTIVE_USER_KEY);
        return value ? JSON.parse(value) : memoryUser;
      } catch { return memoryUser; }
    },

    setActiveUser(user) {
      memoryUser = user || null;
      try {
        if (storage) storage.setItem(ACTIVE_USER_KEY, JSON.stringify(memoryUser));
      } catch { /* an in-memory fallback still keeps this tab usable */ }
    },

    listVideos() {
      return request("/api/videos");
    },

    async ingest(video, view, options = {}) {
      return normalizeAnalysisResponse(await post("/api/ingest", { video, view, ...options }));
    },
  });
}
