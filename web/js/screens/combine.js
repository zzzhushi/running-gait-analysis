import * as api from "../api.js";
import { el, fmt, gradeClass } from "../format.js";
import { metricCard, asymRow, findingCard, planSection, qualityPanel } from "./report.js";

// Multi-view fusion: merge a side run (sagittal) and a rear run (frontal) of the same
// session into one report. Pure client-side composition of two stored AnalysisResults.
export default async function combine(app) {
  const runs = await api.listRuns();
  const sideRuns = runs.filter((r) => r.view.startsWith("side"));
  const rearRuns = runs.filter((r) => r.view === "rear" || r.view === "front");

  app.append(el("div", { class: "crumb" }, [el("a", { "data-nav": "#/library" }, "← Library")]));
  app.append(el("div", { class: "page-head" }, [el("div", {}, [
    el("h1", {}, "Combined report — side + rear"),
    el("p", {}, "Merge a side and a rear run of the same session into one picture (sagittal + frontal)."),
  ])]));

  if (!sideRuns.length || !rearRuns.length) {
    app.append(el("div", { class: "empty" }, "Need at least one side run and one rear run — analyze both views first."));
    return;
  }

  const sideSel = sel(sideRuns, "Side run");
  const rearSel = sel(rearRuns, "Rear run");
  const out = el("div", {});
  const draw = async () => {
    out.innerHTML = "";
    const [side, rear] = await Promise.all([api.getRun(sideSel.value), api.getRun(rearSel.value)]);
    if (side && rear) out.append(renderCombined(side, rear, sideSel.value, rearSel.value));
  };
  sideSel.addEventListener("change", draw);
  rearSel.addEventListener("change", draw);
  app.append(el("div", { class: "compare-pick" }, [
    el("span", { style: "color:var(--muted);font-size:13px" }, "Side:"), sideSel,
    el("span", { style: "color:var(--muted);font-size:13px" }, "Rear:"), rearSel,
  ]), out);
  draw();
}

function sel(runs, fallback) {
  return el("select", { style: "max-width:260px" },
    runs.map((r) => el("option", { value: r.id }, (r.label || fallback) + " · " + r.grade)));
}

function renderCombined(side, rear, sideId, rearId) {
  const score = (side.summary.overall_score + rear.summary.overall_score) / 2;
  const grade = score >= 85 ? "A" : score >= 72 ? "B" : score >= 58 ? "C" : score >= 42 ? "D" : "E";
  const wrap = el("div", {});

  wrap.append(el("div", { class: "scorecard" }, [
    el("div", { class: "big " + gradeClass(grade) }, grade),
    el("div", { class: "sc-meta" }, [
      el("h2", {}, "Combined — side + rear"),
      el("p", {}, `${fmt(side.summary.cadence, 0)} spm · combined score ${fmt(score, 0)}/100 · sagittal + frontal`),
    ]),
    el("div", { style: "margin-left:auto;display:flex;gap:8px" }, [
      el("a", { class: "btn btn-sm", href: "#/report/" + sideId }, "Side report"),
      el("a", { class: "btn btn-sm", href: "#/report/" + rearId }, "Rear report"),
    ]),
  ]));

  const q = (side.quality || []).concat(rear.quality || []);
  const qp = qualityPanel(q.filter((c, i, a) => a.findIndex((x) => x.message === c.message) === i));
  if (qp) wrap.append(qp);

  wrap.append(el("h3", { class: "sectitle" }, "Metrics — side (sagittal)"));
  const g1 = el("div", { class: "metrics-grid" });
  side.metrics.forEach((m) => g1.append(metricCard(m)));
  wrap.append(g1);

  wrap.append(el("h3", { class: "sectitle" }, "Metrics — rear (frontal)"));
  const g2 = el("div", { class: "metrics-grid" });
  rear.metrics.filter((m) => m.key !== "cadence").forEach((m) => g2.append(metricCard(m)));
  wrap.append(g2);

  const asym = (side.asymmetry || []).concat(rear.asymmetry || []);
  if (asym.length) {
    wrap.append(el("h3", { class: "sectitle" }, "Left / right symmetry"));
    const a = el("div", { class: "asym" });
    asym.forEach((x) => a.append(asymRow(x)));
    wrap.append(a);
  }

  let findings = (side.feedback || []).map((f) => ({ ...f, _id: sideId }))
    .concat((rear.feedback || []).map((f) => ({ ...f, _id: rearId })));
  const real = findings.filter((f) => f.severity !== "good");
  if (real.length) findings = real;
  const order = { high: 0, med: 1, low: 2, good: 3 };
  findings.sort((a, b) => order[a.severity] - order[b.severity]);
  wrap.append(el("h3", { class: "sectitle" }, "Coach feedback (both views)"));
  const fl = el("div", { class: "findings" });
  findings.forEach((f) => fl.append(findingCard(f, f._id)));
  wrap.append(fl);

  const plan = [];
  const seen = new Set();
  (side.plan || []).concat(rear.plan || []).forEach((g) => {
    if (!seen.has(g.key)) { seen.add(g.key); plan.push(g); }
  });
  const ps = planSection(plan);
  if (ps) wrap.append(ps);

  return wrap;
}
