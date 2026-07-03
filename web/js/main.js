import library from "./screens/library.js";
import upload from "./screens/upload.js";
import report from "./screens/report.js";
import analyze from "./screens/analyze.js";
import trends from "./screens/trends.js";
import combine from "./screens/combine.js";
import { el } from "./format.js";
import * as api from "./api.js";
import { IS_STATIC } from "./config.js";

const HOME = IS_STATIC ? "#/upload" : "#/library";

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
  const raw = location.hash || HOME;
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
  if (!area) return;

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

document.body.classList.toggle("static", IS_STATIC);
if (!location.hash) location.hash = HOME;
else route();
initHeader();
