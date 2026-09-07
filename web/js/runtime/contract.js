// analyzePose() and ingest() share this response contract in both runtimes:
// { id: string, result: AnalysisResult, ...optional transport metadata }.
export function normalizeAnalysisResponse(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new TypeError("Analysis response must be an object");
  }
  if (typeof payload.id !== "string" || !payload.id) {
    throw new TypeError("Analysis response is missing a run id");
  }
  if (!payload.result || typeof payload.result !== "object" || Array.isArray(payload.result)) {
    throw new TypeError("Analysis response is missing its result");
  }
  return { ...payload };
}
