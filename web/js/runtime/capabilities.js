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

export function enabledRouteNames(capabilities) {
  if (!capabilities.history) return ["upload", "report", "analyze"];
  return ["library", "upload", "trends", "combine", "report", "analyze"];
}
