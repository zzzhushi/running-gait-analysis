import library from "./screens/library.js";
import upload from "./screens/upload.js";
import report from "./screens/report.js";
import analyze from "./screens/analyze.js";
import trends from "./screens/trends.js";
import combine from "./screens/combine.js";
import { el } from "./format.js";

const ROUTES = [
  [/^#\/library$/, library, []],
  [/^#\/upload$/, upload, []],
  [/^#\/trends$/, trends, []],
  [/^#\/combine$/, combine, []],
  [/^#\/report\/(\w+)$/, report, ["id"]],
  [/^#\/analyze\/(\w+)$/, analyze, ["id"]],
];

let cleanup = null;

async function route() {
  const app = document.getElementById("app");
  const raw = location.hash || "#/library";
  const [path, qs] = raw.split("?");
  const query = Object.fromEntries(new URLSearchParams(qs || ""));

  if (cleanup) { try { cleanup(); } catch (e) { /* */ } cleanup = null; }
  app.innerHTML = "";

  for (const [re, fn, names] of ROUTES) {
    const m = path.match(re);
    if (!m) continue;
    const params = { ...query };
    names.forEach((nm, i) => (params[nm] = m[i + 1]));
    try {
      cleanup = (await fn(app, params)) || null;
    } catch (e) {
      console.error(e);
      app.innerHTML = "";
      app.append(el("div", { class: "empty" }, "Something went wrong: " + e.message));
    }
    return;
  }
  location.hash = "#/library";
}

// Delegate clicks on [data-nav] elements to hash navigation.
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-nav]");
  if (t) { e.preventDefault(); location.hash = t.getAttribute("data-nav"); }
});

window.addEventListener("hashchange", route);

if (!location.hash) location.hash = "#/library";
else route();
