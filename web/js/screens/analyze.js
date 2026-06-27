import * as api from "../api.js";
import { el, fmt } from "../format.js";
import { SkeletonRenderer, drawTimeline } from "../overlay.js";

export default async function analyze(app, params) {
  const id = params.id;
  const r = await api.getRun(id);
  if (!r) { app.append(el("div", { class: "empty" }, "Run not found.")); return; }

  const pose = r.pose, n = pose.frames.length, fps = pose.fps || 30;
  const videoUrl = api.getVideoUrl(id);

  const canvas = el("canvas");
  const stage = el("div", { class: "stage" });
  let video = null;
  if (videoUrl) {
    video = el("video", { src: videoUrl, playsinline: "", muted: "", loop: "" });
    video.muted = true;
    stage.append(video);
  }
  stage.append(canvas);

  const playBtn = el("button", { class: "icon-btn" }, "▶");
  const stepB = el("button", { class: "icon-btn" }, "‹");
  const stepF = el("button", { class: "icon-btn" }, "›");
  const scrub = el("input", { type: "range", min: "0", max: String(n - 1), value: "0", class: "scrub" });
  const speeds = el("div", { class: "speeds" }, [0.25, 0.5, 1].map((sp) => el("button", { "data-sp": sp }, sp + "×")));
  const tlCanvas = el("canvas");

  const opts = { skeleton: true, angles: true, refs: true, trails: false };
  const toggles = el("div", { class: "toggles" },
    [["skeleton", "Skeleton"], ["angles", "Angles"], ["refs", "Reference lines"], ["trails", "Trails"]].map(([k, lab]) => {
      const cb = el("input", { type: "checkbox" });
      cb.checked = opts[k];
      cb.addEventListener("change", () => { opts[k] = cb.checked; render(Math.floor(state.frame)); });
      return el("label", { class: "toggle" }, [cb, lab]);
    }));

  const isSide = pose.view.startsWith("side");
  const railSpec = isSide
    ? [["Trunk lean", "trunk_lean", ""], ["Knee flexion L", "knee_flexion_l", "side-l"], ["Knee flexion R", "knee_flexion_r", "side-r"]]
    : [["Pelvic tilt", "pelvic_tilt", ""]];
  const rTime = el("span", { class: "v" }, "—");
  const rPhase = el("span", { class: "phase-pill" }, "—");
  const dynRows = railSpec.map(([label, key, cls]) => ({
    label, key, span: el("span", { class: "v " + (cls || "") }, "—"),
  }));
  const rail = el("div", { class: "rail" }, [
    el("h3", {}, "Live readout"),
    readout("Time / frame", rTime),
    readout("Phase (left leg)", rPhase),
    ...dynRows.map((row) => readout(row.label, row.span)),
    el("div", { style: "margin-top:14px" }, [el("a", { class: "btn btn-sm", href: "#/report/" + id }, "← Back to report")]),
  ]);

  app.append(
    el("div", { class: "crumb" }, [
      el("a", { "data-nav": "#/library" }, "← Library"), " · ", el("a", { href: "#/report/" + id }, "Report"),
    ]),
    el("div", { class: "player" }, [
      el("div", { class: "stage-wrap" }, [
        stage,
        el("div", { class: "transport" }, [playBtn, stepB, stepF, scrub, speeds]),
        el("div", { class: "timeline" }, [tlCanvas]),
        el("div", { class: "legend" }, [
          legend("var(--left)", "Left side"), legend("var(--right)", "Right side"),
          legend("#fff", "Foot strike"), el("span", {}, "Bands = stance (foot on ground)"),
        ]),
        toggles,
      ]),
      rail,
    ]),
  );

  const renderer = new SkeletonRenderer(canvas, pose, { hasVideo: !!video });
  const series = r.series || {};
  const state = { frame: 0, playing: false, speed: 1, last: performance.now(), raf: 0 };

  requestAnimationFrame(() => { renderer.resize(); drawTimeline(tlCanvas, r); render(0); });
  const onResize = () => { renderer.resize(); drawTimeline(tlCanvas, r); render(Math.floor(state.frame)); };
  window.addEventListener("resize", onResize);

  function phaseLabel(f) {
    for (const [s, e] of r.events.stance.l || []) {
      if (f >= s && f <= e) return f < (s + e) / 2 ? "stance · loading" : "stance · push-off";
    }
    return "swing";
  }
  function updateRail(f) {
    rTime.textContent = `${(f / fps).toFixed(2)}s · ${f}/${n - 1}`;
    rPhase.textContent = phaseLabel(f);
    for (const row of dynRows) {
      const s = series[row.key];
      row.span.textContent = s && s[f] != null ? fmt(s[f], 0) + "°" : "—";
    }
    scrub.value = String(f);
  }
  function render(f) { renderer.render(f, opts); updateRail(f); }

  function loop(now) {
    const dt = (now - state.last) / 1000; state.last = now;
    if (video && !video.paused) state.frame = Math.min(n - 1, Math.max(0, Math.round(video.currentTime * fps)));
    else if (state.playing) { state.frame += dt * fps * state.speed; if (state.frame >= n - 1) state.frame = 0; }
    render(Math.floor(state.frame));
    state.raf = requestAnimationFrame(loop);
  }
  state.raf = requestAnimationFrame(loop);

  function pause() { if (video) video.pause(); state.playing = false; playBtn.textContent = "▶"; }
  function setFrame(f) {
    f = Math.max(0, Math.min(n - 1, f));
    state.frame = f;
    if (video) video.currentTime = f / fps;
    render(f);
  }

  playBtn.addEventListener("click", () => {
    if (video) {
      if (video.paused) { video.play(); playBtn.textContent = "⏸"; }
      else { video.pause(); playBtn.textContent = "▶"; }
    } else {
      state.playing = !state.playing; state.last = performance.now();
      playBtn.textContent = state.playing ? "⏸" : "▶";
    }
  });
  stepB.addEventListener("click", () => { pause(); setFrame(Math.floor(state.frame) - 1); });
  stepF.addEventListener("click", () => { pause(); setFrame(Math.floor(state.frame) + 1); });
  scrub.addEventListener("input", () => { pause(); setFrame(parseInt(scrub.value, 10)); });
  speeds.addEventListener("click", (e) => {
    const b = e.target.closest("[data-sp]"); if (!b) return;
    state.speed = parseFloat(b.dataset.sp);
    if (video) video.playbackRate = state.speed;
    [...speeds.children].forEach((c) => c.classList.toggle("on", c === b));
  });
  speeds.children[2].classList.add("on");
  tlCanvas.addEventListener("click", (e) => {
    const rect = tlCanvas.getBoundingClientRect();
    pause(); setFrame(Math.round(((e.clientX - rect.left) / rect.width) * (n - 1)));
  });

  if (params.frame != null) { pause(); setFrame(parseInt(params.frame, 10)); }

  return () => {
    cancelAnimationFrame(state.raf);
    window.removeEventListener("resize", onResize);
    if (video) video.pause();
  };
}

function readout(k, v) { return el("div", { class: "readout" }, [el("span", { class: "k" }, k), v]); }
function legend(color, txt) { return el("span", {}, [el("span", { class: "dot", style: `background:${color}` }), txt]); }
