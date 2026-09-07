// Runtime capabilities are the contract between transport/storage and the UI.
// Screens should branch on these flags instead of inferring behavior from a build
// target or attempting an endpoint and swallowing the resulting error.

export const STATIC_CAPABILITIES = Object.freeze({
  browserAnalysis: true,
  history: false,
  users: false,
  diskIngest: false,
  narrative: false,
  seed: false,
});

export const SERVER_CAPABILITIES = Object.freeze({
  browserAnalysis: false,
  history: true,
  users: true,
  diskIngest: true,
  narrative: true,
  seed: true,
});

export function homeRoute(capabilities) {
  return capabilities.history ? "#/library" : "#/upload";
}

// Route name -> the capability it needs, or null when it works in every runtime.
// main.js filters its route table through enabledRouteNames(), so this is the one
// place a new screen declares what it depends on.
export const ROUTE_CAPABILITIES = Object.freeze({
  library: "history",
  upload: null,
  trends: "history",
  combine: "history",
  report: null,
  analyze: null,
});

export function enabledRouteNames(capabilities) {
  return Object.entries(ROUTE_CAPABILITIES)
    .filter(([, capability]) => capability === null || capabilities[capability])
    .map(([name]) => name);
}
