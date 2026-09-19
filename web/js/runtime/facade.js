export class UnsupportedRuntimeOperation extends Error {
  constructor(runtime, operation) {
    super(`${operation} is unavailable in the ${runtime} runtime`);
    this.name = "UnsupportedRuntimeOperation";
    this.runtime = runtime;
    this.operation = operation;
  }
}

function asyncOperation(adapter, operation, name, values) {
  if (typeof operation !== "function") {
    return Promise.reject(new UnsupportedRuntimeOperation(adapter.name, name));
  }
  try { return Promise.resolve(operation(...values)); }
  catch (error) { return Promise.reject(error); }
}

function syncOperation(adapter, operation, name, values) {
  if (typeof operation !== "function") {
    throw new UnsupportedRuntimeOperation(adapter.name, name);
  }
  return operation(...values);
}

export function createRuntimeApi(adapter) {
  const api = {
    runtimeName: adapter.name,
    listRuns: (...values) => asyncOperation(adapter, adapter.listRuns, "listRuns", values),
    getRun: (...values) => asyncOperation(adapter, adapter.getRun, "getRun", values),
    analyzePose: (...values) => asyncOperation(adapter, adapter.analyzePose, "analyzePose", values),
    deleteRun: (...values) => asyncOperation(adapter, adapter.deleteRun, "deleteRun", values),
    reseed: (...values) => asyncOperation(adapter, adapter.reseed, "reseed", values),
    narrative: (...values) => asyncOperation(adapter, adapter.narrative, "narrative", values),
    listUsers: (...values) => asyncOperation(adapter, adapter.listUsers, "listUsers", values),
    createUser: (...values) => asyncOperation(adapter, adapter.createUser, "createUser", values),
    updateUser: (...values) => asyncOperation(adapter, adapter.updateUser, "updateUser", values),
    deleteUser: (...values) => asyncOperation(adapter, adapter.deleteUser, "deleteUser", values),
    getActiveUser: (...values) => syncOperation(adapter, adapter.getActiveUser, "getActiveUser", values),
    setActiveUser: (...values) => syncOperation(adapter, adapter.setActiveUser, "setActiveUser", values),
    listVideos: (...values) => asyncOperation(adapter, adapter.listVideos, "listVideos", values),
    ingest: (...values) => asyncOperation(adapter, adapter.ingest, "ingest", values),
  }

  // Video object URLs belong to the browser session in either runtime and are
  // intentionally outside the persistence adapters.
  const videoUrls = new Map();
  api.setVideoUrl = (id, url) => videoUrls.set(id, url);
  api.getVideoUrl = (id) => videoUrls.get(id);

  return Object.freeze(api);
}
