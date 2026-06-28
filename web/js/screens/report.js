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
      el("p", {}, `${viewLabel(s.view)} view · ${fmt(s.cadence, 0)} spm · ${fmt(s.duration, 1)}s · score ${fmt(s.overall_score, 0)}/100 · ${s.n_findings} finding${s.n_findings === 1 ? "" : "s"}${profileStr(s.profile)}`),
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
    app.append(el("h3", { class: "sectitle" }, "Left / right symmetry"));
    const asym = el("div", { class: "asym" });
    r.asymmetry.forEach((a) => asym.append(asymRow(a)));
    app.append(asym);
  }

  app.append(el("h3", { class: "sectitle" }, "Coach feedback"));
  const findings = el("div", { class: "findings" });
  r.feedback.forEach((f) => findings.append(findingCard(f, id)));
  app.append(findings);

  const plan = planSection(r.plan);
  if (plan) app.append(plan);

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
      "The rule-based feedback above is the source of truth. Optionally rephrase it as a coach's note using a local LLM — nothing leaves your machine."),
    narrBtn, narrOut,
  ]));
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

function profileStr(p) {
  if (!p) return "";
  const parts = [];
  if (p.sex) parts.push(p.sex);
  if (p.height_cm) parts.push(p.height_cm + "cm");
  if (p.leg_length_cm) parts.push("leg " + p.leg_length_cm + "cm");
  if (p.speed_kmh) parts.push(p.speed_kmh + "km/h");
  return parts.length ? " · personalized (" + parts.join(", ") + ")" : "";
}

function qItem(level, msg) {
  const color = level === "warn" ? "var(--warn)" : level === "ok" ? "var(--good)" : "var(--muted)";
  const icon = level === "warn" ? "⚠" : level === "ok" ? "✓" : "ℹ";
  return el("div", { style: `font-size:13px;color:${color};padding:3px 0` }, `${icon}  ${msg}`);
}

function qualityPanel(checks) {
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

function planSection(plan) {
  if (!plan || !plan.length) return null;
  const wrap = el("div", {}, [
    el("h3", { class: "sectitle" }, "Corrective plan"),
    el("div", { style: "color:var(--muted);font-size:13px;margin:-6px 0 12px" },
      "Targeted drills for your top findings. General training guidance, not a medical prescription — for pain or a diagnosed injury, see a physio."),
  ]);
  plan.forEach((g) => {
    wrap.append(el("div", { class: "panel", style: "margin-bottom:12px" }, [
      el("div", { style: "font-weight:600;margin-bottom:4px" }, g.title),
      ...g.exercises.map((ex) =>
        el("div", { style: "padding:9px 0;border-top:1px solid var(--line)" }, [
          el("div", {}, [el("b", {}, ex.name), el("span", { style: "color:var(--muted)" }, " — " + ex.why)]),
          el("div", { style: "color:var(--muted);font-size:12.5px;margin-top:3px" }, [
            el("span", { class: "side-l" }, "Dose: "), ex.dose, "   ",
            el("span", { class: "side-r" }, "Progress: "), ex.progression,
          ]),
        ])),
    ]));
  });
  return wrap;
}
