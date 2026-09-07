// Stable browser API surface. Runtime-specific transport, persistence, and supported
// operations live behind adapters in ./runtime/.

import { RUNTIME } from "./config.js";
import * as engine from "./engine.js";
import { createRuntimeApi } from "./runtime/facade.js";
import { createServerRuntime } from "./runtime/server.js";
import { createStaticRuntime } from "./runtime/static.js";

const adapter = RUNTIME === "server"
  ? createServerRuntime()
  : createStaticRuntime({ engine });

// Named re-exports, so screens keep importing operations rather than an adapter.
// Anything the active runtime does not implement still resolves here and rejects
// with UnsupportedRuntimeOperation when called -- see ./runtime/facade.js.
export const {
  runtimeName, capabilities,
  listRuns, getRun, analyzePose, deleteRun, reseed, narrative,
  listUsers, createUser, updateUser, deleteUser, getActiveUser, setActiveUser,
  listVideos, ingest, setVideoUrl, getVideoUrl,
} = createRuntimeApi(adapter);
