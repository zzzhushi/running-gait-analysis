import { afterEach, describe, expect, it, vi } from "vitest";

import {
  SERVER_CAPABILITIES,
  STATIC_CAPABILITIES,
  enabledRouteNames,
  homeRoute,
} from "../js/runtime/capabilities.js";
import { createRuntimeApi, UnsupportedRuntimeOperation } from "../js/runtime/facade.js";
import { createServerRuntime } from "../js/runtime/server.js";
import { createStaticRuntime } from "../js/runtime/static.js";
import { listRunsForActiveUser } from "../js/screens/combine.js";

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
});

describe("capability-driven UI contract", () => {
  it("keeps history, trends, and combine out of the static route table", () => {
    expect(STATIC_CAPABILITIES).toMatchObject({
      browserAnalysis: true,
      history: false,
      users: false,
      diskIngest: false,
      narrative: false,
      seed: false,
    });
    expect(homeRoute(STATIC_CAPABILITIES)).toBe("#/upload");
    expect(enabledRouteNames(STATIC_CAPABILITIES)).toEqual(["upload", "report", "analyze"]);
  });

  it("enables the persisted-run screens only for the server runtime", () => {
    expect(homeRoute(SERVER_CAPABILITIES)).toBe("#/library");
    expect(enabledRouteNames(SERVER_CAPABILITIES)).toEqual([
      "library", "upload", "trends", "combine", "report", "analyze",
    ]);
  });

  it("loads Combine candidates for the active user only", async () => {
    const client = {
      getActiveUser: vi.fn(() => ({ id: "runner-42", name: "Shirley" })),
      listRuns: vi.fn().mockResolvedValue([{ id: "run-1" }]),
    };

    await expect(listRunsForActiveUser(client)).resolves.toEqual([{ id: "run-1" }]);
    expect(client.listRuns).toHaveBeenCalledWith("runner-42");
  });

  it("resolves a default user before Combine queries and never widens to all runs", async () => {
    const client = {
      capabilities: { users: true },
      getActiveUser: vi.fn(() => null),
      listUsers: vi.fn().mockResolvedValue([{ id: "runner-1", name: "First runner" }]),
      setActiveUser: vi.fn(),
      listRuns: vi.fn().mockResolvedValue([{ id: "run-1" }]),
    };

    await listRunsForActiveUser(client);
    expect(client.setActiveUser).toHaveBeenCalledWith({ id: "runner-1", name: "First runner" });
    expect(client.listRuns).toHaveBeenCalledWith("runner-1");

    const withoutUsers = {
      capabilities: { users: true },
      getActiveUser: vi.fn(() => null),
      listUsers: vi.fn().mockResolvedValue([]),
      setActiveUser: vi.fn(),
      listRuns: vi.fn(),
    };
    await expect(listRunsForActiveUser(withoutUsers)).resolves.toEqual([]);
    expect(withoutUsers.listRuns).not.toHaveBeenCalled();
  });
});
