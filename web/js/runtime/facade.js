export class UnsupportedRuntimeOperation extends Error {
  constructor(runtime, operation) {
    super(`${operation} is unavailable in the ${runtime} runtime`);
    this.name = "UnsupportedRuntimeOperation";
    this.runtime = runtime;
    this.operation = operation;
  }
}

const ASYNC_OPERATIONS = [
  "listRuns", "getRun", "analyzePose", "deleteRun", "reseed", "narrative",
  "listUsers", "createUser", "updateUser", "deleteUser", "listVideos", "ingest",
];
const SYNC_OPERATIONS = ["getActiveUser", "setActiveUser"];

export function createRuntimeApi(adapter) {
  const api = {
    runtimeName: adapter.name,
    capabilities: adapter.capabilities,
  };

  for (const operation of ASYNC_OPERATIONS) {
    api[operation] = (...args) => {
      const implementation = adapter[operation];
      if (typeof implementation !== "function") {
        return Promise.reject(new UnsupportedRuntimeOperation(adapter.name, operation));
      }
      try { return Promise.resolve(implementation(...args)); }
      catch (error) { return Promise.reject(error); }
    };
  }

  for (const operation of SYNC_OPERATIONS) {
    api[operation] = (...args) => {
      const implementation = adapter[operation];
      if (typeof implementation !== "function") {
        throw new UnsupportedRuntimeOperation(adapter.name, operation);
      }
      return implementation(...args);
    };
  }

  // Video object URLs belong to the browser session in either runtime and are
  // intentionally outside the persistence adapters.
  const videoUrls = new Map();
  api.setVideoUrl = (id, url) => videoUrls.set(id, url);
  api.getVideoUrl = (id) => videoUrls.get(id);

  return Object.freeze(api);
}
