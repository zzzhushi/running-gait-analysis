import * as api from "../api.js";
import { el, fmt, viewLabel } from "../format.js";

const SEV = { high: "Review", med: "Review", low: "Observation", good: "Note" };

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
    el("div", { class: "big" }, "2-D"),
    el("div", { class: "sc-meta" }, [
      el("h2", {}, s.label || viewLabel(s.view) + " run"),
      el("p", {}, `${viewLabel(s.view)} view · ${fmt(s.cadence, 0)} spm · ${fmt(s.duration, 1)}s · descriptive research output${profileStr(s.profile)}`),
    ]),
    el("div", { style: "margin-left:auto" }, [
      el("a", { class: "btn btn-accent", href: "#/analyze/" + id }, "▶ Open player"),
    ]),
  ]));

  const qp = qualityPanel(r.quality);
  if (qp) app.append(qp);

  app.append(el("h3", { class: "sectitle" }, "Metrics"));
  const grid = el("div", { class: "metrics-grid" });
  r.metrics.forEach((m) => grid.append(metricCard(m)));
  app.append(grid);

  if (r.asymmetry && r.asymmetry.length) {
    app.append(el("h3", { class: "sectitle" }, "Left / right comparison"));
    const asym = el("div", { class: "asym" });
    r.asymmetry.forEach((a) => asym.append(asymRow(a)));
    app.append(asym);
  }

  app.append(el("h3", { class: "sectitle" }, "Observations"));
  const findings = el("div", { class: "findings" });
  r.feedback.forEach((f) => findings.append(findingCard(f, id)));
  app.append(findings);

  // Optional: rephrase the findings as a coach's note via a local LLM (Ollama).
  const narrOut = el("div", { style: "margin-top:12px;color:#c2ccd8;font-size:14px;white-space:pre-wrap;line-height:1.55" });
  const narrBtn = el("button", { class: "btn" }, "✨ Plain-English summary (optional, local LLM)");
  narrBtn.addEventListener("click", async () => {
    narrBtn.disabled = true; narrBtn.textContent = "Asking your local LLM…";
    try {
      const res = await api.narrative(id);
      narrOut.textContent = res.available ? (res.text || "(empty response)") : (res.error || "Local LLM not available.");
    } catch (e) { narrOut.textContent = "Failed: " + e.message; }
    narrBtn.disabled = false; narrBtn.textContent = "✨ Regenerate summary";
  });
  app.append(el("div", { class: "panel", style: "margin-top:18px" }, [
    el("div", { style: "color:var(--muted);font-size:13px;margin-bottom:10px" },
      "The structured observations above remain authoritative. The optional local model only rephrases them and must not add clinical conclusions."),
    narrBtn, narrOut,
  ]));
}

export function metricCard(m) {
  const card = el("div", { class: "metric " + (m.status || "info") }, [
    el("div", { class: "m-label" }, m.label),
  ]);
  if (m.key === "foot_strike_angle") {
    card.append(el("div", { class: "m-val" }, m.text || "—"));
    card.append(el("div", { class: "m-target" }, `${fmt(m.value, 1)}° image-plane angle`));
  } else if (m.is_boolean) {
    card.append(el("div", { class: "m-val" }, m.text || "—"));
  } else {
    card.append(el("div", { class: "m-val" }, [fmt(m.value, 1), el("small", {}, " " + m.unit)]));
  }
  card.append(el("div", { class: "m-target" }, `${m.confidence || "low"} overall confidence · ${m.evidence_level || "experimental"}`));
  if (m.reference) {
    card.append(el("div", { class: "m-target" }, [
      `${m.reference.label}: ${fmt(m.reference.value, 1)} ${m.unit} · not a target · `,
      el("a", { href: m.reference.url, target: "_blank", rel: "noopener noreferrer" }, "source"),
    ]));
  }
  if (m.statistics) {
    const ci = m.statistics.ci95_mean;
    const detail = ci
      ? `n=${m.statistics.n} · mean 95% CI ${fmt(ci[0], 1)}–${fmt(ci[1], 1)} ${m.unit}`
      : `n=${m.statistics.n}`;
    card.append(el("div", { class: "m-target" }, detail));
  }
  if (m.note) card.append(el("div", { class: "m-target" }, m.note));
  if (m.per_side && (m.per_side.l != null || m.per_side.r != null)) {
    card.append(el("div", { class: "m-side" }, [
      el("span", { class: "side-l" }, ["L ", el("b", {}, fmt(m.per_side.l, 1))]),
      el("span", { class: "side-r" }, ["R ", el("b", {}, fmt(m.per_side.r, 1))]),
    ]));
  }
  return card;
}

export function asymRow(a) {
  const max = Math.max(Math.abs(a.left), Math.abs(a.right)) || 1;
  const lw = (Math.abs(a.left) / max) * 100, rw = (Math.abs(a.right) / max) * 100;
  return el("div", { class: "asym-row" }, [
    el("div", {}, [
      el("div", { class: "asym-lab" }, a.label),
      el("div", { class: "asym-bar left" }, [el("i", { style: `width:${lw}%` })]),
      el("div", { class: "side-l", style: "font-size:12px;margin-top:3px" }, `L ${fmt(a.left, 1)} ${a.unit}`),
    ]),
    el("div", { class: "asym-mid" }, [
      el("div", { class: "pct info" }, `${a.difference > 0 ? "+" : ""}${fmt(a.difference, 1)}`),
      el("div", { style: "font-size:10px;color:var(--muted)" }, a.unit + " L−R"),
    ]),
    el("div", {}, [
      el("div", { class: "asym-lab", style: "text-align:right;min-height:15px" }, " "),
      el("div", { class: "asym-bar right" }, [el("i", { style: `width:${rw}%` })]),
      el("div", { class: "side-r", style: "font-size:12px;margin-top:3px;text-align:right" }, `R ${fmt(a.right, 1)} ${a.unit}`),
    ]),
  ]);
}

export function findingCard(f, id) {
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

export function profileStr(p) {
  if (!p) return "";
  const parts = [];
  if (p.sex) parts.push(p.sex);
  if (p.height_cm) parts.push(p.height_cm + "cm");
  if (p.leg_length_cm) parts.push("leg " + p.leg_length_cm + "cm");
  if (p.speed_kmh) parts.push(p.speed_kmh + "km/h");
  if (p.age_years) parts.push(p.age_years + "y");
  if (p.body_mass_kg) parts.push(p.body_mass_kg + "kg");
  return parts.length ? " · context (" + parts.join(", ") + ")" : "";
}

export function qItem(level, msg) {
  const color = level === "warn" ? "var(--warn)" : level === "ok" ? "var(--good)" : "var(--muted)";
  const icon = level === "warn" ? "⚠" : level === "ok" ? "✓" : "ℹ";
  return el("div", { style: `font-size:13px;color:${color};padding:3px 0` }, `${icon}  ${msg}`);
}

export function qualityPanel(checks) {
  if (!checks || !checks.length) return null;
  const warns = checks.filter((c) => c.level === "warn");
  const rows = [];
  if (!warns.length) {
    const ok = checks.find((c) => c.level === "ok");
    if (ok) rows.push(qItem("ok", ok.message));
  }
  warns.forEach((c) => rows.push(qItem("warn", c.message)));
  checks.filter((c) => c.level === "info").forEach((c) => rows.push(qItem("info", c.message)));
  return el("div", { class: "panel", style: "margin:14px 0" }, [
    el("div", { style: "color:var(--muted);font-size:12px;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px" }, "Capture quality"),
    ...rows,
  ]);
}
