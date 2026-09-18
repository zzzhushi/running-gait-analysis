import { afterEach, describe, expect, it, vi } from "vitest";

import { createRuntimeApi, UnsupportedRuntimeOperation } from "../js/runtime/facade.js";
import { createServerRuntime } from "../js/runtime/server.js";
import { createStaticRuntime } from "../js/runtime/static.js";
import { loadThumbnailRun } from "../js/screens/library.js";

function response(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
    text: async () => JSON.stringify(data),
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("static runtime contract", () => {
  it("stores results in memory and returns the same analysis envelope as the server", async () => {
    const result = { summary: { label: "tempo", overall_score: 82 } };
    const engine = { runAnalysis: vi.fn().mockResolvedValue(result) };
    const runtime = createStaticRuntime({ engine, idFactory: () => "run-static" });

    await expect(runtime.analyzePose({ frames: [] }, "tempo", { speed_kmh: 12 }))
      .resolves.toEqual({ id: "run-static", result });
    await expect(runtime.getRun("run-static")).resolves.toBe(result);
    await expect(runtime.getRun("missing")).resolves.toBeNull();
    expect(engine.runAnalysis).toHaveBeenCalledWith(
      { frames: [] }, "tempo", { speed_kmh: 12 }, undefined,
    );
  });

  it("does not implement or fetch server-only operations", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const adapter = createStaticRuntime({
      engine: { runAnalysis: vi.fn() },
      idFactory: () => "unused",
    });
    const api = createRuntimeApi(adapter);
    const serverOnly = [
      "listRuns", "deleteRun", "reseed", "narrative", "listUsers", "createUser",
      "updateUser", "deleteUser", "listVideos", "ingest",
    ];

    for (const operation of serverOnly) {
      expect(adapter[operation]).toBeUndefined();
      await expect(api[operation]()).rejects.toEqual(
        expect.objectContaining({
          name: "UnsupportedRuntimeOperation",
          runtime: "static",
          operation,
        }),
      );
    }
    expect(() => api.getActiveUser()).toThrow(UnsupportedRuntimeOperation);
    expect(() => api.setActiveUser(null)).toThrow(UnsupportedRuntimeOperation);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("server runtime contract", () => {
  it("normalizes analyze and ingest responses to { id, result, ...metadata }", async () => {
    const result = { summary: { label: "intervals", overall_score: 76 } };
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(response({ id: "run-analyze", result }))
      .mockResolvedValueOnce(response({
        id: "run-ingest", result, cached: true, extractor_log: "cached pose",
      }));
    const runtime = createServerRuntime({ fetchImpl, storage: null });

    await expect(runtime.analyzePose({ frames: [] }, "intervals", null))
      .resolves.toEqual({ id: "run-analyze", result });
    await expect(runtime.ingest("clip 1", "rear", { user_id: "user-1" }))
      .resolves.toEqual({
        id: "run-ingest", result, cached: true, extractor_log: "cached pose",
      });

    expect(fetchImpl).toHaveBeenNthCalledWith(1, "/api/analyze", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({
      pose: { frames: [] }, label: "intervals", profile: null,
    });
    expect(fetchImpl).toHaveBeenNthCalledWith(2, "/api/ingest", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(fetchImpl.mock.calls[1][1].body)).toEqual({
      video: "clip 1", view: "rear", user_id: "user-1",
    });
  });

  it("rejects a drifted analysis response instead of leaking a second shape", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response({ id: "run-flat", summary: {} }));
    const runtime = createServerRuntime({ fetchImpl, storage: null });

    await expect(runtime.analyzePose({}, "", null)).rejects.toThrow(
      "Analysis response is missing its result",
    );
  });

  it("filters run queries by an encoded user id and treats only 404 as missing", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response({ error: "not found" }, 404))
      .mockResolvedValueOnce(response({ error: "database unavailable" }, 500));
    const runtime = createServerRuntime({ fetchImpl, storage: null });

    await expect(runtime.listRuns("runner / one")).resolves.toEqual([]);
    expect(fetchImpl).toHaveBeenNthCalledWith(1, "/api/runs?user_id=runner+%2F+one", undefined);
    await expect(runtime.getRun("missing")).resolves.toBeNull();
    await expect(runtime.getRun("broken")).rejects.toMatchObject({ status: 500 });
  });

  it("seeds demo runs into the active user's library", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response([]));
    const runtime = createServerRuntime({ fetchImpl, storage: null });

    await expect(runtime.reseed("runner-1")).resolves.toEqual([]);
    expect(fetchImpl).toHaveBeenCalledWith("/api/seed", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ user_id: "runner-1" }),
    }));
  });

  it("keeps the in-memory active user when storage rejects an update", () => {
    const storage = {
      getItem: vi.fn(() => JSON.stringify({ id: "old-user" })),
      setItem: vi.fn(() => { throw new Error("storage blocked"); }),
    };
    const runtime = createServerRuntime({ fetchImpl: vi.fn(), storage });

    runtime.setActiveUser({ id: "new-user" });

    expect(runtime.getActiveUser()).toEqual({ id: "new-user" });
  });
});

describe("Library error handling", () => {
  it("isolates a failed thumbnail request from the rest of Library", async () => {
    const error = new Error("database unavailable");
    const client = { getRun: vi.fn().mockRejectedValue(error) };
    const onError = vi.fn();

    await expect(loadThumbnailRun(client, "run-broken", onError)).resolves.toBeNull();
    expect(onError).toHaveBeenCalledWith(
      "Could not load thumbnail for run run-broken",
      error,
    );
  });
});
