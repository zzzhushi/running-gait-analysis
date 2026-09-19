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
  runtimeName,
  listRuns, getRun, analyzePose, deleteRun, reseed, narrative,
  listUsers, createUser, updateUser, deleteUser, getActiveUser, setActiveUser,
  listVideos, ingest, setVideoUrl, getVideoUrl,
} = createRuntimeApi(adapter);

// Client-side extraction diagnostics (timestamp_source, dropped_frame_ratio). Not part
// of the analysis result: the Python engine echoes back only the pose fields it knows
// about, so this rides alongside the run rather than through it. Session-local like
// video URLs above, so it stays outside the runtime adapters too.
const captureMeta = new Map();
export const setCaptureMeta = (id, meta) => captureMeta.set(id, meta);
export const getCaptureMeta = (id) => captureMeta.get(id) || null;
