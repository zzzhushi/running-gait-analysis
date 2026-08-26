import { STATIC_CAPABILITIES } from "./capabilities.js";
import { normalizeAnalysisResponse } from "./contract.js";

let sequence = 0;
function nextId() {
  return "r" + Date.now().toString(36) + (sequence++).toString(36);
}

export function createStaticRuntime({ engine, idFactory = nextId } = {}) {
  if (!engine || typeof engine.runAnalysis !== "function") {
    throw new TypeError("The static runtime requires an analysis engine");
  }

  // Deliberately session-scoped. Static deployments do not pretend to provide
  // server persistence, accounts, seed data, narratives, or disk ingestion.
  const runs = new Map();

  return Object.freeze({
    name: "static",
    capabilities: STATIC_CAPABILITIES,

    async getRun(id) {
      return runs.get(id) || null;
    },

    async analyzePose(pose, label, profile, onProgress) {
      const result = await engine.runAnalysis(pose, label, profile, onProgress);
      const response = normalizeAnalysisResponse({ id: idFactory(), result });
      runs.set(response.id, response.result);
      return response;
    },
  });
}
