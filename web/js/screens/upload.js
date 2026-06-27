import * as api from "../api.js";
import { el } from "../format.js";

export default function upload(app) {
  let poseData = null, videoUrl = null;
  const status = el("div", { style: "color:var(--muted);font-size:13px;margin-top:10px" }, "No pose file loaded yet.");

  const viewSel = el("select", {}, ["side-left", "side-right", "rear", "front"]
    .map((v) => el("option", { value: v }, v)));
  const labelInput = el("input", { type: "text", placeholder: "e.g. Tuesday tempo — side" });

  const poseInput = el("input", { type: "file", accept: ".json,application/json", style: "display:none" });
  const videoInput = el("input", { type: "file", accept: "video/*", style: "display:none" });

  async function loadPose(file) {
    try {
      poseData = JSON.parse(await file.text());
      if (poseData.view) viewSel.value = poseData.view;
      status.textContent = `Loaded pose: ${poseData.frames?.length || 0} frames · view ${poseData.view || "?"} · ${poseData.source || "?"}`;
    } catch (e) {
      status.textContent = "Could not parse that pose JSON.";
    }
  }
  poseInput.addEventListener("change", (e) => e.target.files[0] && loadPose(e.target.files[0]));
  videoInput.addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (f) { videoUrl = URL.createObjectURL(f); status.textContent += "  ·  video attached"; }
  });

  const dz = el("div", { class: "dropzone" }, [
    el("div", { style: "font-size:15px;margin-bottom:6px" }, "Drop a pose .json here"),
    el("div", { style: "color:var(--muted);font-size:13px" }, "…and optionally the matching video to overlay onto"),
    el("div", { style: "margin-top:14px;display:flex;gap:10px;justify-content:center" }, [
      el("button", { class: "btn", onclick: () => poseInput.click() }, "Choose pose JSON"),
      el("button", { class: "btn btn-ghost", onclick: () => videoInput.click() }, "Attach video (optional)"),
    ]),
    status,
  ]);
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", async (e) => {
    e.preventDefault(); dz.classList.remove("drag");
    for (const f of e.dataTransfer.files) {
      if (f.name.endsWith(".json")) await loadPose(f);
      else if (f.type.startsWith("video")) { videoUrl = URL.createObjectURL(f); }
    }
  });

  const analyzeBtn = el("button", { class: "btn btn-accent" }, "Analyze");
  analyzeBtn.addEventListener("click", async () => {
    if (!poseData) { status.textContent = "Pick a pose JSON first."; return; }
    poseData.view = viewSel.value;
    analyzeBtn.textContent = "Analyzing…"; analyzeBtn.disabled = true;
    try {
      const { id } = await api.analyzePose(poseData, labelInput.value || "");
      if (videoUrl) api.setVideoUrl(id, videoUrl);
      location.hash = "#/report/" + id;
    } catch (e) {
      status.textContent = "Analyze failed: " + e.message;
      analyzeBtn.disabled = false; analyzeBtn.textContent = "Analyze";
    }
  });

  app.append(
    el("div", { class: "crumb" }, [el("a", { "data-nav": "#/library" }, "← Library")]),
    el("div", { class: "page-head" }, [el("div", {}, [
      el("h1", {}, "New analysis"),
      el("p", {}, "Everything runs locally — your video never leaves this machine."),
    ])]),
    dz,
    el("div", { style: "display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px" }, [
      el("div", { class: "field" }, [el("label", {}, "View"), viewSel]),
      el("div", { class: "field" }, [el("label", {}, "Label"), labelInput]),
    ]),
    el("div", { style: "margin:6px 0 22px" }, [analyzeBtn]),
    el("div", { class: "tips" }, [
      el("div", { style: "font-weight:600;margin-bottom:8px" }, "Turning a video into a pose file"),
      el("div", {
        style: "font-family:ui-monospace,Menlo,monospace;font-size:12px;background:#0b0f14;padding:10px 12px;border-radius:8px;border:1px solid var(--line);white-space:pre;overflow:auto",
      }, "pip install rtmlib onnxruntime opencv-python\npython extractor/extract_pose.py myrun.mp4 --view side-left -o myrun.pose.json"),
      el("ul", { style: "margin:12px 0 0;padding-left:18px" }, [
        el("li", {}, "Film one runner filling the frame, camera level and steady (a tripod is ideal)."),
        el("li", {}, "Side view shows overstride, trunk lean, and knee drive; rear view shows hip drop and crossover."),
        el("li", {}, "120/240 fps slow-mo sharpens ground-contact timing; 30/60 fps is fine for angles & cadence."),
      ]),
    ]),
  );
}
