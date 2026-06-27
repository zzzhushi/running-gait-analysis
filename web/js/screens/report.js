import * as api from "../api.js";
import { el, fmt, gradeClass, viewLabel } from "../format.js";

const SEV = { high: "High", med: "Medium", low: "Minor", good: "Good" };

export default async function report(app, params) {
  const id = params.id;
  const r = await api.getRun(id);
  if (!r) { app.append(el("div", { class: "empty" }, "Run not found.")); return; }
  const s = r.summary;

  app.append(el("div", { class: "crumb" }, [
    el("a", { "data-nav": "#/library" }, "← Library"), " · ",
    el("a", { "data-nav": "#/trends" }, "Trends"),
  ]));

  app.append(el("div", { class: "scorecard" }, [
    el("div", { class: "big " + gradeClass(s.grade) }, s.grade),
    el("div", { class: "sc-meta" }, [
      el("h2", {}, s.label || viewLabel(s.view) + " run"),
      el("p", {}, `${viewLabel(s.view)} view · ${fmt(s.cadence, 0)} spm · ${fmt(s.duration, 1)}s · score ${fmt(s.overall_score, 0)}/100 · ${s.n_findings} finding${s.n_findings === 1 ? "" : "s"}`),
    ]),
    el("div", { style: "margin-left:auto" }, [
      el("a", { class: "btn btn-accent", href: "#/analyze/" + id }, "▶ Open player"),
    ]),
  ]));

  app.append(el("h3", { class: "sectitle" }, "Metrics"));
  const grid = el("div", { class: "metrics-grid" });
  r.metrics.forEach((m) => grid.append(metricCard(m)));
  app.append(grid);

  if (r.asymmetry && r.asymmetry.length) {
    app.append(el("h3", { class: "sectitle" }, "Left / right symmetry"));
    const asym = el("div", { class: "asym" });
    r.asymmetry.forEach((a) => asym.append(asymRow(a)));
    app.append(asym);
  }

  app.append(el("h3", { class: "sectitle" }, "Coach feedback"));
  const findings = el("div", { class: "findings" });
  r.feedback.forEach((f) => findings.append(findingCard(f, id)));
  app.append(findings);
}

function metricCard(m) {
  const card = el("div", { class: "metric " + (m.status || "info") }, [
    el("div", { class: "m-label" }, m.label),
  ]);
  if (m.key === "foot_strike_angle") {
    card.append(el("div", { class: "m-val" }, m.text || "—"));
    card.append(el("div", { class: "m-target" }, m.note || ""));
    return card;
  }
  card.append(el("div", { class: "m-val" }, [fmt(m.value, 0), el("small", {}, " " + m.unit)]));
  if (m.good) {
    const [lo, hi] = m.good;
    const t = lo != null && hi != null ? `${lo}–${hi}` : hi != null ? `under ${hi}` : lo != null ? `over ${lo}` : "";
    card.append(el("div", { class: "m-target" }, "target: " + t + " " + m.unit));
  }
  if (m.per_side && (m.per_side.l != null || m.per_side.r != null)) {
    card.append(el("div", { class: "m-side" }, [
      el("span", { class: "side-l" }, ["L ", el("b", {}, fmt(m.per_side.l, 0))]),
      el("span", { class: "side-r" }, ["R ", el("b", {}, fmt(m.per_side.r, 0))]),
    ]));
  }
  return card;
}

function asymRow(a) {
  const max = Math.max(Math.abs(a.left), Math.abs(a.right)) || 1;
  const lw = (Math.abs(a.left) / max) * 100, rw = (Math.abs(a.right) / max) * 100;
  return el("div", { class: "asym-row" }, [
    el("div", {}, [
      el("div", { class: "asym-lab" }, a.label),
      el("div", { class: "asym-bar left" }, [el("i", { style: `width:${lw}%` })]),
      el("div", { class: "side-l", style: "font-size:12px;margin-top:3px" }, `L ${fmt(a.left, 0)} ${a.unit}`),
    ]),
    el("div", { class: "asym-mid" }, [
      el("div", { class: "pct " + a.status }, fmt(a.diff_pct, 0) + "%"),
      el("div", { style: "font-size:10px;color:var(--muted)" }, "diff"),
    ]),
    el("div", {}, [
      el("div", { class: "asym-lab", style: "text-align:right;min-height:15px" }, " "),
      el("div", { class: "asym-bar right" }, [el("i", { style: `width:${rw}%` })]),
      el("div", { class: "side-r", style: "font-size:12px;margin-top:3px;text-align:right" }, `R ${fmt(a.right, 0)} ${a.unit}`),
    ]),
  ]);
}

function findingCard(f, id) {
  return el("div", { class: "finding-card " + f.severity }, [
    el("div", { class: "sevbar" }),
    el("div", {}, [
      el("h4", {}, f.title),
      el("div", { class: "detail" }, f.detail),
      el("div", { class: "coach" }, [
        f.cue && el("div", { class: "cue" }, f.cue),
        f.drill && el("div", { class: "drill" }, f.drill),
      ]),
    ]),
    el("div", { style: "display:flex;flex-direction:column;gap:8px;align-items:flex-end" }, [
      el("span", { class: "sev-chip" }, SEV[f.severity] || ""),
      f.frame != null ? el("a", { class: "btn btn-sm", href: `#/analyze/${id}?frame=${f.frame}` }, "View frame") : null,
    ]),
  ]);
}
