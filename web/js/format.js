// Small formatting + DOM helpers.

export function el(tag, attrs = {}, children = []) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null) continue;
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null || c === false) continue;
    n.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return n;
}

export const esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const fmt = (v, dp = 0) =>
  v == null || Number.isNaN(v) ? "—" : Number(v).toFixed(dp);

export const gradeClass = (g) => "s-" + String(g || "e").toLowerCase();
export const scoreClass = (s) => { const n = Number(s) || 0; return n >= 85 ? "s-a" : n >= 72 ? "s-b" : n >= 58 ? "s-c" : n >= 42 ? "s-d" : "s-e"; };

export const STATUS_COLOR = {
  good: "var(--good)", warn: "var(--warn)", bad: "var(--bad)", info: "var(--accent)",
};

export function viewLabel(v) {
  return { "side-left": "Side", "side-right": "Side", rear: "Rear", front: "Front" }[v] || v;
}

export function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const s = Math.max(0, (Date.now() - then) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  return Math.floor(s / 86400) + "d ago";
}

// flexion (0 = straight leg) from an interior joint angle
export const flexion = (interior) => (interior == null ? null : 180 - interior);
