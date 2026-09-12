import * as api from "../api.js";
import { el, fmt, viewLabel } from "../format.js";
import { lineChart } from "../charts.js";

export default async function trends(app) {
  const activeUser = api.getActiveUser();
  const runs = await api.listRuns(activeUser?.id);
  const userLabel = activeUser ? activeUser.name + "'s" : "Your";
  app.append(el("div", { class: "crumb" }, [el("a", { "data-nav": "#/library" }, "← Library")]));
  app.append(el("div", { class: "page-head" }, [el("div", {}, [
    el("h1", {}, userLabel + " trends"),
    el("p", {}, "How your metrics move across sessions."),
  ])]));

  if (!runs.length) { app.append(el("div", { class: "empty" }, "No runs yet.")); return; }

  const chrono = [...runs].reverse();
  const step = Math.ceil((chrono.length || 1) / 6);
  const labels = chrono.map((r, i) =>
    i % step === 0 ? new Date(r.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "");

  app.append(el("div", { class: "chart-row" }, [
    chart("Cadence (spm) · compare like-for-like speeds", lineChart(chrono.map((r) => r.cadence), { color: "#4dabf7", dp: 0, labels })),
  ]));

  app.append(el("h3", { class: "sectitle" }, "Compare two runs"));
  const selA = runSelect(runs);
  const selB = runSelect(runs);
  if (runs[1]) selB.value = runs[1].id;
  const out = el("div", { class: "panel" });
  const draw = async () => {
    out.innerHTML = "";
    const a = await api.getRun(selA.value), b = await api.getRun(selB.value);
    if (a && b) out.append(compareTable(a, b));
  };
  selA.addEventListener("change", draw);
  selB.addEventListener("change", draw);
  app.append(el("div", { class: "compare-pick" }, [selA, el("span", { style: "color:var(--muted)" }, "vs"), selB]), out);
  draw();
}

function chart(title, svg) {
  return el("div", { class: "panel chart" }, [el("h4", {}, title), el("div", { html: svg })]);
}
function runSelect(runs) {
  return el("select", { style: "max-width:280px" },
    runs.map((r) => el("option", { value: r.id }, r.label || viewLabel(r.view) + " run")));
}

function compareTable(a, b) {
  const mapB = Object.fromEntries(b.metrics.map((m) => [m.key, m]));
  const rows = a.metrics
    .filter((m) => m.value != null && m.key !== "foot_strike_angle")
    .map((m) => {
      const mb = mapB[m.key];
      const delta = mb && mb.value != null ? m.value - mb.value : null;
      return el("tr", {}, [
        el("td", {}, m.label),
        el("td", { class: "num" }, fmt(m.value, 0) + " " + m.unit),
        el("td", { class: "num" }, mb ? fmt(mb.value, 0) + " " + mb.unit : "—"),
        el("td", { class: "num", style: "color:var(--muted)" },
          delta == null ? "—" : (delta > 0 ? "+" : "") + delta.toFixed(1)),
      ]);
    });
  const summary = el("div", { style: "margin-bottom:10px;font-size:13px;color:var(--muted)" },
    "Signed change only. Interpret repeated measurements at the same speed and capture setup.");
  const table = el("table", { class: "cmp" }, [
    el("tr", {}, [
      el("th", {}, "Metric"),
      el("th", {}, "A: " + (a.summary.label || viewLabel(a.summary.view))),
      el("th", {}, "B: " + (b.summary.label || viewLabel(b.summary.view))),
      el("th", {}, "Δ (A−B)"),
    ]),
    ...rows,
  ]);
  return el("div", {}, [summary, table]);
}
