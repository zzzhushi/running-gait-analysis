import library from "./screens/library.js";
import upload from "./screens/upload.js";
import report from "./screens/report.js";
import analyze from "./screens/analyze.js";
import trends from "./screens/trends.js";
import combine from "./screens/combine.js";
import { el } from "./format.js";
import * as api from "./api.js";
import { BUILD_VERSION } from "./config.js";
import { openLicenses } from "./licenses.js";
import { enabledRouteNames, homeRoute } from "./runtime/capabilities.js";

const HOME = homeRoute(api.capabilities);
const enabledRoutes = new Set(enabledRouteNames(api.capabilities));

const ROUTES = [
  ["library", /^#\/library$/, library, []],
  ["upload", /^#\/upload$/, upload, []],
  ["trends", /^#\/trends$/, trends, []],
  ["combine", /^#\/combine$/, combine, []],
  ["report", /^#\/report\/(\w+)$/, report, ["id"]],
  ["analyze", /^#\/analyze\/(\w+)$/, analyze, ["id"]],
].filter(([name]) => enabledRoutes.has(name));

let cleanup = null;

async function route() {
  const app = document.getElementById("app");
  const raw = location.hash || HOME;
  const [path, qs] = raw.split("?");
  const query = Object.fromEntries(new URLSearchParams(qs || ""));

  if (cleanup) { try { cleanup(); } catch (e) { /* */ } cleanup = null; }
  app.innerHTML = "";

  for (const [, re, fn, names] of ROUTES) {
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
  location.hash = HOME;
}

// Delegate clicks on [data-nav] elements to hash navigation.
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-nav]");
  if (t) { e.preventDefault(); location.hash = t.getAttribute("data-nav"); }
});

window.addEventListener("hashchange", route);

// ---------------------------------------------------------------- user header
async function initHeader() {
  const area = document.getElementById("user-area");
  if (!area || !api.capabilities.users) return;

  let users = [];
  try { users = await api.listUsers(); } catch { return; }
  if (!users.length) return;

  let active = api.getActiveUser();
  if (!active || !users.find((u) => u.id === active.id)) {
    active = users[0];
    api.setActiveUser(active);
  }

  const wrap = el("div", { class: "user-wrap" });
  const btn = el("button", { class: "user-btn" }, [
    el("span", { class: "user-name" }, active.name),
    el("span", { class: "chevron" }, "▾"),
  ]);
  const menu = el("div", { class: "user-menu", style: "display:none" });

  function buildMenu() {
    menu.innerHTML = "";
    users.forEach((u) => {
      const item = el("button", {
        class: "user-menu-item" + (u.id === active.id ? " current" : ""),
      }, (u.id === active.id ? "✓ " : "") + u.name);
      item.addEventListener("click", () => {
        active = u;
        api.setActiveUser(u);
        btn.querySelector(".user-name").textContent = u.name;
        menu.style.display = "none";
        buildMenu();
        route(); // re-render current screen with new user
      });
      menu.append(item);
    });
    menu.append(el("div", { class: "user-menu-sep" }));
    const newItem = el("button", { class: "user-menu-item" }, "+ New user");
    newItem.addEventListener("click", () => {
      menu.style.display = "none";
      location.hash = "#/upload";
    });
    menu.append(newItem);
  }
  buildMenu();

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.style.display = menu.style.display === "none" ? "block" : "none";
  });
  document.addEventListener("click", () => { menu.style.display = "none"; });

  wrap.append(btn, menu);
  area.append(wrap);
}

function initRuntimeChrome() {
  document.body.dataset.runtime = api.runtimeName;
  const brand = document.querySelector(".brand[data-nav]");
  if (brand) brand.setAttribute("data-nav", HOME);
  document.querySelectorAll("[data-capability]").forEach((node) => {
    node.hidden = !api.capabilities[node.dataset.capability];
  });
  const note = document.getElementById("runtime-note");
  if (note) {
    note.textContent = api.capabilities.browserAnalysis
      ? "Runs entirely in your browser · no account, no upload · pose by MediaPipe (in-browser)"
      : "Runs on this local server · run data stays on this machine";
  }
}

initRuntimeChrome();
// Build stamp: log it and append to the footer so you can confirm a browser picked up a
// fresh deploy (compare against the sha shown in the GitHub Actions run).
console.log(`GaitLab build ${BUILD_VERSION}`);
const foot = document.querySelector(".foot");
if (foot) {
  // Attribution entry point (#21) — the app ships third-party code and an ML model to
  // every visitor, so the notice has to be reachable from every screen.
  foot.append(
    " · ",
    el("a", { href: "#", class: "lic-link", onclick: (e) => { e.preventDefault(); openLicenses(); } },
      "About & licenses"),
    el("span", { style: "opacity:.5" }, ` · build ${BUILD_VERSION}`),
  );
}
if (!location.hash) location.hash = HOME;
else route();
initHeader();
