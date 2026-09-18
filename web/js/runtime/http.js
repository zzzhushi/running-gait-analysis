export async function readJson(response) {
  if (!response.ok) {
    const body = await response.text();
    let detail = "";
    try { detail = JSON.parse(body).error || ""; } catch { /* non-JSON error body */ }
    const error = new Error(`HTTP ${response.status}${detail ? ": " + detail : ""}`);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

export async function requestJson(fetchImpl, url, init) {
  if (typeof fetchImpl !== "function") throw new Error("Fetch is unavailable in the server runtime");
  return readJson(await fetchImpl(url, init));
}
