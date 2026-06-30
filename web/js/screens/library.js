import * as api from "../api.js";
import { el, fmt, scoreClass, timeAgo, viewLabel } from "../format.js";
import { sparkline } from "../charts.js";
import { SkeletonRenderer } from "../overlay.js";

export default async function library(app) {
  const activeUser = api.getActiveUser();
  const runs = await api.listRuns(activeUser?.id);
  const userLabel = activeUser ? activeUser.name + "'s" : "Your";

  app.append(el("div", { class: "page-head" }, [
    el("div", {}, [
      el("h1", {}, userLabel + " runs"),
      el("p", {}, `${runs.length} ${runs.length === 1 ? "analysis" : "analyses"} · stored locally on this machine`),
    ]),
    el("a", { class: "btn btn-accent", "data-nav": "#/upload" }, "+ New analysis"),
  ]));

  if (!runs.length) {
    app.append(el("div", { class: "empty" }, [
      el("p", {}, "No runs yet."),
      el("button", {
        class: "btn btn-accent",
        onclick: async () => { await api.reseed(); location.reload(); },
      }, "Load demo runs"),
    ]));
    return;
  }

  const chrono = [...runs].reverse();
  app.append(el("div", { class: "panel", style: "margin-bottom:18px;display:flex;align-items:center;gap:22px;flex-wrap:wrap" }, [
    el("div", {}, [
      el("div", { style: "color:var(--muted);font-size:12px;margin-bottom:4px" }, "Overall score trend"),
      el("div", { html: sparkline(chrono.map((r) => r.score), { w: 240, h: 40, color: "#2fbf71" }) }),
    ]),
    el("div", { style: "color:var(--muted);font-size:13px" }, `Latest: ${fmt(runs[0].score, 0)}/100`),
  ]));

  const grid = el("div", { class: "grid" });
  runs.forEach((r) => {
    const canvas = el("canvas", { class: "thumb" });
    grid.append(el("div", {
      class: "runcard",
      onclick: () => { location.hash = "#/report/" + r.id; },
    }, [
      canvas,
      el("div", { class: "body" }, [
        el("div", { class: "row" }, [
          el("div", {}, [
            el("div", { class: "label" }, r.label || viewLabel(r.view) + " run"),
            el("div", { class: "meta" }, `${viewLabel(r.view)} · ${fmt(r.cadence, 0)} spm · ${timeAgo(r.created_at)}`),
          ]),
          el("div", { class: "score-badge " + scoreClass(r.score) }, fmt(r.score, 0)),
        ]),
        el("div", { class: "finding" },
          r.n_findings ? `${r.n_findings} thing${r.n_findings > 1 ? "s" : ""} to work on` : "No major flags"),
      ]),
    ]));
  });
  app.append(grid);

  // Lazy skeleton thumbnails (fetch each run's pose, draw one representative frame).
  for (let i = 0; i < runs.length; i++) {
    const detail = await api.getRun(runs[i].id);
    if (!detail) continue;
    const canvas = grid.children[i].querySelector("canvas");
    try {
      const rend = new SkeletonRenderer(canvas, detail.pose, { hasVideo: false });
      const foi = detail.frames_of_interest || {};
      const f = foi.l_strike ?? foi.max_pelvic_drop ?? Math.floor(detail.pose.frames.length / 2);
      rend.render(f, { skeleton: true, angles: false, refs: false, trails: false });
    } catch (e) { /* ignore */ }
  }
}
