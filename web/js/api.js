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
const api = createRuntimeApi(adapter);

export const runtimeName = api.runtimeName;
export const capabilities = api.capabilities;
export const listRuns = api.listRuns;
export const getRun = api.getRun;
export const analyzePose = api.analyzePose;
export const deleteRun = api.deleteRun;
export const reseed = api.reseed;
export const narrative = api.narrative;
export const listUsers = api.listUsers;
export const createUser = api.createUser;
export const updateUser = api.updateUser;
export const deleteUser = api.deleteUser;
export const getActiveUser = api.getActiveUser;
export const setActiveUser = api.setActiveUser;
export const listVideos = api.listVideos;
export const ingest = api.ingest;
export const setVideoUrl = api.setVideoUrl;
export const getVideoUrl = api.getVideoUrl;
